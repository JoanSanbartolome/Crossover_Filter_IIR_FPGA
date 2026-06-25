//=============================================================================
// Modulo    : top_crossover
// Archivo   : top_crossover.sv
// Proyecto  : Filtro Crossover IIR - Tang Nano 9K
// Autor     : Joan
// Fecha     : 2026-06-25
// Version   : 2.1
//-----------------------------------------------------------------------------
// Descripcion:
//   Top-level del sistema de crossover digital IIR (Version UART-only).
//   - Se ha eliminado por completo la lectura desde tarjeta SD y el buffer PCM.
//   - Los datos de audio de entrada se reciben directamente a traves de la UART.
//   - Una FSM de control simplificada habilita/deshabilita el procesamiento
//     segun los comandos recibidos por UART (CMD_STREAM para iniciar).
//   - Soporta un modo Bypass (CMD_BYPASS = 0x04) donde las muestras se copian
//     directamente en la FIFO de salida sin pasar por los filtros IIR.
//   - Utiliza una FIFO de salida de 48 bits de ancho para desacoplar el motor DSP
//     de la transmision UART de vuelta al host.
//
// Parametros:
//   COEFF_LPF_FILE : Ruta del fichero de coeficientes LPF (.bin de texto bits)
//   COEFF_HPF_FILE : Ruta del fichero de coeficientes HPF (.bin de texto bits)
//
// Interfaces:
//   clk_sys        : Reloj del sistema (27 MHz, pin 52)
//   rst_n          : Reset activo bajo (sincrono, boton fisico)
//   // Pines UART
//   uart_rxd       : USB-UART RX
//   uart_txd       : USB-UART TX
//   // Indicadores LED integrados (activos bajo)
//   output var logic [5:0] o_leds_n
//=============================================================================

