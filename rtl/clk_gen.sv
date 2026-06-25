//=============================================================================
// Módulo    : clk_gen
// Archivo   : clk_gen.sv
// Proyecto  : Filtro Crossover IIR — Tang Nano 9K
// Autor     : Joan
// Fecha     : 2026-06-21
// Versión   : 1.0
//-----------------------------------------------------------------------------
// Descripción:
//   Generador de habilitaciones de reloj (clock enables) síncronos a clk_sys
//   usando acumuladores de fase (DDS) para Fs (48 kHz / 44.1 kHz) y BCK.
//
// Parámetros:
//   Ninguno (configurado vía imports o señales)
//
// Interfaces:
//   clk_sys        : Reloj del sistema (27 MHz)
//   rst_n          : Reset activo bajo (síncrono)
//   ic_fs_select   : Selección de Fs: 0 = 48 kHz, 1 = 44.1 kHz
//   oc_ce_sample   : Enable síncrono a frecuencia de muestreo Fs
//   oc_ce_bck      : Enable síncrono a BCK (64 * Fs)
//=============================================================================

`default_nettype none

module clk_gen 
  import crossover_pkg::*;
(
  input  var logic clk_sys,
  input  var logic rst_n,
  input  var logic ic_fs_select, // 0 = 48 kHz, 1 = 44.1 kHz
  output var logic oc_ce_sample,
  output var logic oc_ce_bck
);

  // Pasos de fase DDS para 32 bits a partir de Fsys = 27 MHz
  // phase_step = (Fs * 2^32) / 27,000,000
  localparam logic [31:0] STEP_48K_SAMPLE = 32'd7632618;  // Fs = 48000 Hz
  localparam logic [31:0] STEP_44K_SAMPLE = 32'd7012493;  // Fs = 44100 Hz
  
  localparam logic [31:0] STEP_48K_BCK    = 32'd488487552; // BCK = 3.072 MHz (64 * 48k)
  localparam logic [31:0] STEP_44K_BCK    = 32'd448799552; // BCK = 2.8224 MHz (64 * 44.1k)

  // Registros de fase DDS
  logic [31:0] sample_phase_r;
  logic [31:0] bck_phase_r;

  // Pasos de fase activos combinacionales
  logic [31:0] active_step_sample_s;
  logic [31:0] active_step_bck_s;

  // Selección del paso de fase según ic_fs_select
  always_comb begin
    if (ic_fs_select) begin
      active_step_sample_s = STEP_44K_SAMPLE;
      active_step_bck_s    = STEP_44K_BCK;
    end else begin
      active_step_sample_s = STEP_48K_SAMPLE;
      active_step_bck_s    = STEP_48K_BCK;
    end
  end

  // Acumuladores DDS síncronos
  always_ff @(posedge clk_sys) begin
    if (!rst_n) begin
      sample_phase_r <= 32'd0;
      bck_phase_r    <= 32'd0;
      oc_ce_sample   <= 1'b0;
      oc_ce_bck      <= 1'b0;
    end else begin
      // Suma y detección de desbordamiento (overflow del acumulador)
      // El bit de carry de la suma es equivalente a que ocurra un desbordamiento.
      // Comparamos el valor acumulado con el valor futuro para detectar el overflow.
      logic [32:0] sample_sum_s;
      logic [32:0] bck_sum_s;

      sample_sum_s = {1'b0, sample_phase_r} + {1'b0, active_step_sample_s};
      bck_sum_s    = {1'b0, bck_phase_r}    + {1'b0, active_step_bck_s};

      sample_phase_r <= sample_sum_s[31:0];
      bck_phase_r    <= bck_sum_s[31:0];

      // La habilitación se activa solo en el ciclo donde se produce el desbordamiento
      oc_ce_sample   <= sample_sum_s[32];
      oc_ce_bck      <= bck_sum_s[32];
    end
  end

endmodule : clk_gen

`default_nettype wire
