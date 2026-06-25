//=============================================================================
// Modulo    : top_crossover_tb
// Archivo   : top_crossover_tb.sv
// Proyecto  : Filtro Crossover IIR — Tang Nano 9K
// Autor     : Joan
// Fecha     : 2026-06-25
// Version   : 2.1
//-----------------------------------------------------------------------------
// Descripcion:
//   Testbench de integracion completo para el top-level UART-only (top_crossover.sv).
//   - Envia el comando de activacion CMD_STREAM (0x03).
//   - Envia muestras de estimulo leidas desde noise.bin empaquetadas en tramas UART
//     de 4 bytes (0xAA, MSB, LSB, 0x55) a 921600 bps.
//   - Recibe y deserializa las tramas compuestas de salida de 8 bytes de la FPGA.
//   - Realiza la verificacion mediante aserciones concurrentes externas disparadas
//     por eventos de senal.
//=============================================================================

`timescale 1ns/1ps
`default_nettype none

module top_crossover_tb;

  import crossover_pkg::*;

  // Parametros de simulacion
  localparam time CLK_PERIOD = 37.037ns;   // Reloj de 27 MHz
  localparam time BIT_PERIOD = 1085.069ns; // 921600 bps (1s / 921600)
  
  // Numero de muestras para el test de integracion
  localparam int NUM_TEST_SAMPLES = 10000;

  // Senales de la UUT
  logic clk_sys;
  logic rst_n;
  logic uart_rxd;
  logic uart_txd;
  logic [5:0] leds_n;

  // Instanciacion del Top-Level (UUT)
  top_crossover #(
    .COEFF_LPF_FILE ("sim/data/coeff_lpf_48k.bin"),
    .COEFF_HPF_FILE ("sim/data/coeff_hpf_48k.bin")
  ) uut (
    .clk_sys  (clk_sys),
    .rst_n    (rst_n),
    .uart_rxd (uart_rxd),
    .uart_txd (uart_txd),
    .o_leds_n (leds_n)
  );

  // Generador de Reloj de 27 MHz
  initial begin
    clk_sys = 1'b0;
    forever #(CLK_PERIOD / 2) clk_sys = ~clk_sys;
  end

  // Variables de lectura y validacion
  integer fp_in;
  integer fp_gold_lpf;
  integer fp_gold_hpf;
  integer fp_out_lpf;
  integer fp_out_hpf;
  integer scan_status;
  
  logic [15:0] in_sample_16b;
  logic [23:0] golden_lpf_24b;
  logic [23:0] golden_hpf_24b;

  // Contadores
  int samples_sent = 0;
  int samples_received = 0;
  int error_cnt_lpf = 0;
  int error_cnt_hpf = 0;
  logic tx_done = 1'b0;

  // Senales de comparacion y formas de onda
  logic signed [23:0] out_lpf_F;   // Salida Golden LPF (referencia)
  logic signed [23:0] out_lpf_M;   // Salida RTL LPF (Woofer)
  logic signed [23:0] out_hpf_F;   // Salida Golden HPF (referencia)
  logic signed [23:0] out_hpf_M;   // Salida RTL HPF (Tweeter)

  // Tarea para enviar un byte por UART (PC -> FPGA)
  task automatic send_uart_byte(input logic [7:0] data);
    int bit_idx;
    begin
      // Bit de START (bajo)
      uart_rxd = 1'b0;
      #(BIT_PERIOD);
      
      // Bits de datos (LSB first)
      for (bit_idx = 0; bit_idx < 8; bit_idx++) begin
        uart_rxd = data[bit_idx];
        #(BIT_PERIOD);
      end
      
      // Bit de STOP (alto)
      uart_rxd = 1'b1;
      #(BIT_PERIOD);
    end
  endtask

  // Tarea para enviar una trama de audio UART de 4 bytes (0xAA, MSB, LSB, 0x55)
  task automatic send_audio_frame(input logic signed [15:0] sample);
    begin
      send_uart_byte(UART_START_BYTE);
      send_uart_byte(sample[15:8]); // MSB
      send_uart_byte(sample[7:0]);  // LSB
      send_uart_byte(UART_END_BYTE);
    end
  endtask

  // Tarea para recibir un byte por UART (FPGA -> PC)
  task automatic receive_uart_byte(output logic [7:0] data);
    int bit_idx;
    begin
      @(negedge uart_txd);
      #(BIT_PERIOD / 2); // Ir al centro del bit START
      
      if (uart_txd != 1'b0) begin
        $display("[WARN] START bit invalido recibido");
      end
      
      #(BIT_PERIOD); // Ir al centro del primer bit de datos
      for (bit_idx = 0; bit_idx < 8; bit_idx++) begin
        data[bit_idx] = uart_txd;
        #(BIT_PERIOD);
      end
      
      if (uart_txd != 1'b1) begin
        $display("[WARN] STOP bit invalido recibido (Valor: %b)", uart_txd);
      end
      
      #(BIT_PERIOD * 0.2); // Pequena espera en el STOP
    end
  endtask

  // Proceso de Envio de Estimulos y Comandos
  initial begin
    // Inicializacion de senales
    rst_n    = 1'b0;
    uart_rxd = 1'b1;

    // Reset del sistema
    #(CLK_PERIOD * 10);
    rst_n = 1'b1;
    #(CLK_PERIOD * 10);

    // Abrir archivos de datos
    fp_in = $fopen("sim/data/noise.bin", "r");
    if (fp_in == 0) begin
      $display("[ERROR] No se pudo abrir el archivo sim/data/noise.bin");
      $finish;
    end

    $display("[INFO] Enviando comando de inicializacion CMD_STREAM (0x03)...");
    send_uart_byte(CMD_STREAM);
    #(BIT_PERIOD * 5);

    $display("[INFO] Comenzando envio de tramas de audio...");

    // Enviamos solo el numero de muestras configurado
    while (samples_sent < NUM_TEST_SAMPLES && !$feof(fp_in)) begin
      scan_status = $fscanf(fp_in, "%b\n", in_sample_16b);
      if (scan_status == 1) begin
        send_audio_frame(in_sample_16b);
        samples_sent++;
        // Espera entre muestras para no saturar el canal UART (la salida requiere 80 periodos de bit por trama)
        #(BIT_PERIOD * 50);
      end
    end

    $fclose(fp_in);
    $display("[INFO] Envio de estimulos finalizado. Muestras enviadas: %0d", samples_sent);
    tx_done = 1'b1;
  end

  // Proceso de Recepcion de Respuestas y Lectura de Referencias
  initial begin
    logic [7:0] rx_frame [0:7];
    logic signed [23:0] woofer_rtl;
    logic signed [23:0] tweeter_rtl;

    fp_gold_lpf = $fopen("sim/data/golden_lpf_fixed.txt", "r");
    fp_gold_hpf = $fopen("sim/data/golden_hpf_fixed.txt", "r");
    fp_out_lpf  = $fopen("sim/data/output_lpf_rtl.txt", "w");
    fp_out_hpf  = $fopen("sim/data/output_hpf_rtl.txt", "w");

    if (fp_gold_lpf == 0 || fp_gold_hpf == 0 || fp_out_lpf == 0 || fp_out_hpf == 0) begin
      $display("[ERROR] No se pudieron abrir los archivos de referencia o de salida.");
      $finish;
    end

    $display("[INFO] Receptor UART del testbench listo y a la escucha...");

    // Bucle para recibir y verificar cada trama de 8 bytes transmitida por la FPGA
    while (!tx_done || samples_received < samples_sent) begin
      // Recibir los 8 bytes de la trama
      for (int i = 0; i < 8; i++) begin
        receive_uart_byte(rx_frame[i]);
      end

      // Validar delimitadores de trama
      if (rx_frame[0] !== UART_START_BYTE || rx_frame[7] !== UART_END_BYTE) begin
        $display("[ERROR] Trama de salida corrupta (START=0x%02X, END=0x%02X)", rx_frame[0], rx_frame[7]);
      end else begin
        samples_received++;

        // Reconstruccion de las muestras de 24 bits
        woofer_rtl  = {rx_frame[1], rx_frame[2], rx_frame[3]};
        tweeter_rtl = {rx_frame[4], rx_frame[5], rx_frame[6]};

        // Escribir salidas RTL a archivo
        $fwrite(fp_out_lpf, "%b\n", woofer_rtl);
        $fwrite(fp_out_hpf, "%b\n", tweeter_rtl);

        // Leer referencias del Golden Model
        if ($fscanf(fp_gold_lpf, "%b\n", golden_lpf_24b) == 1 &&
            $fscanf(fp_gold_hpf, "%b\n", golden_hpf_24b) == 1) begin
          
          // Asignaciones no bloqueantes con retardo para disparar las aserciones
          out_lpf_F <= #(CLK_PERIOD/10) golden_lpf_24b;
          out_lpf_M <= #(CLK_PERIOD/10) woofer_rtl;
          
          out_hpf_F <= #(CLK_PERIOD/10) golden_hpf_24b;
          out_hpf_M <= #(CLK_PERIOD/10) tweeter_rtl;
        end
      end
    end

    $fclose(fp_gold_lpf);
    $fclose(fp_gold_hpf);
    $fclose(fp_out_lpf);
    $fclose(fp_out_hpf);

    // Dar un par de periodos de reloj antes de cerrar la simulacion
    #(CLK_PERIOD * 5);

    $display("==========================================================");
    $display("           REPORTE DE INTEGRACION UART-TOP");
    $display("==========================================================");
    $display(" Muestras UART Enviadas: %0d", samples_sent);
    $display(" Muestras UART Recibidas: %0d", samples_received);
    $display(" Errores Woofer LPF     : %0d", error_cnt_lpf);
    $display(" Errores Tweeter HPF    : %0d", error_cnt_hpf);
    $display("==========================================================");
    if (error_cnt_lpf == 0 && error_cnt_hpf == 0 && samples_received == samples_sent) begin
      $display(" [EXITO] LA INTEGRACION UART-TOP ES 100%% BIT-EXACTA CON EL GOLDEN MODEL!");
    end else begin
      $display(" [FALLO] Se detectaron errores de transmision o procesamiento.");
    end
    $display("==========================================================");
    $stop;
  end

  // Comparacion muestra a muestra: Canal LPF (Woofer)
  always @(out_lpf_M, out_lpf_F) begin
    Assert_error_lpf:
      assert (out_lpf_M == out_lpf_F)
        else begin
          error_cnt_lpf = error_cnt_lpf + 1;
          $display("[ERROR LPF] Muestra %0d: RTL = %06X, Golden = %06X", samples_received, out_lpf_M, out_lpf_F);
        end
  end

  // Comparacion muestra a muestra: Canal HPF (Tweeter)
  always @(out_hpf_M, out_hpf_F) begin
    Assert_error_hpf:
      assert (out_hpf_M == out_hpf_F)
        else begin
          error_cnt_hpf = error_cnt_hpf + 1;
          $display("[ERROR HPF] Muestra %0d: RTL = %06X, Golden = %06X", samples_received, out_hpf_M, out_hpf_F);
        end
  end

endmodule : top_crossover_tb

`default_nettype wire
