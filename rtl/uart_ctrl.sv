//=============================================================================
// Módulo    : uart_ctrl
// Archivo   : uart_ctrl.sv
// Proyecto  : Filtro Crossover IIR — Tang Nano 9K
// Autor     : Joan
// Fecha     : 2026-06-21
// Versión   : 1.0
//-----------------------------------------------------------------------------
// Descripción:
//   Controlador UART bidireccional de alta velocidad (921600 bps) a clk_sys (27 MHz).
//   - RX: Utiliza un acumulador de fase DDS de 16 bits para un muestreo exacto
//         en el centro del bit, previniendo errores acumulados.
//   - TX: Transmite tramas compuestas de 8 bytes delimitadas por 0xAA y 0x55.
//
// Interfaces:
//   clk_sys        : Reloj del sistema (27 MHz)
//   rst_n          : Reset activo bajo (síncrono)
//   id_woofer      : Muestra filtrada Woofer (24 bits)
//   id_tweeter     : Muestra filtrada Tweeter (24 bits)
//   ic_tx_valid    : Pulso de inicio de transmisión de la trama de muestra
//   oc_tx_busy     : Bandera indicando que la TX está en progreso
//   oc_rx_cmd      : Comando de 8 bits recibido del PC
//   oc_rx_valid    : Pulso de comando válido recibido
//   uart_rxd       : Línea física RX
//   uart_txd       : Línea física TX
//=============================================================================

