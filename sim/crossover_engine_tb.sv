//=============================================================================
// Modulo    : crossover_engine_tb
// Archivo   : crossover_engine_tb.sv
// Proyecto  : Filtro Crossover IIR - Tang Nano 9K
// Autor     : Joan
// Fecha     : 2026-06-25
// Version   : 2.0
//-----------------------------------------------------------------------------
// Descripcion:
//   Testbench de verificacion bit-exact para el motor crossover_engine.
//   Sigue el formato sincrono del testbench modelo con contadores de errores
//   y aserciones concurrentes muestra a muestra.
//=============================================================================

`timescale 1ns/1ps
`default_nettype none

module crossover_engine_tb;

  import crossover_pkg::*;

  // Periodo de reloj del sistema (27 MHz -> 37.037ns)
  parameter PER = 37.037;

  // Senales del testbench para UUT
  logic        clk_sys;
  logic        rst_n;
  logic [23:0] id_sample;
  logic        ic_sample_valid;
  logic [23:0] od_woofer;
  logic [23:0] od_tweeter;
  logic        oc_output_valid;
  logic        oc_ready;

  // Contadores y control de simulacion
  integer in_sample_cnt;    // Contador de muestras de entrada
  integer sample_cnt;       // Contador de muestras revisadas de salida
  integer error_cnt_lpf;    // Contador de errores Woofer (LPF)
  integer error_cnt_hpf;    // Contador de errores Tweeter (HPF)
  logic   end_sim;          // Indicacion de simulacion on/off
  logic   load_data;        // Inicio de lectura de datos

  // Gestion de I/O texto (cadenas de 0s y 1s)
  integer data_in_file_val;
  integer data_out_lpf_file_val;
  integer data_out_hpf_file_val;
  
  logic signed [15:0] data_in_file;
  logic signed [23:0] golden_lpf_bits;
  logic signed [23:0] golden_hpf_bits;
  
  integer scan_data_in;
  integer scan_data_out_lpf;
  integer scan_data_out_hpf;

  // Senales de comparacion y formas de onda
  logic signed [23:0] out_lpf_F;   // Salida Golden LPF (referencia)
  logic signed [23:0] out_lpf_M;   // Salida RTL LPF (Woofer)
  logic signed [23:0] out_hpf_F;   // Salida Golden HPF (referencia)
  logic signed [23:0] out_hpf_M;   // Salida RTL HPF (Tweeter)

  // Generador de Reloj controlado por simulacion
  always #(PER/2) clk_sys = !clk_sys & end_sim;

  // Instanciacion del modulo bajo prueba (UUT)
  crossover_engine #(
    .COEFF_LPF_FILE ("sim/data/coeff_lpf_48k.bin"),
    .COEFF_HPF_FILE ("sim/data/coeff_hpf_48k.bin")
  ) UUT (
    .clk_sys         (clk_sys),
    .rst_n           (rst_n),
    .id_sample       (id_sample),
    .ic_sample_valid (ic_sample_valid),
    .od_woofer       (od_woofer),
    .od_tweeter      (od_tweeter),
    .oc_output_valid (oc_output_valid),
    .oc_ready        (oc_ready)
  );

  // Inicializacion de simulacion
  initial begin
    $display("###########################################");
    $display(" INICIANDO TEST DE VERIFICACION BIT-EXACT");
    $display("###########################################");

    // Abrir archivos en formato texto binario
    data_in_file_val = $fopen("sim/data/noise.bin", "r");
    if (!data_in_file_val) begin
      $display("[ERROR] No se pudo abrir el archivo sim/data/noise.bin");
      $stop;
    end

    data_out_lpf_file_val = $fopen("sim/data/golden_lpf_fixed.txt", "r");
    if (!data_out_lpf_file_val) begin
      $display("[ERROR] No se pudo abrir el archivo sim/data/golden_lpf_fixed.txt");
      $stop;
    end

    data_out_hpf_file_val = $fopen("sim/data/golden_hpf_fixed.txt", "r");
    if (!data_out_hpf_file_val) begin
      $display("[ERROR] No se pudo abrir el archivo sim/data/golden_hpf_fixed.txt");
      $stop;
    end

    // Inicializacion de registros
    sample_cnt      = 0;
    error_cnt_lpf   = 0;
    error_cnt_hpf   = 0;
    end_sim         = 1'b1;
    in_sample_cnt   = 0;
    clk_sys         = 1'b1;
    ic_sample_valid = 1'b0;
    id_sample       = 24'd0;
    rst_n           = 1'b0; // Reset activo al inicio
    load_data       = 1'b0;

    #(10*PER);
    load_data = 1'b1;
  end

  // Proceso de lectura de datos de entrada (estimulo sincrono controlado por handshake)
  always @(posedge clk_sys) begin
    if (load_data) begin
      // Solo inyectamos muestra si el motor esta listo y no estamos en medio de un pulso
      if (oc_ready && !ic_sample_valid) begin
        if (!$feof(data_in_file_val)) begin
          in_sample_cnt   = in_sample_cnt + 1;
          scan_data_in    = $fscanf(data_in_file_val, "%b\n", data_in_file);
          
          // Extension de signo y padding de 16-bit a 24-bit
          id_sample       <= #(PER/10) {data_in_file, 8'b0};
          rst_n           <= #(PER/10) 1'b1; // Libera reset
          ic_sample_valid <= #(PER/10) 1'b1; // Pulso de validez
        end else begin
          ic_sample_valid <= #(PER/10) 1'b0;
          load_data       =  #(PER/10) 1'b0;
        end
      end else begin
        ic_sample_valid   <= #(PER/10) 1'b0; // Apagar pulso al ciclo siguiente
      end
    end else if (!load_data && rst_n == 1'b1) begin
      // Dejar transcurrir ciclos para procesar las ultimas muestras en la pipeline del hardware
      end_sim <= #(100*PER) 1'b0;
    end
  end

  // Proceso de lectura de datos de salida de referencia y captura RTL
  always @(posedge clk_sys) begin
    if (oc_output_valid) begin
      sample_cnt = sample_cnt + 1;
      if (!$feof(data_out_lpf_file_val) && !$feof(data_out_hpf_file_val)) begin
        scan_data_out_lpf = $fscanf(data_out_lpf_file_val, "%b\n", golden_lpf_bits);
        scan_data_out_hpf = $fscanf(data_out_hpf_file_val, "%b\n", golden_hpf_bits);

        out_lpf_F <= #(PER/10) golden_lpf_bits; // Referencia Golden
        out_lpf_M <= #(PER/10) od_woofer;        // Salida RTL
        
        out_hpf_F <= #(PER/10) golden_hpf_bits; // Referencia Golden
        out_hpf_M <= #(PER/10) od_tweeter;       // Salida RTL
      end else begin
        end_sim = #(10*PER) 1'b0;
      end
    end
  end

  // Comparacion muestra a muestra: Canal LPF (Woofer)
  always @(out_lpf_M, out_lpf_F) begin
    Assert_error_lpf:
      assert (out_lpf_M == out_lpf_F)
        else begin
          error_cnt_lpf = error_cnt_lpf + 1;
          $display("[ERROR LPF] Muestra %0d: RTL = %06X, Golden = %06X", sample_cnt, out_lpf_M, out_lpf_F);
        end
  end

  // Comparacion muestra a muestra: Canal HPF (Tweeter)
  always @(out_hpf_M, out_hpf_F) begin
    Assert_error_hpf:
      assert (out_hpf_M == out_hpf_F)
        else begin
          error_cnt_hpf = error_cnt_hpf + 1;
          $display("[ERROR HPF] Muestra %0d: RTL = %06X, Golden = %06X", sample_cnt, out_hpf_M, out_hpf_F);
        end
  end

  // Fin de la simulacion e informe de resultados
  always @(end_sim) begin
    if (!end_sim) begin
      $display("###########################################");
      $display("           FIN DE LA SIMULACION");
      $display("###########################################");
      $display(" Muestras de Entrada Inyectadas: %0d", in_sample_cnt);
      $display(" Muestras de Salida Verificadas: %0d", sample_cnt);
      $display(" Errores Woofer LPF            : %0d", error_cnt_lpf);
      $display(" Errores Tweeter HPF           : %0d", error_cnt_hpf);
      $display("###########################################");
      if (error_cnt_lpf == 0 && error_cnt_hpf == 0) begin
        $display("   [EXITO] EL RTL ES 100%% BIT-EXACTO RESPECTO AL GOLDEN MODEL!");
      end else begin
        $display("   [FAIL] Se detectaron errores de cuantizacion o logica en el RTL.");
      end
      $display("###########################################");
      
      $fclose(data_in_file_val);
      $fclose(data_out_lpf_file_val);
      $fclose(data_out_hpf_file_val);
      #(PER*2) $stop;
    end
  end

endmodule

`default_nettype wire
