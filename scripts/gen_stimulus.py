#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_stimulus.py
Genera ruido blanco uniforme en formato binario PCM de 16 bits con signo,
su correspondiente representacion en bytes para el simulador SD y 
las muestras hexadecimales de 16 bits para el testbench unitario.
Disenado para generar exactamente 4096 muestras (16 sectores de la SD).
"""

import os
import numpy as np

def main():
    import sys
    # Valor por defecto
    num_samples = 240128
    if len(sys.argv) > 1:
        try:
            num_samples = int(sys.argv[1])
        except ValueError:
            pass
    
    # Amplitud al 18% para evitar saturacion por ganancia del filtro (norma L1 de 3.32): 0.18 * 32767 = 5898
    amplitude = 0.18 * 32767
    
    print(f"Generando exactamente {num_samples} muestras de ruido blanco uniforme (16 sectores SD)...")
    
    # Ruido blanco uniforme en [-1, 1]
    noise = np.random.uniform(-1.0, 1.0, num_samples)
    
    # Escalar a 16 bits con signo
    noise_scaled = (noise * amplitude).astype(np.int16)
    
    # Crear directorio si no existe
    os.makedirs("sim/data", exist_ok=True)
    
    def to_bin_str(val, bits):
        if val < 0:
            val = (1 << bits) + val
        return f"{val:0{bits}b}"
    
    # 1. Guardar archivo en formato texto binario (0s y 1s, uno por linea) en noise.bin
    output_bin = "sim/data/noise.bin"
    with open(output_bin, "w") as f:
        for val in noise_scaled:
            f.write(to_bin_str(int(val), 16) + "\n")
    print(f"Estimulo binario en texto (0s y 1s) generado en: {output_bin}")
    
    # 3. Guardar archivo en formato texto hexadecimal (bytes Little Endian) para el mock de la SD
    output_hex = "sim/data/noise_hex.txt"
    with open(output_hex, "w") as f:
        f.write("// Ruido blanco uniforme en bytes (Little Endian). Formato: LSB, MSB\n")
        for val in noise_scaled:
            val_us = int(val) & 0xFFFF
            lsb = val_us & 0xFF
            msb = (val_us >> 8) & 0xFF
            f.write(f"{lsb:02X}\n")
            f.write(f"{msb:02X}\n")
            
    print(f"Estimulo hexadecimal para simulador SD generado en: {output_hex}")
    
    # 4. Guardar archivo de estimulo de muestras hex de 16 bits para crossover_engine_tb
    output_stimulus_hex = "sim/data/stimulus_hex.txt"
    with open(output_stimulus_hex, "w") as f:
        for val in noise_scaled:
            val_us = int(val) & 0xFFFF
            f.write(f"{val_us:04X}\n")
            
    print(f"Estimulo de muestras hex para testbench unitario generado en: {output_stimulus_hex}")

if __name__ == "__main__":
    main()
