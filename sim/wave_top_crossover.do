onerror {resume}
quietly WaveActivateNextPane {} 0
add wave -noupdate -divider {Reloj y Reset}
add wave -noupdate -format Logic /top_crossover_tb/clk_sys
add wave -noupdate -format Logic /top_crossover_tb/rst_n

add wave -noupdate -divider {Interfaces Fisicas (UART & LEDs)}
add wave -noupdate -format Logic -color Yellow /top_crossover_tb/uart_rxd
add wave -noupdate -format Logic -color Orange /top_crossover_tb/uart_txd
add wave -noupdate -format Literal -radix binary /top_crossover_tb/leds_n

add wave -noupdate -divider {FSM de Control Global}
add wave -noupdate -format Literal -radix symbolic /top_crossover_tb/uut/global_state_r
add wave -noupdate -format Logic /top_crossover_tb/uut/streaming_mode_r
add wave -noupdate -format Logic /top_crossover_tb/uut/bypass_mode_r

add wave -noupdate -divider {UART RX Decoder (Encuadre)}
add wave -noupdate -format Literal -radix symbolic /top_crossover_tb/uut/u_uart_ctrl/rx_state_r
add wave -noupdate -format Logic -color Red /top_crossover_tb/uut/rx_sync_error_r
add wave -noupdate -format Literal -radix decimal /top_crossover_tb/uut/rx_bad_bytes_cnt_r

add wave -noupdate -divider {DSP Input (24-bit)}
add wave -noupdate -format Analog-Step -height 80 -max 8388607.0 -min -8388608.0 -radix decimal -color Gray /top_crossover_tb/uut/dsp_input_sample_s
add wave -noupdate -format Logic /top_crossover_tb/uut/dsp_input_valid_s

add wave -noupdate -divider {DSP Crossover Outputs}
add wave -noupdate -format Analog-Step -height 80 -max 8388607.0 -min -8388608.0 -radix decimal -color Cyan /top_crossover_tb/uut/woofer_sample_s
add wave -noupdate -format Analog-Step -height 80 -max 8388607.0 -min -8388608.0 -radix decimal -color Pink /top_crossover_tb/uut/tweeter_sample_s
add wave -noupdate -format Logic /top_crossover_tb/uut/engine_output_valid_s

add wave -noupdate -divider {Datapath Interno del Filtro}
add wave -noupdate -format Literal -radix symbolic /top_crossover_tb/uut/u_crossover_engine/state_r
add wave -noupdate -format Literal -radix decimal /top_crossover_tb/uut/u_crossover_engine/step_cnt_r
add wave -noupdate -format Literal -radix decimal /top_crossover_tb/uut/u_crossover_engine/bq_idx_s
add wave -noupdate -format Literal -radix decimal /top_crossover_tb/uut/u_crossover_engine/term_idx_s
add wave -noupdate -format Analog-Step -height 60 -max 8388607.0 -min -8388608.0 -radix decimal -color Gray /top_crossover_tb/uut/u_crossover_engine/x_in_active_s
add wave -noupdate -format Analog-Step -height 60 -max 8388607.0 -min -8388608.0 -radix decimal -color Gray /top_crossover_tb/uut/u_crossover_engine/mult_val_a_s
add wave -noupdate -format Literal -radix hex /top_crossover_tb/uut/u_crossover_engine/mult_val_b_s
add wave -noupdate -format Literal -radix decimal /top_crossover_tb/uut/u_crossover_engine/product_s
add wave -noupdate -format Literal -radix decimal /top_crossover_tb/uut/u_crossover_engine/accum_r
add wave -noupdate -format Literal -radix decimal /top_crossover_tb/uut/u_crossover_engine/accum_next_s
add wave -noupdate -format Analog-Step -height 60 -max 8388607.0 -min -8388608.0 -radix decimal -color White /top_crossover_tb/uut/u_crossover_engine/y_shifted_s
add wave -noupdate -format Analog-Step -height 60 -max 8388607.0 -min -8388608.0 -radix decimal -color Green /top_crossover_tb/uut/u_crossover_engine/y_saturada_s
add wave -noupdate -format Literal -radix decimal /top_crossover_tb/uut/u_crossover_engine/state_reg_r
add wave -noupdate -format Literal -radix decimal /top_crossover_tb/uut/u_crossover_engine/y_temp_r


add wave -noupdate -divider {Comparacion Analogica (Golden vs RTL)}
add wave -noupdate -format Analog-Step -height 80 -max 8388607.0 -min -8388608.0 -radix decimal -color Cyan /top_crossover_tb/out_lpf_F
add wave -noupdate -format Analog-Step -height 80 -max 8388607.0 -min -8388608.0 -radix decimal -color Blue /top_crossover_tb/out_lpf_M
add wave -noupdate -format Analog-Step -height 80 -max 8388607.0 -min -8388608.0 -radix decimal -color Pink /top_crossover_tb/out_hpf_F
add wave -noupdate -format Analog-Step -height 80 -max 8388607.0 -min -8388608.0 -radix decimal -color Red /top_crossover_tb/out_hpf_M

add wave -noupdate -divider {FIFO de Salida}
add wave -noupdate -format Literal -radix decimal /top_crossover_tb/uut/out_wr_ptr_r
add wave -noupdate -format Literal -radix decimal /top_crossover_tb/uut/out_rd_ptr_r
add wave -noupdate -format Logic /top_crossover_tb/uut/out_fifo_empty_s
add wave -noupdate -format Logic /top_crossover_tb/uut/out_fifo_full_s

add wave -noupdate -divider {UART TX Encoder}
add wave -noupdate -format Literal -radix symbolic /top_crossover_tb/uut/u_uart_ctrl/tx_state_r
add wave -noupdate -format Logic /top_crossover_tb/uut/u_uart_ctrl/oc_tx_busy
add wave -noupdate -format Logic /top_crossover_tb/uut/u_uart_ctrl/ic_tx_valid

add wave -noupdate -divider {Validacion del Testbench}
add wave -noupdate -format Literal -radix decimal /top_crossover_tb/samples_sent
add wave -noupdate -format Literal -radix decimal /top_crossover_tb/samples_received
add wave -noupdate -format Literal -radix decimal -color Red /top_crossover_tb/error_cnt_lpf
add wave -noupdate -format Literal -radix decimal -color Red /top_crossover_tb/error_cnt_hpf

TreeUpdate [SetDefaultTree]
WaveRestoreCursors {{Cursor 1} {0 ps} 0}
quietly wave cursor active 1
configure wave -namecolwidth 250
configure wave -valuecolwidth 100
configure wave -justifyvalue left
configure wave -signalnamewidth 1
configure wave -snapdistance 10
configure wave -datasetprefix 0
configure wave -rowmargin 4
configure wave -childrowmargin 2
configure wave -gridoffset 0
configure wave -gridperiod 1
configure wave -griddelta 40
configure wave -timeline 0
configure wave -timelineunits ns
update
WaveRestoreZoom {0 ps} {100000000 ps}
