onerror {resume}
quietly WaveActivateNextPane {} 0
add wave -noupdate -divider {Reloj y Control}
add wave -noupdate -format Logic /crossover_engine_tb/clk_sys
add wave -noupdate -format Logic /crossover_engine_tb/rst_n
add wave -noupdate -format Logic /crossover_engine_tb/load_data
add wave -noupdate -format Logic /crossover_engine_tb/end_sim

add wave -noupdate -divider {Senal de Entrada (24-bit)}
add wave -noupdate -format Analog-Step -height 80 -max 8388607.0 -min -8388608.0 -radix decimal -color Gray /crossover_engine_tb/id_sample
add wave -noupdate -format Logic /crossover_engine_tb/ic_sample_valid

add wave -noupdate -divider {Woofer LPF (24-bit)}
add wave -noupdate -format Analog-Step -height 80 -max 8388607.0 -min -8388608.0 -radix decimal -color Cyan /crossover_engine_tb/out_lpf_F
add wave -noupdate -format Analog-Step -height 80 -max 8388607.0 -min -8388608.0 -radix decimal -color Blue /crossover_engine_tb/out_lpf_M

add wave -noupdate -divider {Tweeter HPF (24-bit)}
add wave -noupdate -format Analog-Step -height 80 -max 8388607.0 -min -8388608.0 -radix decimal -color Pink /crossover_engine_tb/out_hpf_F
add wave -noupdate -format Analog-Step -height 80 -max 8388607.0 -min -8388608.0 -radix decimal -color Red /crossover_engine_tb/out_hpf_M

add wave -noupdate -divider {Datapath Interno del Filtro}
add wave -noupdate -format Literal -radix symbolic /crossover_engine_tb/UUT/state_r
add wave -noupdate -format Literal -radix decimal /crossover_engine_tb/UUT/step_cnt_r
add wave -noupdate -format Literal -radix decimal /crossover_engine_tb/UUT/bq_idx_s
add wave -noupdate -format Literal -radix decimal /crossover_engine_tb/UUT/term_idx_s
add wave -noupdate -format Analog-Step -height 60 -max 8388607.0 -min -8388608.0 -radix decimal -color Gray /crossover_engine_tb/UUT/x_in_active_s
add wave -noupdate -format Analog-Step -height 60 -max 8388607.0 -min -8388608.0 -radix decimal -color Gray /crossover_engine_tb/UUT/mult_val_a_s
add wave -noupdate -format Literal -radix hex /crossover_engine_tb/UUT/mult_val_b_s
add wave -noupdate -format Literal -radix decimal /crossover_engine_tb/UUT/product_s
add wave -noupdate -format Literal -radix decimal /crossover_engine_tb/UUT/accum_r
add wave -noupdate -format Literal -radix decimal /crossover_engine_tb/UUT/accum_next_s
add wave -noupdate -format Analog-Step -height 60 -max 8388607.0 -min -8388608.0 -radix decimal -color White /crossover_engine_tb/UUT/y_shifted_s
add wave -noupdate -format Analog-Step -height 60 -max 8388607.0 -min -8388608.0 -radix decimal -color Green /crossover_engine_tb/UUT/y_saturada_s
add wave -noupdate -format Literal -radix decimal /crossover_engine_tb/UUT/state_reg_r
add wave -noupdate -format Literal -radix decimal /crossover_engine_tb/UUT/y_temp_r


add wave -noupdate -divider {Handshake y Validacion}
add wave -noupdate -format Logic /crossover_engine_tb/oc_output_valid
add wave -noupdate -format Literal -radix decimal /crossover_engine_tb/sample_cnt
add wave -noupdate -format Literal -radix decimal -color Yellow /crossover_engine_tb/error_cnt_lpf
add wave -noupdate -format Literal -radix decimal -color Yellow /crossover_engine_tb/error_cnt_hpf

TreeUpdate [SetDefaultTree]
WaveRestoreCursors {{Cursor 1} {0 ps} 0}
quietly wave cursor active 1
configure wave -namecolwidth 220
configure wave -valuecolwidth 120
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
WaveRestoreZoom {0 ps} {200000 ns}
