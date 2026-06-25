//=============================================================================
// Módulo    : crossover_pkg
// Archivo   : crossover_pkg.sv
// Proyecto  : Filtro Crossover IIR — Tang Nano 9K
// Autor     : Joan
// Fecha     : 2026-06-21
// Versión   : 1.0
//-----------------------------------------------------------------------------
// Descripción:
//   Paquete global que define las constantes, anchos de palabra y parámetros
//   comunes para todo el sistema del Crossover IIR.
//=============================================================================

package crossover_pkg;

  // Anchos de palabra de precisión
  localparam int DATA_WIDTH  = 24;  // Ancho de las muestras de audio
  localparam int COEFF_WIDTH = 40;  // Ancho de los coeficientes de filtro (Q4.36)
  
  // Posición de la coma binaria en los coeficientes Q4.36
  localparam int Q_FRAC_BITS = 36;

  // Ancho del acumulador (64 bits del producto + 8 bits de crecimiento para L1 y suma de 5 términos)
  localparam int ACCUM_WIDTH = 72;

  // Protocolo y Comandos UART
  localparam logic [7:0] UART_START_BYTE = 8'hAA;
  localparam logic [7:0] UART_END_BYTE   = 8'h55;
  localparam logic [7:0] CMD_START       = 8'h01;
  localparam logic [7:0] CMD_TRANSPARENT = 8'h02;
  localparam logic [7:0] CMD_STREAM      = 8'h03;
  localparam logic [7:0] CMD_BYPASS      = 8'h04;

  // Relojes del Sistema
  localparam int CLK_SYS_FREQ = 27_000_000; // 27 MHz Reloj Principal
  localparam int UART_BAUDRATE = 921_600;   // 921600 bps UART

endpackage : crossover_pkg
