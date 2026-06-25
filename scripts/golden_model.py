#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
golden_model.py
Modelo de simulacion sincrono del Crossover IIR.
Genera dos salidas:
  1. Calculo directo en coma flotante (doble precision) con coeficientes ideales.
  2. Punto fijo bit-exact (igual al hardware) con coeficientes Q4.36 de 40 bits.
Calcula el SQNR de la salida de punto fijo frente a la version ideal.
"""

import os
import numpy as np
from scipy import signal

def to_bin_str(val, bits):
    """
    Convierte un entero con signo a su representacion binaria en texto plano de N bits (complemento a dos).
    """
    if val < 0:
        val = (1 << bits) + val
    return f"{val:0{bits}b}"

def load_coeffs_bin_txt(filepath):
    """
    Carga los coeficientes en formato texto conteniendo cadenas binarias de 40 bits ('0' y '1').
    """
    coeffs = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            # Convertir de binario (cadenas de 0 y 1) a entero
            val = int(line, 2)
            # Manejo de signo (complemento a dos de 40 bits)
            if val >= (1 << 39):
                val = val - (1 << 40)
            coeffs.append(val)
    return coeffs

def load_stimulus_bin_txt(filepath):
    """
    Carga las muestras de estimulo (16 bits) desde su representacion binaria en texto.
    """
    samples = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            val = int(line, 2)
            # Manejo de signo (16 bits)
            if val >= (1 << 15):
                val = val - (1 << 16)
            samples.append(val)
    return np.array(samples, dtype=np.int16)

def apply_biquad_float(x, coeffs, state):
    """
    Aplica una seccion biquad (Forma Directa I) en coma flotante pura.
    coeffs: [b0, b1, b2, -a1, -a2] ideales
    state: [x[n-1], x[n-2], y[n-1], y[n-2]]
    """
    b0, b1, b2, m_a1, m_a2 = coeffs
    x1, x2, y1, y2 = state
    
    # Ecuacion en diferencias en coma flotante pura
    y = x*b0 + x1*b1 + x2*b2 + y1*m_a1 + y2*m_a2
    
    return y, [x, x1, y, y1]

def process_chain_float(samples_float, coeffs_cascade):
    """
    Filtra la senal a traves de la cascada de 2 biquads flotantes (4o orden total).
    """
    out_samples = []
    state1 = [0.0, 0.0, 0.0, 0.0]
    state2 = [0.0, 0.0, 0.0, 0.0]
    
    for s in samples_float:
        y1, state1 = apply_biquad_float(s, coeffs_cascade[0], state1)
        y2, state2 = apply_biquad_float(y1, coeffs_cascade[1], state2)
        out_samples.append(y2)
        
    return np.array(out_samples, dtype=np.float64)

def apply_biquad_fixed(x, coeffs, state):
    """
    Aplica una seccion biquad (Forma Directa I) de coma fija bit-exact.
    x: muestra de entrada de 24 bits con signo (extendida).
    coeffs: lista de 5 coeficientes de 40 bits (b0, b1, b2, -a1, -a2).
    state: registros de estado [x[n-1], x[n-2], y[n-1], y[n-2]] (todos de 24 bits con signo).
    """
    b0, b1, b2, m_a1, m_a2 = coeffs
    x1, x2, y1, y2 = state
    
    # Productos parciales de 64 bits con signo (24-bit * 40-bit = 64-bit)
    p0 = x * b0
    p1 = x1 * b1
    p2 = x2 * b2
    p3 = y1 * m_a1
    p4 = y2 * m_a2
    
    # Acumulacion de precision (72 bits en hardware)
    accum = p0 + p1 + p2 + p3 + p4
    
    # Desplazamiento a la derecha con signo de 36 bits (eliminacion de la fraccion Q4.36)
    y = accum >> 36
    
    # Saturacion a 24 bits con signo (rango [-2^23, 2^23 - 1])
    min_24b = -2**23
    max_24b = 2**23 - 1
    if y < min_24b:
        y = min_24b
    elif y > max_24b:
        y = max_24b
        
    return y, [x, x1, y, y1]

def process_chain_fixed(samples_16b, coeffs_cascade):
    """
    Filtra la senal a traves de la cascada de 2 biquads en coma fija (4o orden total).
    Las muestras de entrada de 16 bits se extienden primero a 24 bits (LShift 8).
    """
    out_samples = []
    state1 = [0, 0, 0, 0]
    state2 = [0, 0, 0, 0]
    
    for s in samples_16b:
        # Extension a 24 bits: {s[15:0], 8'b0}
        x = int(s) << 8
        y1, state1 = apply_biquad_fixed(x, coeffs_cascade[0], state1)
        y2, state2 = apply_biquad_fixed(y1, coeffs_cascade[1], state2)
        out_samples.append(y2)
        
    return np.array(out_samples, dtype=np.int32)

def calculate_sqnr(signal_ideal, signal_quant):
    """
    Calcula el SQNR (Signal-to-Quantization-Noise Ratio) en dB.
    """
    signal_power = np.sum(signal_ideal ** 2)
    noise_power = np.sum((signal_ideal - signal_quant) ** 2)
    if noise_power == 0:
        return float('inf')
    return 10 * np.log10(signal_power / noise_power)

def save_float_txt(samples, filepath):
    """
    Guarda las muestras en formato de punto flotante en texto plano (%f), una por linea.
    """
    with open(filepath, "w") as f:
        for val in samples:
            f.write(f"{val:.8f}\n")

def save_bin_txt_24b(samples, filepath):
    """
    Guarda las muestras de 24 bits con signo como cadenas binarias (0s y 1s) en texto plano, una por linea.
    """
    with open(filepath, "w") as f:
        for val in samples:
            f.write(to_bin_str(int(val), 24) + "\n")

def main():
    import sys
    # Parametros del sistema
    fs = 48000
    fc = 2000.0
    
    if len(sys.argv) > 1:
        try:
            fc = float(sys.argv[1])
        except ValueError:
            print(f"Error: Frecuencia de corte '{sys.argv[1]}' no es valida. Usando 2000.0 Hz.")
            
    coeff_lpf_path = "sim/data/coeff_lpf_48k.bin"
    coeff_hpf_path = "sim/data/coeff_hpf_48k.bin"
    stimulus_path = "sim/data/noise.bin"
    
    # Salidas del Golden Model
    out_lpf_float_path = "sim/data/golden_lpf_float.txt"
    out_hpf_float_path = "sim/data/golden_hpf_float.txt"
    out_lpf_fixed_path = "sim/data/golden_lpf_fixed.txt"
    out_hpf_fixed_path = "sim/data/golden_hpf_fixed.txt"
    
    if not os.path.exists(coeff_lpf_path) or not os.path.exists(coeff_hpf_path):
        print("Error: Ejecuta calc_coefficients.py primero para generar los coeficientes.")
        return
    if not os.path.exists(stimulus_path):
        print("Error: Ejecuta gen_stimulus.py primero para generar el estimulo (noise.bin).")
        return
        
    print("=" * 60)
    print(" EJECUCION DEL GOLDEN MODEL crossover IIR (LR4) @ 48kHz")
    print("=" * 60)
    
    # 1. Cargar datos de entrada
    coeffs_lpf_fixed_single = load_coeffs_bin_txt(coeff_lpf_path)
    coeffs_hpf_fixed_single = load_coeffs_bin_txt(coeff_hpf_path)
    
    coeffs_lpf_fixed_cascade = [coeffs_lpf_fixed_single, coeffs_lpf_fixed_single]
    coeffs_hpf_fixed_cascade = [coeffs_hpf_fixed_single, coeffs_hpf_fixed_single]
    
    input_data = load_stimulus_bin_txt(stimulus_path)
    print(f"Cargadas {len(input_data)} muestras desde {stimulus_path}")
    
    # 2. Disenar coeficientes flotantes ideales para la simulacion directa
    nyquist = fs / 2.0
    wn = fc / nyquist
    b_lpf, a_lpf = signal.butter(2, wn, btype='low')
    b_hpf, a_hpf = signal.butter(2, wn, btype='high')
    
    coeffs_lpf_ideal_single = [b_lpf[0], b_lpf[1], b_lpf[2], -a_lpf[1], -a_lpf[2]]
    coeffs_hpf_ideal_single = [b_hpf[0], b_hpf[1], b_hpf[2], -a_hpf[1], -a_hpf[2]]
    
    coeffs_lpf_ideal_cascade = [coeffs_lpf_ideal_single, coeffs_lpf_ideal_single]
    coeffs_hpf_ideal_cascade = [coeffs_hpf_ideal_single, coeffs_hpf_ideal_single]
    
    # 3. Preparar la entrada para el calculo directo (escala de 24 bits)
    input_data_float = input_data.astype(np.float64) * 256.0
    
    # 4. Procesar calculo directo (coma flotante ideal)
    print("Procesando Woofer LPF Flotante...")
    out_woofer_float = process_chain_float(input_data_float, coeffs_lpf_ideal_cascade)
    
    print("Procesando Tweeter HPF Flotante...")
    out_tweeter_float = process_chain_float(input_data_float, coeffs_hpf_ideal_cascade)
    
    # 5. Procesar punto fijo bit-exact
    print("Procesando Woofer LPF Punto Fijo...")
    out_woofer_fixed = process_chain_fixed(input_data, coeffs_lpf_fixed_cascade)
    
    print("Procesando Tweeter HPF Punto Fijo...")
    out_tweeter_fixed = process_chain_fixed(input_data, coeffs_hpf_fixed_cascade)
    
    # 6. Calcular SQNR
    sqnr_lpf = calculate_sqnr(out_woofer_float, out_woofer_fixed)
    sqnr_hpf = calculate_sqnr(out_tweeter_float, out_tweeter_fixed)
    
    print("-" * 60)
    print(f"SQNR Woofer LPF: {sqnr_lpf:.2f} dB")
    print(f"SQNR Tweeter HPF: {sqnr_hpf:.2f} dB")
    print("-" * 60)
    
    # 7. Guardar resultados
    save_float_txt(out_woofer_float, out_lpf_float_path)
    save_float_txt(out_tweeter_float, out_hpf_float_path)
    print(f"Salidas de calculo directo guardadas en:\n  - {out_lpf_float_path}\n  - {out_hpf_float_path}")
    
    save_bin_txt_24b(out_woofer_fixed, out_lpf_fixed_path)
    save_bin_txt_24b(out_tweeter_fixed, out_hpf_fixed_path)
    print(f"Salidas en punto fijo (texto binario) guardadas en:\n  - {out_lpf_fixed_path}\n  - {out_hpf_fixed_path}")

if __name__ == "__main__":
    main()
