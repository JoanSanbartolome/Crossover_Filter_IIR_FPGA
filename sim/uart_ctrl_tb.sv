//=============================================================================
// Módulo    : uart_ctrl_tb
// Archivo   : uart_ctrl_tb.sv
// Proyecto  : Filtro Crossover IIR — Tang Nano 9K
// Autor     : Joan
// Fecha     : 2026-06-22
// Versión   : 1.5
//-----------------------------------------------------------------------------
// Descripción:
//   Testbench unitario con sincronización robusta para las señales de control,
//   evitando condiciones de carrera al esperar la propagación de oc_tx_busy.
//=============================================================================

`timescale 1ns/1ps
`default_nettype none

module uart_ctrl_tb;

  import crossover_pkg::*;

  // Parámetros de simulación exactos basados en el DDS
  localparam time CLK_PERIOD = 37.037ns;      // 27 MHz
  localparam time BIT_PERIOD = 1085.136ns;    // 921600 bps promedio real

  // Señales
  logic        clk_sys;
  logic        rst_n;
  logic [23:0] id_woofer;
  logic [23:0] id_tweeter;
  logic        ic_tx_valid;
  logic        oc_tx_busy;
  logic [7:0]  oc_rx_cmd;
  logic        oc_rx_valid;
  logic        uart_rxd;
  logic        uart_txd;

  // Instanciación de la UUT
  uart_ctrl uut (
    .clk_sys     (clk_sys),
    .rst_n       (rst_n),
    .id_woofer   (id_woofer),
    .id_tweeter  (id_tweeter),
    .ic_tx_valid (ic_tx_valid),
    .oc_tx_busy  (oc_tx_busy),
    .oc_rx_cmd   (oc_rx_cmd),
    .oc_rx_valid (oc_rx_valid),
    .uart_rxd    (uart_rxd),
    .uart_txd    (uart_txd)
  );

  // Generador de reloj
  initial begin
    clk_sys = 1'b0;
    forever #(CLK_PERIOD / 2) clk_sys = ~clk_sys;
  end

  // Traza de depuración por ciclo de clk (se desactiva para reducir el tamaño del log en el test final)
  /*
  initial begin
    @(posedge rst_n);
    forever begin
      @(posedge clk_sys);
      if (oc_tx_busy) begin
        $display("[TRACE-TX] Time=%0t clk=%0d | State=%s Byte=%0d Bit=%0d | txd=%b phase=%0d", 
                 $time, $time/CLK_PERIOD, uut.tx_state_r.name(), uut.tx_byte_cnt_r, uut.tx_bit_cnt_r, uart_txd, uut.tx_phase_accum_r);
      end
    end
  end
  */

  // Monitor de recepción TX con resincronización asíncrona real por byte
  task automatic receive_and_print_frame();
    logic [7:0] rx_bytes [0:7];
    int byte_idx;
    int bit_idx;
    begin
      $display("[MONITOR-TX] Esperando flanco de bajada de START de la trama...");
      
      for (byte_idx = 0; byte_idx < 8; byte_idx++) begin
        // Resincronización en el flanco de bajada de cada byte
        @(negedge uart_txd);
        
        #(BIT_PERIOD / 2); // Ir al centro del bit START
        
        if (uart_txd != 1'b0) begin
          $display("[MONITOR-TX] [ERROR] START bit inválido en byte %0d", byte_idx);
        end
        
        // Ir al centro del bit 0
        #(BIT_PERIOD);
        
        // Leer 8 bits de datos (LSB first)
        for (bit_idx = 0; bit_idx < 8; bit_idx++) begin
          rx_bytes[byte_idx][bit_idx] = uart_txd;
          #(BIT_PERIOD);
        end
        
        // Verificar bit de STOP (debe ser alto)
        if (uart_txd != 1'b1) begin
          $display("[MONITOR-TX] [ERROR] STOP bit inválido en byte %0d (Valor: %b) en tiempo %0t", byte_idx, uart_txd, $time);
        end
        
        // Esperamos 0.2 bits para asegurar que seguimos en el STOP y evitar condiciones de carrera
        // en el negedge del siguiente byte
        #(BIT_PERIOD * 0.2);
      end
      
      $display("[MONITOR-TX] Trama recibida con éxito:");
      $display("  - Byte 0 (START)  : 0x%02X (Esperado: 0xAA)", rx_bytes[0]);
      $display("  - Woofer MSB/M/L  : 0x%02X, 0x%02X, 0x%02X (Valor: 0x%06X)", rx_bytes[1], rx_bytes[2], rx_bytes[3], {rx_bytes[1], rx_bytes[2], rx_bytes[3]});
      $display("  - Tweeter MSB/M/L : 0x%02X, 0x%02X, 0x%02X (Valor: 0x%06X)", rx_bytes[4], rx_bytes[5], rx_bytes[6], {rx_bytes[4], rx_bytes[5], rx_bytes[6]});
      $display("  - Byte 7 (END)    : 0x%02X (Esperado: 0x55)", rx_bytes[7]);
    end
  endtask

  // Inyección de bytes RX
  task automatic send_uart_byte(input logic [7:0] data);
    int bit_idx;
    begin
      uart_rxd = 1'b0;
      #(BIT_PERIOD);
      for (bit_idx = 0; bit_idx < 8; bit_idx++) begin
        uart_rxd = data[bit_idx];
        #(BIT_PERIOD);
      end
      uart_rxd = 1'b1;
      #(BIT_PERIOD);
    end
  endtask

  // Proceso principal
  initial begin
    $display("[INFO] Iniciando Simulación de uart_ctrl_tb...");
    
    rst_n       = 1'b0;
    id_woofer   = 24'h000000;
    id_tweeter  = 24'h000000;
    ic_tx_valid = 1'b0;
    uart_rxd    = 1'b1;
    
    #(CLK_PERIOD * 5);
    rst_n = 1'b1;
    #(CLK_PERIOD * 5);
    
    $display("\n--- TEST 1: Transmisión UART (TX) ---");
    fork
      receive_and_print_frame();
    join_none
    
    @(posedge clk_sys);
    id_woofer   = 24'h123456;
    id_tweeter  = 24'hABCDEF;
    ic_tx_valid = 1'b1;
    @(posedge clk_sys);
    ic_tx_valid = 1'b0;
    
    // Esperar un ciclo de reloj para que la UUT propague oc_tx_busy a 1
    @(posedge clk_sys);
    
    while (oc_tx_busy) begin
      @(posedge clk_sys);
    end
    $display("[TX] Transmisión terminada.");
    
    #(BIT_PERIOD * 10);
    
    $display("\n--- TEST 2: Recepción UART (RX) ---");
    fork
      begin
        send_uart_byte(CMD_START);
      end
      begin
        fork
          begin
            #(BIT_PERIOD * 15);
            $display("[RX] [ERROR] Timeout esperando oc_rx_valid.");
          end
          begin
            @(posedge oc_rx_valid);
            $display("[RX] [OK] Comando recibido: 0x%02X (Esperado: 0x01)", oc_rx_cmd);
          end
        join_any
        disable fork;
      end
    join
    
    #(BIT_PERIOD * 5);
    $display("[INFO] Simulación unitaria de UART finalizada.");
    $finish;
  end

endmodule : uart_ctrl_tb

`default_nettype wire
