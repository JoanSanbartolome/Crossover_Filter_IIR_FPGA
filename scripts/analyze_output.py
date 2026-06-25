#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_output.py
Verifica la bit-exactitud muestra a muestra entre la salida del RTL de la FPGA,
el Golden Model y la ultima captura de datos desde la UART.
Adicionalmente, realiza el analisis espectral Welch PSD y grafica las respuestas.
"""

import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import signal

def read_bin_txt_file(filepath):
    """
    Lee un archivo de texto con muestras representadas en binario (0s y 1s) de 24 bits con signo y las convierte a enteros.
    """
    vals = []
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip().replace('\x00', '')
            if not line or line.startswith("//"):
                continue
            if not all(c in '01' for c in line):
                continue
            # Convertir binario de 24 bits a entero con signo
            val = int(line, 2)
            # Complemento a dos de 24 bits
            if val >= (1 << 23):
                val = val - (1 << 24)
            vals.append(val)
    return np.array(vals, dtype=np.int32)

def read_hex_txt_file(filepath):
    """
    Lee un archivo de texto con muestras representadas en hexadecimal (24 bits con signo) y las convierte a enteros.
    """
    vals = []
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip().replace('\x00', '')
            if not line or line.startswith("//"):
                continue
            if not all(c in '0123456789ABCDEFabcdef' for c in line):
                continue
            # Convertir hexadecimal de 24 bits a entero con signo
            val = int(line, 16)
            # Complemento a dos de 24 bits
            if val >= (1 << 23):
                val = val - (1 << 24)
            vals.append(val)
    return np.array(vals, dtype=np.int32)

def read_bin_txt_16b_file(filepath):
    """
    Lee un archivo de texto con muestras representadas en binario (0s y 1s) de 16 bits con signo y las convierte a enteros.
    """
    vals = []
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip().replace('\x00', '')
            if not line or line.startswith("//"):
                continue
            if not all(c in '01' for c in line):
                continue
            val = int(line, 2)
            if val >= (1 << 15):
                val = val - (1 << 16)
            vals.append(val)
    return np.array(vals, dtype=np.int16)

def load_coeffs(filepath):
    """
    Carga los coeficientes en formato binario de texto Q4.36 y los convierte a flotantes.
    """
    coeffs = []
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip().replace('\x00', '')
            if not line or line.startswith("//"):
                continue
            if not all(c in '01' for c in line):
                continue
            val = int(line, 2)
            if val >= (1 << 39):
                val = val - (1 << 40)
            # Convertir de Q4.36 a float
            coeffs.append(val / (2**36))
    return coeffs


def find_latest_captures(capture_dir="captures"):
    """
    Busca los archivos de captura UART mas recientes para LPF y HPF.
    Retorna: (lpf_path, hpf_path, timestamp) o (None, None, None).
    """
    if not os.path.isdir(capture_dir):
        return None, None, None
    
    lpf_files = [f for f in os.listdir(capture_dir) if f.startswith("capture_") and f.endswith("_lpf.txt")]
    hpf_files = [f for f in os.listdir(capture_dir) if f.startswith("capture_") and f.endswith("_hpf.txt")]
    
    if not lpf_files or not hpf_files:
        return None, None, None
    
    # Ordenar alfabeticamente para obtener la captura mas reciente por fecha/hora
    latest_lpf = sorted(lpf_files)[-1]
    
    # Extraer timestamp del nombre: capture_YYYYMMDD_HHMMSS_lpf.txt
    parts = latest_lpf.split("_")
    if len(parts) >= 3:
        timestamp = f"{parts[1]}_{parts[2]}"
    else:
        timestamp = "unknown"
        
    corresponding_hpf = f"capture_{timestamp}_hpf.txt"
    lpf_path = os.path.join(capture_dir, latest_lpf)
    hpf_path = os.path.join(capture_dir, corresponding_hpf)
    
    if not os.path.exists(hpf_path):
        # Fallback por si los nombres de archivo difieren
        latest_hpf = sorted(hpf_files)[-1]
        hpf_path = os.path.join(capture_dir, latest_hpf)
        print(f"  [Advertencia] No se encontro HPF con timestamp exacto {timestamp}. Usando el mas reciente: {latest_hpf}")
        
    return lpf_path, hpf_path, timestamp

def align_signals(ref, sig, max_lag=2000, search_len=10000):
    """
    Encuentra la alineacion optima de 'sig' respecto a 'ref' minimizando el MSE.
    Retorna: (sig_aligned, ref_aligned, best_lag)
    """
    n_ref = len(ref)
    n_sig = len(sig)
    
    len_fit = min(search_len, n_ref, n_sig)
    if len_fit < 2 * max_lag:
        max_lag = len_fit // 4
        
    if len_fit < 100 or max_lag <= 0:
        return sig, ref, 0
        
    # Extraer segmentos y normalizar para evitar bias de DC/amplitud durante la alineacion
    ref_sub = ref[:len_fit].astype(np.float64)
    sig_sub = sig[:len_fit].astype(np.float64)
    
    ref_sub -= np.mean(ref_sub)
    sig_sub -= np.mean(sig_sub)
    
    # Usar ventana central
    win_size = len_fit - 2 * max_lag
    ref_win = ref_sub[max_lag : max_lag + win_size]
    
    lags = np.arange(-max_lag, max_lag + 1)
    min_mse = float('inf')
    best_lag = 0
    
    for lag in lags:
        sig_win = sig_sub[max_lag + lag : max_lag + lag + win_size]
        mse = np.mean((ref_win - sig_win) ** 2)
        if mse < min_mse:
            min_mse = mse
            best_lag = lag
            
    # Alinear senales reales
    if best_lag > 0:
        # 'sig' esta adelantada respecto a 'ref', recortar el inicio de 'sig'
        sig_aligned = sig[best_lag:]
        ref_aligned = ref[:]
    elif best_lag < 0:
        # 'sig' esta retrasada respecto a 'ref' (debemos recortar 'ref')
        sig_aligned = sig[:]
        ref_aligned = ref[-best_lag:]
    else:
        sig_aligned = sig[:]
        ref_aligned = ref[:]
        
    # Ajustar a la misma longitud minima
    min_len = min(len(sig_aligned), len(ref_aligned))
    return sig_aligned[:min_len], ref_aligned[:min_len], best_lag

def compute_metrics(ref, sig):
    """
    Calcula metricas de error y similitud entre dos senales.
    """
    ref_f = ref.astype(np.float64)
    sig_f = sig.astype(np.float64)
    
    diff = sig_f - ref_f
    max_err = np.max(np.abs(diff))
    mae = np.mean(np.abs(diff))
    mse = np.mean(diff ** 2)
    rmse = np.sqrt(mse)
    
    # Correlacion de Pearson
    std_ref = np.std(ref_f)
    std_sig = np.std(sig_f)
    if std_ref == 0.0 or std_sig == 0.0:
        r = 0.0
    else:
        r = np.corrcoef(ref_f, sig_f)[0, 1]
        
    # SNR (dB)
    ref_power = np.mean(ref_f ** 2)
    if mse == 0.0:
        snr = float('inf')
    else:
        snr = 10 * np.log10(ref_power / mse)
        
    return {
        "max_err": max_err,
        "mae": mae,
        "mse": mse,
        "rmse": rmse,
        "r": r,
        "snr": snr,
        "len": len(ref)
    }

def main():
    # 0. Comprobar si el testbench reporto errores en el log del simulador
    transcript_path = "sim/transcript.log"
    if os.path.exists(transcript_path):
        has_errors = False
        error_lines = []
        with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "[ERROR LPF]" in line or "[ERROR HPF]" in line or "[FALLO]" in line:
                    has_errors = True
                    error_lines.append(line.strip())
        
        # Asercion para abortar si el testbench fallo
        assert not has_errors, (
            f"El testbench reporto errores en {transcript_path}. "
            "No tiene sentido realizar el analisis de salidas.\n"
            "Errores detectados:\n" + "\n".join(error_lines[:5])
        )

    # Rutas por defecto
    golden_lpf_path = "sim/data/golden_lpf_fixed.txt"
    golden_hpf_path = "sim/data/golden_hpf_fixed.txt"
    rtl_lpf_path = "sim/data/output_lpf_rtl.txt"
    rtl_hpf_path = "sim/data/output_hpf_rtl.txt"
    
    print("=" * 70)
    print(" ANALISIS Y VALIDACION EXHAUSTIVA DE RESULTADOS (GOLDEN VS. RTL VS. UART)")
    print("=" * 70)
    
    # Comprobar si archivos de simulacion existen
    files_ok = True
    for p in [golden_lpf_path, golden_hpf_path, rtl_lpf_path, rtl_hpf_path]:
        if not os.path.exists(p):
            print(f"Error: No se encuentra el archivo {p}")
            files_ok = False
            
    if not files_ok:
        print("Asegurate de ejecutar la simulacion en ModelSim y exportar las salidas.")
        return
        
    # Cargar datos de simulacion y modelo golden
    g_lpf = read_bin_txt_file(golden_lpf_path)
    g_hpf = read_bin_txt_file(golden_hpf_path)
    r_lpf = read_bin_txt_file(rtl_lpf_path)
    r_hpf = read_bin_txt_file(rtl_hpf_path)
    
    print(f"Muestras de simulacion cargadas:")
    print(f"  Golden: LPF ({len(g_lpf)}), HPF ({len(g_hpf)})")
    print(f"  RTL:    LPF ({len(r_lpf)}), HPF ({len(r_hpf)})")
    
    # Cargar ultima captura UART
    print("\nBuscando capturas UART mas recientes...")
    u_lpf_path, u_hpf_path, uart_timestamp = find_latest_captures("captures")
    
    has_uart = False
    if u_lpf_path and u_hpf_path:
        try:
            u_lpf = read_hex_txt_file(u_lpf_path)
            u_hpf = read_hex_txt_file(u_hpf_path)
            print(f"  Captura UART encontrada (Timestamp: {uart_timestamp}):")
            print(f"    LPF: {u_lpf_path} ({len(u_lpf)} muestras)")
            print(f"    HPF: {u_hpf_path} ({len(u_hpf)} muestras)")
            if len(u_lpf) < 128 or len(u_hpf) < 128:
                print("  [Advertencia] La captura UART es demasiado corta (menor de 128 muestras). Se descarta para el analisis de comparacion.")
                has_uart = False
            else:
                has_uart = True
        except Exception as e:
            print(f"  [Error] No se pudieron leer los archivos UART: {e}")
    else:
        print("  [Advertencia] No se encontraron archivos de captura UART en la carpeta 'captures/'.")
        
    # --- COMPARACIONES DE BIT-EXACTITUD Y ALINEACION ---
    # 1. Woofer (LPF)
    print("\n" + "-" * 50)
    print(" ANALISIS CANAL PASO BAJO (LPF - WOOFER)")
    print("-" * 50)
    
    # RTL vs Golden (LPF)
    n_samples_rtl_lpf = min(len(g_lpf), len(r_lpf))
    metrics_rtl_g_lpf = compute_metrics(g_lpf[:n_samples_rtl_lpf], r_lpf[:n_samples_rtl_lpf])
    print("1. RTL vs. GOLDEN MODEL:")
    print(f"   - Error absoluto maximo: {metrics_rtl_g_lpf['max_err']}")
    print(f"   - SNR: {metrics_rtl_g_lpf['snr']:.2f} dB")
    print(f"   - Correlacion (r): {metrics_rtl_g_lpf['r']:.6f}")
    if metrics_rtl_g_lpf['max_err'] == 0:
        print("   [ESTADO] 100% BIT-EXACTO!")
    else:
        print("   [ESTADO] Diferencias detectadas en la simulacion.")
        
    # UART LPF comparado
    metrics_uart_g_lpf = None
    metrics_uart_rtl_lpf = None
    u_lpf_aligned_g = None
    g_lpf_aligned = None
    lag_uart_lpf = 0
    
    if has_uart:
        print("\nAlineando senales UART LPF con el Golden Model...")
        u_lpf_aligned_g, g_lpf_aligned, lag_uart_lpf = align_signals(g_lpf, u_lpf)
        metrics_uart_g_lpf = compute_metrics(g_lpf_aligned, u_lpf_aligned_g)
        
        # Alinear UART con RTL (generalmente identico a Golden)
        u_lpf_aligned_r, r_lpf_aligned, _ = align_signals(r_lpf, u_lpf)
        metrics_uart_rtl_lpf = compute_metrics(r_lpf_aligned, u_lpf_aligned_r)
        
        print("\n2. UART vs. GOLDEN MODEL (Alineados):")
        print(f"   - Desfase optimo: {lag_uart_lpf} muestras")
        print(f"   - Error absoluto maximo: {metrics_uart_g_lpf['max_err']}")
        print(f"   - MAE: {metrics_uart_g_lpf['mae']:.2f} | RMSE: {metrics_uart_g_lpf['rmse']:.2f}")
        print(f"   - SNR: {metrics_uart_g_lpf['snr']:.2f} dB")
        print(f"   - Correlacion (r): {metrics_uart_g_lpf['r']:.6f}")
        
        print("\n3. UART vs. RTL SIMULACION (Alineados):")
        print(f"   - Error absoluto maximo: {metrics_uart_rtl_lpf['max_err']}")
        print(f"   - SNR: {metrics_uart_rtl_lpf['snr']:.2f} dB")
        print(f"   - Correlacion (r): {metrics_uart_rtl_lpf['r']:.6f}")
        
    # 2. Tweeter (HPF)
    print("\n" + "-" * 50)
    print(" ANALISIS CANAL PASO ALTO (HPF - TWEETER)")
    print("-" * 50)
    
    # RTL vs Golden (HPF)
    n_samples_rtl_hpf = min(len(g_hpf), len(r_hpf))
    metrics_rtl_g_hpf = compute_metrics(g_hpf[:n_samples_rtl_hpf], r_hpf[:n_samples_rtl_hpf])
    print("1. RTL vs. GOLDEN MODEL:")
    print(f"   - Error absoluto maximo: {metrics_rtl_g_hpf['max_err']}")
    print(f"   - SNR: {metrics_rtl_g_hpf['snr']:.2f} dB")
    print(f"   - Correlacion (r): {metrics_rtl_g_hpf['r']:.6f}")
    if metrics_rtl_g_hpf['max_err'] == 0:
        print("   [ESTADO] 100% BIT-EXACTO!")
    else:
        print("   [ESTADO] Diferencias detectadas en la simulacion.")
        
    # UART HPF comparado
    metrics_uart_g_hpf = None
    metrics_uart_rtl_hpf = None
    u_hpf_aligned_g = None
    g_hpf_aligned = None
    lag_uart_hpf = 0
    
    if has_uart:
        print("\nAlineando senales UART HPF con el Golden Model...")
        u_hpf_aligned_g, g_hpf_aligned, lag_uart_hpf = align_signals(g_hpf, u_hpf)
        metrics_uart_g_hpf = compute_metrics(g_hpf_aligned, u_hpf_aligned_g)
        
        # Alinear UART con RTL
        u_hpf_aligned_r, r_hpf_aligned, _ = align_signals(r_hpf, u_hpf)
        metrics_uart_rtl_hpf = compute_metrics(r_hpf_aligned, u_hpf_aligned_r)
        
        print("\n2. UART vs. GOLDEN MODEL (Alineados):")
        print(f"   - Desfase optimo: {lag_uart_hpf} muestras")
        print(f"   - Error absoluto maximo: {metrics_uart_g_hpf['max_err']}")
        print(f"   - MAE: {metrics_uart_g_hpf['mae']:.2f} | RMSE: {metrics_uart_g_hpf['rmse']:.2f}")
        print(f"   - SNR: {metrics_uart_g_hpf['snr']:.2f} dB")
        print(f"   - Correlacion (r): {metrics_uart_g_hpf['r']:.6f}")
        
        print("\n3. UART vs. RTL SIMULACION (Alineados):")
        print(f"   - Error absoluto maximo: {metrics_uart_rtl_hpf['max_err']}")
        print(f"   - SNR: {metrics_uart_rtl_hpf['snr']:.2f} dB")
        print(f"   - Correlacion (r): {metrics_uart_rtl_hpf['r']:.6f}")
        
    # --- PROCESAMIENTO PSD (RESPUESTA EN FRECUENCIA) ---
    fs = 48000
    print("\nCalculando Densidad Espectral de Potencia (PSD Welch)...")
    
    r_lpf_norm = r_lpf / 8388608.0
    r_hpf_norm = r_hpf / 8388608.0
    
    f_lpf, psd_lpf = signal.welch(r_lpf_norm, fs, nperseg=1024)
    f_hpf, psd_hpf = signal.welch(r_hpf_norm, fs, nperseg=1024)
    
    db_lpf = 10 * np.log10(psd_lpf + 1e-15)
    db_hpf = 10 * np.log10(psd_hpf + 1e-15)
    
    # Cargar y normalizar estimulo de entrada
    input_stimulus_path = "sim/data/noise.bin"
    r_in_norm = None
    if os.path.exists(input_stimulus_path):
        r_in = read_bin_txt_16b_file(input_stimulus_path)
        r_in_norm = r_in / 32768.0
        
    # Calibracion de escala vertical
    offset = 0.0
    if r_in_norm is not None:
        f_in, psd_in = signal.welch(r_in_norm, fs, nperseg=1024)
        db_in = 10 * np.log10(psd_in + 1e-15)
        mean_db_in = np.mean(db_in)
        offset = -6.0 - mean_db_in
        db_in_cal = db_in + offset
    else:
        offset = -np.max(db_lpf)
        
    db_lpf_cal = db_lpf + offset
    db_hpf_cal = db_hpf + offset
    
    # Cargar coeficientes y calcular respuestas teoricas
    coeff_lpf_path = "sim/data/coeff_lpf_48k.bin"
    coeff_hpf_path = "sim/data/coeff_hpf_48k.bin"
    db_lpf_teorica = None
    db_hpf_teorica = None
    
    if os.path.exists(coeff_lpf_path):
        c_lpf = load_coeffs(coeff_lpf_path)
        b_lpf = c_lpf[0:3]
        a_lpf = [1.0, -c_lpf[3], -c_lpf[4]]
        w_lpf, h_lpf_single = signal.freqz(b_lpf, a_lpf, worN=1024, fs=fs)
        h_lpf_teorica = h_lpf_single * h_lpf_single
        db_lpf_teorica = 20 * np.log10(np.abs(h_lpf_teorica) + 1e-15)
        
    if os.path.exists(coeff_hpf_path):
        c_hpf = load_coeffs(coeff_hpf_path)
        b_hpf = c_hpf[0:3]
        a_hpf = [1.0, -c_hpf[3], -c_hpf[4]]
        w_hpf, h_hpf_single = signal.freqz(b_hpf, a_hpf, worN=1024, fs=fs)
        h_hpf_teorica = h_hpf_single * h_hpf_single
        db_hpf_teorica = 20 * np.log10(np.abs(h_hpf_teorica) + 1e-15)
        
    # PSD de la UART si existe
    db_u_lpf_cal = None
    db_u_hpf_cal = None
    if has_uart:
        u_lpf_norm = u_lpf / 8388608.0
        u_hpf_norm = u_hpf / 8388608.0
        f_u_lpf, psd_u_lpf = signal.welch(u_lpf_norm, fs, nperseg=1024)
        f_u_hpf, psd_u_hpf = signal.welch(u_hpf_norm, fs, nperseg=1024)
        db_u_lpf_cal = 10 * np.log10(psd_u_lpf + 1e-15) + offset
        db_u_hpf_cal = 10 * np.log10(psd_u_hpf + 1e-15) + offset
        
    # --- GRAFICAR 1: COMBINADA GENERAL ---
    plt.figure(figsize=(11, 6.5))
    if db_lpf_teorica is not None:
        plt.semilogx(w_lpf, db_lpf_teorica, label="Teorica LPF (Linkwitz-Riley)", color="lightblue", linestyle="--", linewidth=2.5)
    if db_hpf_teorica is not None:
        plt.semilogx(w_hpf, db_hpf_teorica, label="Teorica HPF (Linkwitz-Riley)", color="lightcoral", linestyle="--", linewidth=2.5)
        
    if r_in_norm is not None:
        plt.semilogx(f_in, db_in_cal, label="Entrada (Ruido Blanco)", color="gray", linestyle=":", linewidth=1.2, alpha=0.7)
        
    plt.semilogx(f_lpf, db_lpf_cal, label="Woofer LPF (RTL Sim)", color="blue", linewidth=2.0)
    plt.semilogx(f_hpf, db_hpf_cal, label="Tweeter HPF (RTL Sim)", color="red", linewidth=2.0)
    
    if has_uart:
        plt.semilogx(f_u_lpf, db_u_lpf_cal, label="Woofer LPF (UART)", color="cyan", linestyle="-.", linewidth=1.5, alpha=0.9)
        plt.semilogx(f_u_hpf, db_u_hpf_cal, label="Tweeter HPF (UART)", color="magenta", linestyle="-.", linewidth=1.5, alpha=0.9)
        
    plt.axvline(2000, color="darkgray", linestyle=":", label="Fc = 2.0 kHz")
    octave_freqs = [20, 31.25, 62.5, 125, 250, 500, 1000, 2000, 4000, 8000, 16000, 20000]
    octave_labels = ["20", "31.25", "62.5", "125", "250", "500", "1k", "2k", "4k", "8k", "16k", "20k"]
    plt.xscale("log")
    plt.xticks(octave_freqs, octave_labels)
    plt.title("Respuesta en Frecuencia Crossover IIR (Golden vs. RTL vs. UART)")
    plt.xlabel("Frecuencia (Hz) - Escala de Octavas")
    plt.ylabel("Ganancia Espectral / Magnitud (dB)")
    plt.grid(True, which="both", ls="-", color="0.90")
    plt.legend(loc="lower left")
    plt.xlim(20, 22000)
    plt.ylim(-45, 5)
    
    os.makedirs("doc/plots", exist_ok=True)
    graph_path = "doc/plots/crossover_response.png"
    plt.savefig(graph_path, dpi=300)
    plt.close()
    print(f"\nGrafico combinado guardado en: {graph_path}")
    
    # --- GRAFICAR 2: ANALISIS LPF EXHAUSTIVO ---
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 10))
    # Panel superior: Respuesta en frecuencia
    if db_lpf_teorica is not None:
        ax1.semilogx(w_lpf, db_lpf_teorica, label="Teorica LPF", color="lightblue", linestyle="--", linewidth=2.5)
    ax1.semilogx(f_lpf, db_lpf_cal, label="Woofer LPF (RTL Sim)", color="blue", linewidth=2.0)
    if has_uart:
        ax1.semilogx(f_u_lpf, db_u_lpf_cal, label="Woofer LPF (UART)", color="cyan", linestyle="-.", linewidth=1.8)
    ax1.axvline(2000, color="darkgray", linestyle=":", label="Fc = 2.0 kHz")
    ax1.xscale = "log"
    ax1.set_xscale("log")
    ax1.set_xticks(octave_freqs)
    ax1.set_xticklabels(octave_labels)
    ax1.set_title("Analisis Espectral (Welch PSD) - Canal Paso Bajo (LPF)")
    ax1.set_xlabel("Frecuencia (Hz)")
    ax1.set_ylabel("Magnitud (dB)")
    ax1.grid(True, which="both", ls="-", color="0.90")
    ax1.legend(loc="lower left")
    ax1.set_xlim(20, 22000)
    ax1.set_ylim(-45, 5)
    
    # Panel inferior: Comparativa temporal
    # Mostrar las primeras 150 muestras de simulacion frente a la UART alineada
    n_plot = 150
    if has_uart and u_lpf_aligned_g is not None:
        ax2.plot(g_lpf_aligned[:n_plot], label="Golden Model", color="black", alpha=0.5, linewidth=3)
        ax2.plot(r_lpf_aligned[:n_plot], label="RTL Sim", color="blue", alpha=0.8, linewidth=1.5)
        ax2.plot(u_lpf_aligned_g[:n_plot], label=f"UART (Alineado, Lag={lag_uart_lpf})", color="cyan", linestyle="--", linewidth=1.5)
    else:
        # Si no hay UART, comparar Golden vs RTL
        ax2.plot(g_lpf[:n_plot], label="Golden Model", color="black", alpha=0.5, linewidth=3)
        ax2.plot(r_lpf[:n_plot], label="RTL Sim", color="blue", alpha=0.8, linewidth=1.5)
        
    ax2.set_title(f"Muestras de Tiempo Alineadas (Primeras {n_plot} muestras) - Canal LPF")
    ax2.set_xlabel("Muestra")
    ax2.set_ylabel("Valor Digital (24-bit)")
    ax2.grid(True)
    ax2.legend(loc="upper right")
    
    plt.tight_layout()
    lpf_graph_path = "doc/plots/crossover_lpf_analysis.png"
    plt.savefig(lpf_graph_path, dpi=300)
    plt.close()
    print(f"Grafico LPF guardado en: {lpf_graph_path}")
    
    # --- GRAFICAR 3: ANALISIS HPF EXHAUSTIVO ---
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 10))
    # Panel superior: Respuesta en frecuencia
    if db_hpf_teorica is not None:
        ax1.semilogx(w_hpf, db_hpf_teorica, label="Teorica HPF", color="lightcoral", linestyle="--", linewidth=2.5)
    ax1.semilogx(f_hpf, db_hpf_cal, label="Tweeter HPF (RTL Sim)", color="red", linewidth=2.0)
    if has_uart:
        ax1.semilogx(f_u_hpf, db_u_hpf_cal, label="Tweeter HPF (UART)", color="magenta", linestyle="-.", linewidth=1.8)
    ax1.axvline(2000, color="darkgray", linestyle=":", label="Fc = 2.0 kHz")
    ax1.set_xscale("log")
    ax1.set_xticks(octave_freqs)
    ax1.set_xticklabels(octave_labels)
    ax1.set_title("Analisis Espectral (Welch PSD) - Canal Paso Alto (HPF)")
    ax1.set_xlabel("Frecuencia (Hz)")
    ax1.set_ylabel("Magnitud (dB)")
    ax1.grid(True, which="both", ls="-", color="0.90")
    ax1.legend(loc="lower left")
    ax1.set_xlim(20, 22000)
    ax1.set_ylim(-45, 5)
    
    # Panel inferior: Comparativa temporal
    if has_uart and u_hpf_aligned_g is not None:
        ax2.plot(g_hpf_aligned[:n_plot], label="Golden Model", color="black", alpha=0.5, linewidth=3)
        ax2.plot(r_hpf_aligned[:n_plot], label="RTL Sim", color="red", alpha=0.8, linewidth=1.5)
        ax2.plot(u_hpf_aligned_g[:n_plot], label=f"UART (Alineado, Lag={lag_uart_hpf})", color="magenta", linestyle="--", linewidth=1.5)
    else:
        ax2.plot(g_hpf[:n_plot], label="Golden Model", color="black", alpha=0.5, linewidth=3)
        ax2.plot(r_hpf[:n_plot], label="RTL Sim", color="red", alpha=0.8, linewidth=1.5)
        
    ax2.set_title(f"Muestras de Tiempo Alineadas (Primeras {n_plot} muestras) - Canal HPF")
    ax2.set_xlabel("Muestra")
    ax2.set_ylabel("Valor Digital (24-bit)")
    ax2.grid(True)
    ax2.legend(loc="upper right")
    
    plt.tight_layout()
    hpf_graph_path = "doc/plots/crossover_hpf_analysis.png"
    plt.savefig(hpf_graph_path, dpi=300)
    plt.close()
    print(f"Grafico HPF guardado en: {hpf_graph_path}")
    
    # --- GENERAR INFORME DE VALIDACION MARKDOWN ---
    os.makedirs("doc/notes", exist_ok=True)
    report_path = "doc/notes/validation_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Informe de Validacion y Bit-Exactitud del Crossover Digital IIR\n\n")
        f.write(f"**Fecha del analisis:** {np.datetime64('now')}\n")
        if has_uart:
            f.write(f"**Ultima Captura UART utilizada:** `{u_lpf_path}` / `{u_hpf_path}` (Timestamp: `{uart_timestamp}`)\n")
        else:
            f.write("**Ultima Captura UART utilizada:** No disponible\n")
            
        f.write("\n## 1. Canal Paso Bajo (LPF - Woofer)\n\n")
        f.write("### RTL vs. Golden Model (Simulacion)\n")
        f.write(f"- **Error Absoluto Maximo:** `{metrics_rtl_g_lpf['max_err']}`\n")
        f.write(f"- **Error Absoluto Medio (MAE):** `{metrics_rtl_g_lpf['mae']:.4f}`\n")
        f.write(f"- **SNR:** `{metrics_rtl_g_lpf['snr']:.4f} dB`\n")
        f.write(f"- **Correlacion de Pearson:** `{metrics_rtl_g_lpf['r']:.8f}`\n")
        f.write(f"- **Estado:** `{'BIT-EXACTO' if metrics_rtl_g_lpf['max_err'] == 0 else 'DESVIACION DETECTADA'}`\n\n")
        
        if has_uart:
            f.write("### UART vs. Golden Model (Fisico vs. Teorico)\n")
            f.write(f"- **Alineacion (Lag):** `{lag_uart_lpf}` muestras\n")
            f.write(f"- **Error Absoluto Maximo:** `{metrics_uart_g_lpf['max_err']}`\n")
            f.write(f"- **Error Absoluto Medio (MAE):** `{metrics_uart_g_lpf['mae']:.4f}`\n")
            f.write(f"- **SNR:** `{metrics_uart_g_lpf['snr']:.4f} dB`\n")
            f.write(f"- **Correlacion de Pearson:** `{metrics_uart_g_lpf['r']:.8f}`\n\n")
            
            f.write("### UART vs. RTL (Fisico vs. Simulacion)\n")
            f.write(f"- **Error Absoluto Maximo:** `{metrics_uart_rtl_lpf['max_err']}`\n")
            f.write(f"- **Error Absoluto Medio (MAE):** `{metrics_uart_rtl_lpf['mae']:.4f}`\n")
            f.write(f"- **SNR:** `{metrics_uart_rtl_lpf['snr']:.4f} dB`\n")
            f.write(f"- **Correlacion de Pearson:** `{metrics_uart_rtl_lpf['r']:.8f}`\n\n")
            
        f.write("\n## 2. Canal Paso Alto (HPF - Tweeter)\n\n")
        f.write("### RTL vs. Golden Model (Simulacion)\n")
        f.write(f"- **Error Absoluto Maximo:** `{metrics_rtl_g_hpf['max_err']}`\n")
        f.write(f"- **Error Absoluto Medio (MAE):** `{metrics_rtl_g_hpf['mae']:.4f}`\n")
        f.write(f"- **SNR:** `{metrics_rtl_g_hpf['snr']:.4f} dB`\n")
        f.write(f"- **Correlacion de Pearson:** `{metrics_rtl_g_hpf['r']:.8f}`\n")
        f.write(f"- **Estado:** `{'BIT-EXACTO' if metrics_rtl_g_hpf['max_err'] == 0 else 'DESVIACION DETECTADA'}`\n\n")
        
        if has_uart:
            f.write("### UART vs. Golden Model (Fisico vs. Teorico)\n")
            f.write(f"- **Alineacion (Lag):** `{lag_uart_hpf}` muestras\n")
            f.write(f"- **Error Absoluto Maximo:** `{metrics_uart_g_hpf['max_err']}`\n")
            f.write(f"- **Error Absoluto Medio (MAE):** `{metrics_uart_g_hpf['mae']:.4f}`\n")
            f.write(f"- **SNR:** `{metrics_uart_g_hpf['snr']:.4f} dB`\n")
            f.write(f"- **Correlacion de Pearson:** `{metrics_uart_g_hpf['r']:.8f}`\n\n")
            
            f.write("### UART vs. RTL (Fisico vs. Simulacion)\n")
            f.write(f"- **Error Absoluto Maximo:** `{metrics_uart_rtl_hpf['max_err']}`\n")
            f.write(f"- **Error Absoluto Medio (MAE):** `{metrics_uart_rtl_hpf['mae']:.4f}`\n")
            f.write(f"- **SNR:** `{metrics_uart_rtl_hpf['snr']:.4f} dB`\n")
            f.write(f"- **Correlacion de Pearson:** `{metrics_uart_rtl_hpf['r']:.8f}`\n\n")
            
        # Conclusiones automatizadas
        f.write("## 3. Diagnostico y Conclusion\n\n")
        if metrics_rtl_g_lpf['max_err'] == 0 and metrics_rtl_g_hpf['max_err'] == 0:
            f.write("- **Simulacion RTL:** El hardware descrito en RTL es **totalmente bit-exacto** respecto al Golden Model.\n")
        else:
            f.write("- **Simulacion RTL:** Se observan desviaciones numericas. Comprobar diferencias de redondeo o truncamiento en la simulacion RTL.\n")
            
        if has_uart:
            # Evaluar calidad fisica (UART vs RTL/Golden)
            if metrics_uart_rtl_lpf['snr'] > 70 and metrics_uart_rtl_hpf['snr'] > 70:
                f.write("- **Hardware Fisico (UART):** Los datos capturados por UART muestran una **excelente coincidencia** con la simulacion ")
                f.write(f"(SNR Woofer: {metrics_uart_rtl_lpf['snr']:.1f} dB, SNR Tweeter: {metrics_uart_rtl_hpf['snr']:.1f} dB).\n")
            else:
                f.write("- **Hardware Fisico (UART):** Se detectan desviaciones significativas o atenuacion en los datos de la UART. ")
                f.write(f"(SNR Woofer: {metrics_uart_rtl_lpf['snr']:.1f} dB, SNR Tweeter: {metrics_uart_rtl_hpf['snr']:.1f} dB). ")
                f.write("Verificar el formato de los datos transmitidos o posibles perdidas de muestras en la transmision serie.\n")
                
    print(f"Informe de validacion guardado en: {report_path}")

if __name__ == "__main__":
    main()
