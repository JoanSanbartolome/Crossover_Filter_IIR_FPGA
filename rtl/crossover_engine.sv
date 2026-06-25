//=============================================================================
// Modulo    : crossover_engine
// Archivo   : crossover_engine.sv
// Proyecto  : Filtro Crossover IIR - Tang Nano 9K
// Autor     : Joan
// Fecha     : 2026-06-21
// Version   : 1.0
//-----------------------------------------------------------------------------
// Descripcion:
//   Motor de procesamiento DSP para el Crossover IIR.
//   - Comparte un unico multiplicador de 24 x 40 bits para realizar 20 MACs.
//   - Cascada de 4 biquads: 2 LPF para Woofer, 2 HPF para Tweeter.
//   - Registros de estado basados en flip-flops internos distribuidos.
//   - Inicializacion de coeficientes via ficheros de texto ($readmemh).
//
// Parametros:
//   COEFF_LPF_FILE : Ruta del archivo de coeficientes para el LPF (.bin de bits)
//   COEFF_HPF_FILE : Ruta del archivo de coeficientes para el HPF (.bin de bits)
//
// Interfaces:
//   clk_sys        : Reloj del sistema (27 MHz)
//   rst_n          : Reset activo bajo (sincrono)
//   id_sample      : Muestra de entrada de 24 bits
//   ic_sample_valid: Pulso de muestra de entrada lista para procesar
//   od_woofer      : Muestra filtrada Woofer (24 bits)
//   od_tweeter     : Muestra filtrada Tweeter (24 bits)
//   oc_output_valid: Pulso indicando que las salidas estan listas
//=============================================================================

`default_nettype none

module crossover_engine 
  import crossover_pkg::*;
#(
  parameter string COEFF_LPF_FILE = "sim/data/coeff_lpf_48k.bin",
  parameter string COEFF_HPF_FILE = "sim/data/coeff_hpf_48k.bin"
) (
  input  var logic        clk_sys,
  input  var logic        rst_n,
  // Entrada
  input  var logic [23:0] id_sample,
  input  var logic        ic_sample_valid,
  // Salidas
  output var logic [23:0] od_woofer,
  output var logic [23:0] od_tweeter,
  output var logic        oc_output_valid,
  output var logic        oc_ready
);

  //---------------------------------------------------------------------------
  // Coeficientes IIR hardcodeados (Q4.36, 40 bits con signo, Butterworth 2o orden LR4)
  // Fc = 2000 Hz, Fs = 48000 Hz
  // NOTA: NO usar $readmemh - Gowin lo ignora en sintesis e inicializa BSRAM a cero.
  // Los coeficientes se definen como constantes para inferirse como LUT-ROM o FF.
  // Formato: [b0, b1, b2, -a1, -a2]
  //---------------------------------------------------------------------------

  // LPF: Butterworth 2o orden @ Fc=2kHz, Fs=48kHz (float: b0=0.01440144, a1=-1.63299316, a2=0.69059892)
  localparam logic [COEFF_WIDTH-1:0] LPF_B0  = 40'h003AFD0135; //  0.0144014403
  localparam logic [COEFF_WIDTH-1:0] LPF_B1  = 40'h0075FA026A; //  0.0288028807
  localparam logic [COEFF_WIDTH-1:0] LPF_B2  = 40'h003AFD0135; //  0.0144014403
  localparam logic [COEFF_WIDTH-1:0] LPF_MA1 = 40'h1A20BD700C; //  1.6329931619 (negado: -a1)
  localparam logic [COEFF_WIDTH-1:0] LPF_MA2 = 40'hF4F34E8B20; // -0.6905989232 (negado: -a2)

  // HPF: Butterworth 2o orden @ Fc=2kHz, Fs=48kHz (float: b0=0.83089802, a1=-1.63299316, a2=0.69059892)
  localparam logic [COEFF_WIDTH-1:0] HPF_B0  = 40'h0D4B5BB93B; //  0.8308980213
  localparam logic [COEFF_WIDTH-1:0] HPF_B1  = 40'hE569488D8A; // -1.6617960426
  localparam logic [COEFF_WIDTH-1:0] HPF_B2  = 40'h0D4B5BB93B; //  0.8308980213
  localparam logic [COEFF_WIDTH-1:0] HPF_MA1 = 40'h1A20BD700C; //  1.6329931619 (negado: -a1)
  localparam logic [COEFF_WIDTH-1:0] HPF_MA2 = 40'hF4F34E8B20; // -0.6905989232 (negado: -a2)

  // Arrays de coeficientes accesibles por indice
  logic signed [COEFF_WIDTH-1:0] coeff_lpf_mem_r [0:4];
  logic signed [COEFF_WIDTH-1:0] coeff_hpf_mem_r [0:4];

  // Inicializacion en simulacion Y en sintesis.
  // Gowin infiere la inicializacion en hardware a partir del bloque initial.
  initial begin
    coeff_lpf_mem_r[0] = LPF_B0;
    coeff_lpf_mem_r[1] = LPF_B1;
    coeff_lpf_mem_r[2] = LPF_B2;
    coeff_lpf_mem_r[3] = LPF_MA1;
    coeff_lpf_mem_r[4] = LPF_MA2;

    coeff_hpf_mem_r[0] = HPF_B0;
    coeff_hpf_mem_r[1] = HPF_B1;
    coeff_hpf_mem_r[2] = HPF_B2;
    coeff_hpf_mem_r[3] = HPF_MA1;
    coeff_hpf_mem_r[4] = HPF_MA2;

    // En simulacion, si se pasan los archivos, cargamos desde ellos usando $readmemb
`ifndef SYNTHESIS
    if (COEFF_LPF_FILE != "") begin
      $display("[INFO] Cargando coeficientes LPF desde: %s", COEFF_LPF_FILE);
      $readmemb(COEFF_LPF_FILE, coeff_lpf_mem_r);
    end
    if (COEFF_HPF_FILE != "") begin
      $display("[INFO] Cargando coeficientes HPF desde: %s", COEFF_HPF_FILE);
      $readmemb(COEFF_HPF_FILE, coeff_hpf_mem_r);
    end