`default_nettype none

module uart_ctrl 
  import crossover_pkg::*;
(
  input  var logic        clk_sys,
  input  var logic        rst_n,
  // Datapath Audio TX
  input  var logic [23:0] id_woofer,
  input  var logic [23:0] id_tweeter,
  input  var logic        ic_tx_valid,
  output var logic        oc_tx_busy,
  // Interfaz de modo transparente / bypass
  input  var logic        ic_tx_mode,       // 0 = normal, 1 = transparente (byte único)
  input  var logic [7:0]  id_single_byte,   // Byte a enviar en modo transparente
  // Controlpath RX
  output var logic [7:0]  oc_rx_cmd,
  output var logic        oc_rx_valid,
  // Pines Físicos
  input  var logic        uart_rxd,
  output var logic        uart_txd
);

  //---------------------------------------------------------------------------
  // Constantes de Baudrate (921600 bps a 27 MHz)
  // Paso de fase DDS de 16 bits = (921600 * 2^16) / 27,000,000 = 2236.96... ≈ 2237
  //---------------------------------------------------------------------------
  localparam logic [15:0] DDS_PHASE_STEP = 16'd2237;

  //---------------------------------------------------------------------------
  // Sincronizador de entrada RX para evitar metaestabilidad
  //---------------------------------------------------------------------------
  logic uart_rx_sync0_r;
  logic uart_rx_sync1_r;

  always_ff @(posedge clk_sys) begin
    if (!rst_n) begin
      uart_rx_sync0_r <= 1'b1;
      uart_rx_sync1_r <= 1'b1;
    end else begin
      uart_rx_sync0_r <= uart_rxd;
      uart_rx_sync1_r <= uart_rx_sync0_r;
    end
  end

  // Detección de flanco de bajada para inicio de START
  logic rx_falling_edge_s;
  assign rx_falling_edge_s = (uart_rx_sync1_r == 1'b0) && (uart_rx_sync0_r == 1'b1);

  //---------------------------------------------------------------------------
  // Receptor UART (RX) con DDS de 16 bits
  //---------------------------------------------------------------------------
  typedef enum logic [1:0] {
    RX_STATE_IDLE  = 2'b00,
    RX_STATE_START = 2'b01,
    RX_STATE_DATA  = 2'b10,
    RX_STATE_STOP  = 2'b11
  } rx_state_t;

  rx_state_t   rx_state_r;
  logic [15:0] rx_phase_accum_r;
  logic [2:0]  rx_bit_cnt_r;
  logic [7:0]  rx_shifter_r;

  always_ff @(posedge clk_sys) begin
    if (!rst_n) begin
      rx_state_r       <= RX_STATE_IDLE;
      rx_phase_accum_r <= 16'd0;
      rx_bit_cnt_r     <= 3'd0;
      rx_shifter_r     <= 8'd0;
      oc_rx_cmd        <= 8'd0;
      oc_rx_valid      <= 1'b0;
    end else begin
      oc_rx_valid <= 1'b0; // Pulso por defecto

      case (rx_state_r)

        RX_STATE_IDLE: begin
          if (uart_rx_sync1_r == 1'b0) begin // Flanco de bajada de START
            // Inicializar acumulador a mitad del rango (0x8000) para muestrear en el centro del bit
            rx_phase_accum_r <= 16'h8000;
            rx_state_r       <= RX_STATE_START;
          end
        end

        RX_STATE_START: begin
          logic [16:0] sum_s;
          sum_s = rx_phase_accum_r + DDS_PHASE_STEP;
          rx_phase_accum_r <= sum_s[15:0];

          if (sum_s[16]) begin // Desbordamiento -> centro de bit
            if (uart_rx_sync1_r == 1'b0) begin // Confirmamos START en bajo
              rx_state_r   <= RX_STATE_DATA;
              rx_bit_cnt_r <= 3'd0;
            end else begin
              rx_state_r   <= RX_STATE_IDLE; // Falsa alarma
            end
          end
        end

        RX_STATE_DATA: begin
          logic [16:0] sum_s;
          sum_s = rx_phase_accum_r + DDS_PHASE_STEP;
          rx_phase_accum_r <= sum_s[15:0];

          if (sum_s[16]) begin // Desbordamiento -> centro del bit de datos
            rx_shifter_r <= {uart_rx_sync1_r, rx_shifter_r[7:1]}; // LSB first
            if (rx_bit_cnt_r == 3'd7) begin
              rx_state_r <= RX_STATE_STOP;
            end else begin
              rx_bit_cnt_r <= rx_bit_cnt_r + 1'b1;
            end
          end
        end

        RX_STATE_STOP: begin
          logic [16:0] sum_s;
          sum_s = rx_phase_accum_r + DDS_PHASE_STEP;
          rx_phase_accum_r <= sum_s[15:0];

          if (sum_s[16]) begin // Desbordamiento -> centro de bit de STOP
            if (uart_rx_sync1_r == 1'b1) begin // Bit de stop válido (alto)
              oc_rx_cmd   <= rx_shifter_r;
              oc_rx_valid <= 1'b1;
            end
            rx_state_r <= RX_STATE_IDLE;
          end
        end

        default: rx_state_r <= RX_STATE_IDLE;
      endcase
    end
  end

  //---------------------------------------------------------------------------
  // Transmisor UART (TX)
  // Secuencia el envío de una trama compuesta de 8 bytes:
  // Byte 0: 0xAA (START)
  // Byte 1: id_woofer[23:16]
  // Byte 2: id_woofer[15:8]
  // Byte 3: id_woofer[7:0]
  // Byte 4: id_tweeter[23:16]
  // Byte 5: id_tweeter[15:8]
  // Byte 6: id_tweeter[7:0]
  // Byte 7: 0x55 (END)
  //---------------------------------------------------------------------------
  typedef enum logic [1:0] {
    TX_STATE_IDLE      = 2'b00,
    TX_STATE_SEND_BYTE = 2'b01,
    TX_STATE_BIT_WAIT  = 2'b10,
    TX_STATE_NEXT_BYTE = 2'b11
  } tx_state_t;

  tx_state_t   tx_state_r;
  logic [15:0] tx_phase_accum_r;
  logic [3:0]  tx_bit_cnt_r;   // 0 = START, 1..8 = DATA, 9 = STOP
  logic [2:0]  tx_byte_cnt_r;  // Contador de 0 a 7 para los 8 bytes de la trama
  logic [7:0]  tx_current_byte_s;
  logic        uart_txd_r;

  // Registros locales para congelar los datos de entrada
  logic [23:0] tx_woofer_reg_r;
  logic [23:0] tx_tweeter_reg_r;

  assign uart_txd = uart_txd_r;

  // Seleccion del byte de la trama a enviar usando los registros locales
  always_comb begin
    if (ic_tx_mode) begin
      tx_current_byte_s = id_single_byte;
    end else begin
      case (tx_byte_cnt_r)
        3'd0: tx_current_byte_s = UART_START_BYTE;
        3'd1: tx_current_byte_s = tx_woofer_reg_r[23:16];
        3'd2: tx_current_byte_s = tx_woofer_reg_r[15:8];
        3'd3: tx_current_byte_s = tx_woofer_reg_r[7:0];
        3'd4: tx_current_byte_s = tx_tweeter_reg_r[23:16];
        3'd5: tx_current_byte_s = tx_tweeter_reg_r[15:8];
        3'd6: tx_current_byte_s = tx_tweeter_reg_r[7:0];
        3'd7: tx_current_byte_s = UART_END_BYTE;
        default: tx_current_byte_s = UART_END_BYTE;
      endcase
    end
  end

  always_ff @(posedge clk_sys) begin
    if (!rst_n) begin
      tx_state_r       <= TX_STATE_IDLE;
      tx_phase_accum_r <= 16'd0;
      tx_bit_cnt_r     <= 4'd0;
      tx_byte_cnt_r    <= 3'd0;
      uart_txd_r       <= 1'b1;
      oc_tx_busy       <= 1'b0;
      tx_woofer_reg_r  <= 24'd0;
      tx_tweeter_reg_r <= 24'd0;
    end else begin
      case (tx_state_r)

        TX_STATE_IDLE: begin
          if (ic_tx_valid) begin
            oc_tx_busy       <= 1'b1;
            tx_byte_cnt_r    <= 3'd0;
            tx_bit_cnt_r     <= 4'd0; // START bit
            tx_phase_accum_r <= 16'd0;
            uart_txd_r       <= 1'b0; // Bit de START (bajo)
            tx_woofer_reg_r  <= id_woofer;
            tx_tweeter_reg_r <= id_tweeter;
            tx_state_r       <= TX_STATE_BIT_WAIT;
          end else begin
            uart_txd_r <= 1'b1;
            oc_tx_busy <= 1'b0;
          end
        end

        TX_STATE_BIT_WAIT: begin
          logic [16:0] sum_s;
          sum_s = tx_phase_accum_r + DDS_PHASE_STEP;
          tx_phase_accum_r <= sum_s[15:0];

          if (sum_s[16]) begin // Desbordamiento -> tiempo de emitir el siguiente bit
            if (tx_bit_cnt_r == 4'd9) begin
              // Hemos completado el bit de STOP de este byte
              if (ic_tx_mode || (tx_byte_cnt_r == 3'd7)) begin
                // Trama completa o byte unico transmitido
                tx_state_r <= TX_STATE_IDLE;
              end else begin
                tx_byte_cnt_r <= tx_byte_cnt_r + 1'b1;
                tx_bit_cnt_r  <= 4'd0; // Siguiente byte bit START
                uart_txd_r    <= 1'b0; // Bit START (bajo)
              end
            end else begin
              // Siguiente bit (datos o stop)
              tx_bit_cnt_r <= tx_bit_cnt_r + 1'b1;
              if (tx_bit_cnt_r == 4'd7) begin
                // Si tx_bit_cnt_r actual es 7, se incrementara a 8 (bit 7 de datos - el ultimo)
                uart_txd_r <= tx_current_byte_s[7];
              end else if (tx_bit_cnt_r == 4'd8) begin
                // Si tx_bit_cnt_r actual es 8, se incrementara a 9 (bit de STOP)
                uart_txd_r <= 1'b1;
              end else begin
                // Si tx_bit_cnt_r actual es 0..6, se incrementara a 1..7.
                // Transmitimos tx_current_byte_s[tx_bit_cnt_r] usando el valor previo para indexar
                uart_txd_r <= tx_current_byte_s[tx_bit_cnt_r];
              end
            end
          end
        end

        default: tx_state_r <= TX_STATE_IDLE;
      endcase
    end
  end

endmodule : uart_ctrl

`default_nettype wire