`default_nettype none

module top_crossover 
  import crossover_pkg::*;
#(
  parameter string COEFF_LPF_FILE  = "sim/data/coeff_lpf_48k.bin",
  parameter string COEFF_HPF_FILE  = "sim/data/coeff_hpf_48k.bin"
) (
  input  var logic clk_sys,
  input  var logic rst_n,
  // Interfaz fisica UART
  input  var logic uart_rxd,
  output var logic uart_txd,
  // Indicadores LED integrados (activos bajo)
  output var logic [5:0] o_leds_n
);

  //---------------------------------------------------------------------------
  // Interconexion de senales y Enables
  //---------------------------------------------------------------------------
  logic ce_sample_s;
  logic ce_bck_s;

  // Generador de Clock Enables (Mantenido para sincronizaciones de baudios/muestra)
  clk_gen u_clk_gen (
    .clk_sys      (clk_sys),
    .rst_n        (rst_n),
    .ic_fs_select (1'b0), // Fijo a 48 kHz
    .oc_ce_sample (ce_sample_s),
    .oc_ce_bck    (ce_bck_s)
  );

  // Senales Motor Crossover
  logic [23:0] woofer_sample_s;
  logic [23:0] tweeter_sample_s;
  logic        engine_output_valid_s;
  logic        engine_ready_s;

  // Logica de recepcion y multiplexacion en modo Streaming UART
  logic        streaming_mode_r;
  logic        bypass_mode_r;
  logic [7:0]  rx_sample_msb_r;
  logic [7:0]  rx_sample_lsb_r;
  logic        rx_sample_ready_r;

  // Senales UART
  logic [7:0]  uart_rx_cmd_s;
  logic        uart_rx_valid_s;
  logic        uart_tx_busy_s;
  logic        uart_tx_trigger_s;
  logic [23:0] woofer_tx_s;
  logic [23:0] tweeter_tx_s;

  // Mecanismo de descarte y deteccion de desincronizacion
  logic [3:0]  rx_bad_bytes_cnt_r;
  logic        rx_sync_error_r;

  // Ventana deslizante de 4 bytes para el encuadre de tramas UART RX
  logic [7:0]  rx_stream_buf_r [0:3];

  // Proceso de encuadre UART RX en Streaming
  always_ff @(posedge clk_sys) begin
    if (!rst_n) begin
      rx_stream_buf_r[0]  <= 8'd0;
      rx_stream_buf_r[1]  <= 8'd0;
      rx_stream_buf_r[2]  <= 8'd0;
      rx_stream_buf_r[3]  <= 8'd0;
      rx_sample_msb_r     <= 8'd0;
      rx_sample_lsb_r     <= 8'd0;
      rx_sample_ready_r   <= 1'b0;
      rx_bad_bytes_cnt_r  <= 4'd0;
      rx_sync_error_r     <= 1'b0;
    end else begin
      rx_sample_ready_r <= 1'b0; // Pulso de un ciclo de reloj
      
      if (streaming_mode_r && uart_rx_valid_s) begin
        rx_stream_buf_r[0] <= rx_stream_buf_r[1];
        rx_stream_buf_r[1] <= rx_stream_buf_r[2];
        rx_stream_buf_r[2] <= rx_stream_buf_r[3];
        rx_stream_buf_r[3] <= uart_rx_cmd_s;

        // Comprobamos la trama utilizando la ventana deslizante combinada
        if (rx_stream_buf_r[1] == UART_START_BYTE && uart_rx_cmd_s == UART_END_BYTE) begin
          rx_sample_msb_r    <= rx_stream_buf_r[2];
          rx_sample_lsb_r    <= rx_stream_buf_r[3];
          rx_sample_ready_r  <= 1'b1;
          rx_bad_bytes_cnt_r <= 4'd0; // Sincronizacion OK
          rx_sync_error_r    <= 1'b0;
        end else begin
          // Si no hay trama valida, incrementamos contador de bytes corruptos
          if (rx_bad_bytes_cnt_r < 4'd12) begin
            rx_bad_bytes_cnt_r <= rx_bad_bytes_cnt_r + 1'b1;
          end else begin
            rx_sync_error_r <= 1'b1; // Activacion de bandera tras 12 bytes erroneos
          end
        end
      end
    end
  end

  // Senales de datos listas para inyeccion en el motor DSP
  logic [23:0] dsp_input_sample_s;
  logic        dsp_input_valid_s;

  // Si hay error de desincronizacion inyectamos silencio, si no la muestra decodificada extendida
  assign dsp_input_sample_s = rx_sync_error_r ? 24'd0 : {rx_sample_msb_r, rx_sample_lsb_r, 8'b0};
  
  // En modo normal iniciamos el DSP, en modo Bypass no inyectamos muestras al DSP
  assign dsp_input_valid_s  = rx_sample_ready_r && streaming_mode_r && !bypass_mode_r;

  // Motor del Crossover IIR
  crossover_engine #(
    .COEFF_LPF_FILE (COEFF_LPF_FILE),
    .COEFF_HPF_FILE (COEFF_HPF_FILE)
  ) u_crossover_engine (
    .clk_sys         (clk_sys),
    .rst_n           (rst_n),
    .id_sample       (dsp_input_sample_s),
    .ic_sample_valid (dsp_input_valid_s),
    .od_woofer       (woofer_sample_s),
    .od_tweeter      (tweeter_sample_s),
    .oc_output_valid (engine_output_valid_s),
    .oc_ready        (engine_ready_s)
  );

  // Controlador UART Fisico
  uart_ctrl u_uart_ctrl (
    .clk_sys        (clk_sys),
    .rst_n          (rst_n),
    .id_woofer      (woofer_tx_s),
    .id_tweeter     (tweeter_tx_s),
    .ic_tx_valid    (uart_tx_trigger_s),
    .oc_tx_busy     (uart_tx_busy_s),
    .oc_rx_cmd      (uart_rx_cmd_s),
    .oc_rx_valid    (uart_rx_valid_s),
    .uart_rxd       (uart_rxd),
    .uart_txd       (uart_txd),
    .ic_tx_mode     (1'b0), // Fijo a modo procesado normal
    .id_single_byte (8'd0)  // No se usa modo transparente
  );

  //---------------------------------------------------------------------------
  // FIFO de Salida Sincrona de 48 bits (Woofer + Tweeter)
  //---------------------------------------------------------------------------
  localparam int OUT_FIFO_DEPTH = 256;
  localparam int OUT_ADDR_WIDTH = $clog2(OUT_FIFO_DEPTH);

  logic [47:0]             out_fifo_mem_r [0:OUT_FIFO_DEPTH-1];
  logic [OUT_ADDR_WIDTH:0] out_wr_ptr_r;
  logic [OUT_ADDR_WIDTH:0] out_rd_ptr_r;

  logic out_fifo_wr_s;
  logic out_fifo_rd_s;
  logic out_fifo_empty_s;
  logic out_fifo_full_s;

  // Logica de multiplexacion del trigger de escritura en la FIFO:
  // - En modo normal: escribe cuando la salida del DSP es valida (engine_output_valid_s).
  // - En modo bypass: escribe al vuelo cuando se recibe la muestra por UART (rx_sample_ready_r).
  assign out_fifo_wr_s = (bypass_mode_r ? (rx_sample_ready_r && streaming_mode_r) : engine_output_valid_s) && !out_fifo_full_s;
  assign out_fifo_rd_s = uart_tx_trigger_s; 

  // Seleccion de datos para escribir en la FIFO
  logic [23:0] fifo_data_woofer_s;
  logic [23:0] fifo_data_tweeter_s;
  assign fifo_data_woofer_s  = bypass_mode_r ? dsp_input_sample_s : woofer_sample_s;
  assign fifo_data_tweeter_s = bypass_mode_r ? dsp_input_sample_s : tweeter_sample_s;

  // Escritura y lectura en la FIFO
  always_ff @(posedge clk_sys) begin
    if (out_fifo_wr_s) begin
      out_fifo_mem_r[out_wr_ptr_r[OUT_ADDR_WIDTH-1:0]] <= {fifo_data_woofer_s, fifo_data_tweeter_s};
    end
  end

  always_ff @(posedge clk_sys) begin
    if (!rst_n) begin
      out_wr_ptr_r <= '0;
      out_rd_ptr_r <= '0;
    end else begin
      if (out_fifo_wr_s) out_wr_ptr_r <= out_wr_ptr_r + 1'b1;
      if (out_fifo_rd_s) out_rd_ptr_r <= out_rd_ptr_r + 1'b1;
    end
  end

  assign out_fifo_empty_s = (out_wr_ptr_r == out_rd_ptr_r);
  assign out_fifo_full_s  = (out_wr_ptr_r[OUT_ADDR_WIDTH-1:0] == out_rd_ptr_r[OUT_ADDR_WIDTH-1:0]) && 
                            (out_wr_ptr_r[OUT_ADDR_WIDTH] != out_rd_ptr_r[OUT_ADDR_WIDTH]);

  // Desempaquetado de la salida de la FIFO
  assign {woofer_tx_s, tweeter_tx_s} = out_fifo_mem_r[out_rd_ptr_r[OUT_ADDR_WIDTH-1:0]];

  // Evitamos disparo multiple registrando el trigger
  logic uart_tx_trigger_s_r;

  // Transmision UART en segundo plano
  assign uart_tx_trigger_s = !out_fifo_empty_s && !uart_tx_busy_s && !uart_tx_trigger_s_r;

  always_ff @(posedge clk_sys) begin
    if (!rst_n) begin
      uart_tx_trigger_s_r <= 1'b0;
    end else begin
      uart_tx_trigger_s_r <= uart_tx_trigger_s;
    end
  end

  //---------------------------------------------------------------------------
  // FSM de Control Global del Sistema
  //---------------------------------------------------------------------------
  typedef enum logic {
    GLOBAL_IDLE      = 1'b0,
    GLOBAL_STREAMING = 1'b1
  } global_state_t;

  global_state_t global_state_r;

  always_ff @(posedge clk_sys) begin
    if (!rst_n) begin
      global_state_r    <= GLOBAL_IDLE;
      streaming_mode_r  <= 1'b0;
      bypass_mode_r     <= 1'b0;
    end else begin
      case (global_state_r)

        GLOBAL_IDLE: begin
          // Espera comando de streaming/bypass desde la UART RX (CMD_STREAM = 0x03, CMD_BYPASS = 0x04)
          if (uart_rx_valid_s) begin
            if (uart_rx_cmd_s == CMD_STREAM) begin
              streaming_mode_r <= 1'b1;
              bypass_mode_r    <= 1'b0;
              global_state_r   <= GLOBAL_STREAMING;
            end else if (uart_rx_cmd_s == CMD_BYPASS) begin
              streaming_mode_r <= 1'b1;
              bypass_mode_r    <= 1'b1;
              global_state_r   <= GLOBAL_STREAMING;
            end
          end
        end

        GLOBAL_STREAMING: begin
          // Se mantiene en este estado de forma indefinida hasta que ocurra un reset fisico (rst_n)
        end

        default: global_state_r <= GLOBAL_IDLE;
      endcase
    end
  end

  //---------------------------------------------------------------------------
  // Logica de Indicadores LED (Activos Bajo)
  //---------------------------------------------------------------------------
  logic [24:0] heartbeat_cnt_r;

  always_ff @(posedge clk_sys) begin
    if (!rst_n) begin
      heartbeat_cnt_r <= '0;
    end else begin
      heartbeat_cnt_r <= heartbeat_cnt_r + 1'b1;
    end
  end

  // LED 0: Encendido si hay error de sincronismo UART RX
  assign o_leds_n[0] = !rx_sync_error_r;

  // LED 1: Encendido si está esperando comando (IDLE)
  assign o_leds_n[1] = !(global_state_r == GLOBAL_IDLE);

  // LED 2: Encendido si el modo de flujo está activo (streaming o bypass)
  assign o_leds_n[2] = !streaming_mode_r;

  // LED 3: Apagado si hay modo bypass activo (aviso visual de diagnostico)
  assign o_leds_n[3] = bypass_mode_r;

  // LED 4: Alerta de FIFO de salida llena
  assign o_leds_n[4] = !out_fifo_full_s;

  // LED 5: Latido de reloj (parpadeo a ~0.8 Hz)
  assign o_leds_n[5] = heartbeat_cnt_r[24];

endmodule : top_crossover

`default_nettype wire