`endif
  end

  //---------------------------------------------------------------------------
  // Registros de Estado de los Biquads (Flip-Flops)
  // 4 biquads: 0=LPF1, 1=LPF2, 2=HPF1, 3=HPF2
  // Para cada biquad guardamos 4 retardos: 0=x[n-1], 1=x[n-2], 2=y[n-1], 3=y[n-2]
  // NOTA: (* keep *) evita que Gowin infiera este array como BSRAM.
  //       state_reg_r DEBE ser flip-flops: es accedido asincronamente.
  //---------------------------------------------------------------------------
  (* keep *) logic signed [DATA_WIDTH-1:0] state_reg_r [0:3][0:3];

  // Muestra de entrada registrada para el procesamiento estable de la trama
  logic signed [DATA_WIDTH-1:0] input_sample_r;

  // Resultados intermedios registrados de cada biquad
  logic signed [DATA_WIDTH-1:0] y_temp_r [0:3];

  //---------------------------------------------------------------------------
  // Maquina de Estados (FSM) de Procesamiento MAC
  //---------------------------------------------------------------------------
  typedef enum logic [1:0] {
    STATE_IDLE    = 2'b00,
    STATE_COMPUTE = 2'b01,
    STATE_DONE    = 2'b10
  } state_t;

  state_t             state_r;
  logic [4:0]         step_cnt_r; // Cuenta de 0 a 19 para los 20 productos MAC

  //---------------------------------------------------------------------------
  // Logica del Datapath DSP Sincrono/Combinacional
  //---------------------------------------------------------------------------
  logic [1:0]                  bq_idx_s;    // Biquad activo (0..3)
  logic [2:0]                  term_idx_s;  // Termino activo (0..4)
  logic signed [DATA_WIDTH-1:0]  mult_val_a_s;
  logic signed [COEFF_WIDTH-1:0] mult_val_b_s;
  logic signed [ACCUM_WIDTH-1:0] accum_r;

  assign bq_idx_s   = step_cnt_r / 5;
  assign term_idx_s = step_cnt_r % 5;

  // Seleccion de la entrada 'x[n]' para el biquad activo
  logic signed [DATA_WIDTH-1:0] x_in_active_s;
  always_comb begin
    case (bq_idx_s)
      2'd0:    x_in_active_s = input_sample_r; // LPF1 toma la entrada directa
      2'd1:    x_in_active_s = y_temp_r[0];    // LPF2 toma la salida de LPF1
      2'd2:    x_in_active_s = input_sample_r; // HPF1 toma la entrada directa
      2'd3:    x_in_active_s = y_temp_r[2];    // HPF2 toma la salida de HPF1
      default: x_in_active_s = input_sample_r;
    endcase
  end

  // Multiplexacion de los operandos del multiplicador compartido
  always_comb begin
    // Operando A (Datos - 24 bits con signo)
    case (term_idx_s)
      3'd0:    mult_val_a_s = x_in_active_s;
      3'd1:    mult_val_a_s = state_reg_r[bq_idx_s][0]; // x[n-1]
      3'd2:    mult_val_a_s = state_reg_r[bq_idx_s][1]; // x[n-2]
      3'd3:    mult_val_a_s = state_reg_r[bq_idx_s][2]; // y[n-1]
      3'd4:    mult_val_a_s = state_reg_r[bq_idx_s][3]; // y[n-2]
      default: mult_val_a_s = 24'd0;
    endcase

    // Operando B (Coeficientes - 40 bits con signo)
    if (bq_idx_s == 2'd0 || bq_idx_s == 2'd1) begin
      mult_val_b_s = coeff_lpf_mem_r[term_idx_s];
    end else begin
      mult_val_b_s = coeff_hpf_mem_r[term_idx_s];
    end
  end

  // Calculo del producto parcial de 64 bits con signo
  logic signed [DATA_WIDTH + COEFF_WIDTH - 1 : 0] product_s;
  assign product_s = mult_val_a_s * mult_val_b_s;

  // Calculo combinacional del acumulador del siguiente paso
  logic signed [ACCUM_WIDTH-1:0] accum_next_s;
  assign accum_next_s = (term_idx_s == 3'd0) ? 
                        $signed(product_s) : 
                        accum_r + $signed(product_s);

  // Truncamiento y saturacion combinacional del resultado del biquad activo
  // El producto Q23.0 * Q4.36 genera Q27.36. Hacemos shift de 36 bits a la derecha.
  logic signed [ACCUM_WIDTH-1:0] y_shifted_s;
  logic signed [DATA_WIDTH-1:0]  y_saturada_s;

  assign y_shifted_s = accum_next_s >>> Q_FRAC_BITS;

  always_comb begin
    // Saturacion a 24 bits con signo
    if (y_shifted_s > $signed(24'sh7FFFFF)) begin
      y_saturada_s = 24'sh7FFFFF;
    end else if (y_shifted_s < $signed(24'sh800000)) begin
      y_saturada_s = 24'sh800000;
    end else begin
      y_saturada_s = y_shifted_s[DATA_WIDTH-1:0];
    end
  end

  //---------------------------------------------------------------------------
  // Control secuencial de la FSM
  //---------------------------------------------------------------------------
  always_ff @(posedge clk_sys) begin
    if (!rst_n) begin
      state_r         <= STATE_IDLE;
      step_cnt_r      <= 5'd0;
      accum_r         <= '0;
      input_sample_r  <= 24'd0;
      oc_output_valid <= 1'b0;
      od_woofer       <= 24'd0;
      od_tweeter      <= 24'd0;

      // Inicializacion de registros de estado a 0
      for (int bq = 0; bq < 4; bq++) begin
        for (int st = 0; st < 4; st++) begin
          state_reg_r[bq][st] <= 24'd0;
        end
        y_temp_r[bq] <= 24'd0;
      end
    end else begin
      oc_output_valid <= 1'b0; // Pulso por defecto

      case (state_r)

        STATE_IDLE: begin
          if (ic_sample_valid) begin
            input_sample_r <= $signed(id_sample);
            step_cnt_r     <= 5'd0;
            accum_r        <= '0;
            state_r        <= STATE_COMPUTE;
          end
        end

        STATE_COMPUTE: begin
          // Guardar el acumulador sincronamente
          accum_r <= accum_next_s;

          // Si es el ultimo termino del biquad activo (termino 4),
          // registramos el resultado del biquad y actualizamos sus retardos.
          if (term_idx_s == 3'd4) begin
            y_temp_r[bq_idx_s] <= y_saturada_s;

            // Actualizar retardos del biquad activo
            state_reg_r[bq_idx_s][1] <= state_reg_r[bq_idx_s][0]; // x[n-2] <= x[n-1]
            state_reg_r[bq_idx_s][0] <= x_in_active_s;            // x[n-1] <= x[n]
            state_reg_r[bq_idx_s][3] <= state_reg_r[bq_idx_s][2]; // y[n-2] <= y[n-1]
            state_reg_r[bq_idx_s][2] <= y_saturada_s;             // y[n-1] <= y[n]
          end

          // Control del contador de pasos
          if (step_cnt_r == 5'd19) begin
            state_r <= STATE_DONE;
          end else begin
            step_cnt_r <= step_cnt_r + 1'b1;
          end
        end

        STATE_DONE: begin
          od_woofer       <= y_temp_r[1]; // Salida de LPF2
          od_tweeter      <= y_temp_r[3]; // Salida de HPF2
          oc_output_valid <= 1'b1;
          state_r         <= STATE_IDLE;
        end

        default: state_r <= STATE_IDLE;
      endcase
    end
  end

  // Senal combinacional indicando que la FSM esta lista
  assign oc_ready = (state_r == STATE_IDLE);

endmodule : crossover_engine

`default_nettype wire
