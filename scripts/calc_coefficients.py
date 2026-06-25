#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calc_coefficients.py
Calcula los coeficientes para el crossover IIR Butterworth de 4o orden (LR4)
y realiza el analisis de bit growth para determinar el acumulador del hardware.
"""

import os
import numpy as np
from scipy import signal

def quantize_q4_36(val):
    """
    Cuantiza un valor float a coma fija Q4.36 (40 bits con signo).
    4 bits enteros (incluido signo) -> rango: [-8.0, 7.999999999985]
    36 bits fraccionarios.
    """
    scale = 2**36
    # Redondeo al entero mas cercano
    q_val = int(np.round(val * scale))
    
    # Saturacion a rango de 40-bit complemento a dos
    min_val = -2**39
    max_val = 2**39 - 1
    if q_val < min_val:
        q_val = min_val
    elif q_val > max_val:
        q_val = max_val
        
    return q_val

def to_hex_40b(val_int):
    """
    Convierte un entero de 40 bits en su representacion hexadecimal de 10 caracteres.
    Maneja valores negativos usando complemento a dos.
    """
    if val_int < 0:
        val_int = (1 << 40) + val_int
    return f"{val_int:010X}"

def to_bin_str(val, bits):
    """
    Convierte un entero con signo a su representacion binaria en texto plano de N bits (complemento a dos).
    """
    if val < 0:
        val = (1 << bits) + val
    return f"{val:0{bits}b}"

def write_coeff_bin(coeffs, filename):
    """
    Guarda los coeficientes cuantizados en un archivo de texto que contiene las representaciones
    binarias de 40 bits (0s y 1s), una por linea. Ideal para $readmemb en SystemVerilog.
    """
    with open(filename, "w") as f:
        for c in coeffs:
            q_val = quantize_q4_36(c)
            bin_str = to_bin_str(q_val, 40)
            f.write(bin_str + "\n")

def analyze_filter_stability(b_ideal, a_ideal, coeffs_fixed, fs, name):
    """
    Analiza la estabilidad y respuesta en frecuencia del filtro cuantizado frente al ideal.
    coeffs_fixed: [b0, b1, b2, -a1, -a2] cuantizados (enteros en escala 2^36).
    """
    scale = 2**36
    # Des-cuantizar los coeficientes para obtener los valores reales implementados en hardware
    b_quant = np.array([coeffs_fixed[0], coeffs_fixed[1], coeffs_fixed[2]], dtype=float) / scale
    # Recordar que guardamos -a1 y -a2, por lo tanto a1 = -coeffs_fixed[3] y a2 = -coeffs_fixed[4]
    a_quant = np.array([1.0, -coeffs_fixed[3] / scale, -coeffs_fixed[4] / scale], dtype=float)
    
    # 1. Comprobar estabilidad por los polos del filtro de segundo orden
    # El denominador es z^2 + a1*z + a2 = 0
    poles_ideal = np.roots(a_ideal)
    poles_quant = np.roots(a_quant)
    
    max_pole_ideal = np.max(np.abs(poles_ideal))
    max_pole_quant = np.max(np.abs(poles_quant))
    
    stable_ideal = max_pole_ideal < 1.0
    stable_quant = max_pole_quant < 1.0
    
    print(f"  [Estabilidad {name.upper()}]")
    print(f"    Polos Ideales: Max Radio = {max_pole_ideal:.8f} (Estable: {stable_ideal})")
    print(f"    Polos Cuantizados: Max Radio = {max_pole_quant:.8f} (Estable: {stable_quant})")
    if not stable_quant:
        print(f"    ALERTA: El filtro cuantizado {name.upper()} es INESTABLE.")
        
    # 2. Calcular respuesta en frecuencia
    w, h_ideal = signal.freqz(b_ideal, a_ideal, worN=8000)
    w, h_quant = signal.freqz(b_quant, a_quant, worN=8000)
    
    # Diferencia de magnitud en dB (evitando log de cero)
    mag_ideal = 20 * np.log10(np.abs(h_ideal) + 1e-15)
    mag_quant = 20 * np.log10(np.abs(h_quant) + 1e-15)
    mag_diff = np.abs(mag_ideal - mag_quant)
    
    # Diferencia de fase en grados
    phase_ideal = np.unwrap(np.angle(h_ideal)) * (180.0 / np.pi)
    phase_quant = np.unwrap(np.angle(h_quant)) * (180.0 / np.pi)
    phase_diff = np.abs(phase_ideal - phase_quant)
    
    print(f"    Diferencia Magnitud Maxima: {np.max(mag_diff):.6e} dB")
    print(f"    Diferencia Magnitud Media: {np.mean(mag_diff):.6e} dB")
    print(f"    Diferencia Fase Maxima: {np.max(phase_diff):.6f} grados")
    print(f"    Diferencia Fase Media: {np.mean(phase_diff):.6f} grados")
    return stable_quant

def main():
    import sys
    # Parametros del sistema
    fs_list = [48000]
    fc = 2000.0  # Frecuencia de corte por defecto: 2 kHz
    
    if len(sys.argv) > 1:
        try:
            fc = float(sys.argv[1])
            if fc <= 0 or fc >= 24000:
                print(f"Error: Frecuencia de corte fc={fc} Hz fuera de rango (debe ser > 0 y < 24000).")
                sys.exit(1)
        except ValueError:
            print(f"Error: Frecuencia de corte '{sys.argv[1]}' no es valida.")
            sys.exit(1)
            
    print("=" * 60)
    print(" CALCULO DE COEFICIENTES crossover IIR (LR4)")
    print(f" Frecuencia de corte (Fc): {fc} Hz")
    print("=" * 60)
    
    # Creamos directorio para guardar coeficientes si no existe
    os.makedirs("sim/data", exist_ok=True)
    
    for fs in fs_list:
        print(f"\n--- Procesando Fs = {fs} Hz ---")
        
        # Un crossover Linkwitz-Riley de 4o orden (LR4) se compone de
        # dos filtros Butterworth de 2o orden identicos en cascada.
        # Disenamos un Butterworth de 2o orden estandar.
        nyquist = fs / 2.0
        wn = fc / nyquist
        
        # Filtro LPF (2o orden Butterworth)
        b_lpf, a_lpf = signal.butter(2, wn, btype='low')
        # Filtro HPF (2o orden Butterworth)
        b_hpf, a_hpf = signal.butter(2, wn, btype='high')
        
        # En la estructura de hardware (Forma Directa I), usaremos la suma para todo:
        # y[n] = b0*x[n] + b1*x[n-1] + b2*x[n-2] + (-a1)*y[n-1] + (-a2)*y[n-2]
        # Por lo tanto, invertimos el signo de a1 y a2 para guardarlos directamente.
        coeffs_lpf = [b_lpf[0], b_lpf[1], b_lpf[2], -a_lpf[1], -a_lpf[2]]
        coeffs_hpf = [b_hpf[0], b_hpf[1], b_hpf[2], -a_hpf[1], -a_hpf[2]]
        
        # Analizar ganancia y Bit Growth
        sys_lpf = signal.TransferFunction(b_lpf, a_lpf, dt=1.0/fs)
        t, y_imp = signal.dimpulse(sys_lpf, n=1000)
        l1_norm_lpf = np.sum(np.abs(y_imp[0]))
        
        sys_hpf = signal.TransferFunction(b_hpf, a_hpf, dt=1.0/fs)
        t, y_imp_h = signal.dimpulse(sys_hpf, n=1000)
        l1_norm_hpf = np.sum(np.abs(y_imp_h[0]))
        
        worst_l1 = max(l1_norm_lpf, l1_norm_hpf)
        print(f"Norma L1 LPF (Cota superior de ganancia temporal): {l1_norm_lpf:.4f}")
        print(f"Norma L1 HPF (Cota superior de ganancia temporal): {l1_norm_hpf:.4f}")
        
        # Bit growth necesario: log2(worst_l1)
        bit_growth = np.ceil(np.log2(worst_l1))
        # Adicionalmente, sumamos 5 productos en el acumulador de biquad,
        # lo que anade log2(5) ~ 2.32 -> 3 bits mas de crecimiento de acumulador.
        accum_bits = 64 + int(bit_growth) + 3
        
        print(f"Crecimiento de bits por ganancia del filtro: +{int(bit_growth)} bits")
        print(f"Crecimiento de bits por acumulacion (5 terminos): +3 bits")
        print(f"Ancho del acumulador recomendado: {accum_bits} bits")
        
        # Cuantizacion de coeficientes
        q_coeffs_lpf = [quantize_q4_36(c) for c in coeffs_lpf]
        q_coeffs_hpf = [quantize_q4_36(c) for c in coeffs_hpf]
        
        # Estabilidad
        lpf_stable = analyze_filter_stability(b_lpf, a_lpf, q_coeffs_lpf, fs, "lpf")
        hpf_stable = analyze_filter_stability(b_hpf, a_hpf, q_coeffs_hpf, fs, "hpf")
        
        # Guardar coeficientes
        suffix = "48k"
        
        # 1. Guardar en formato binario de texto (.bin) de 40 bits con signo
        write_coeff_bin(coeffs_lpf, f"sim/data/coeff_lpf_{suffix}.bin")
        write_coeff_bin(coeffs_hpf, f"sim/data/coeff_hpf_{suffix}.bin")
        print(f"Guardados archivos binarios coeff_lpf_{suffix}.bin y coeff_hpf_{suffix}.bin (texto binario)")
        
        # 2. Mantener la exportacion de texto hexadecimal (.txt) para retrocompatibilidad
        for name, coeffs in [("lpf", coeffs_lpf), ("hpf", coeffs_hpf)]:
            filename = f"sim/data/coeff_{name}_{suffix}.txt"
            with open(filename, "w") as f:
                f.write(f"// Coeficientes para Filtro {name.upper()} @ {fs}Hz (Fc = {fc}Hz)\n")
                f.write(f"// Formato: Q4.36 (40 bits). b0, b1, b2, -a1, -a2\n")
                for c in coeffs:
                    q_val = quantize_q4_36(c)
                    hex_str = to_hex_40b(q_val)
                    f.write(f"{hex_str}\n")
            print(f"Guardado {filename} (Texto Hex)")
            
        if not lpf_stable or not hpf_stable:
            print("ERROR: Uno o ambos filtros cuantizados son INESTABLES.")
            sys.exit(2)

if __name__ == "__main__":
    main()
