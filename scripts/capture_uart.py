#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
capture_uart.py
Adquiere tramas de audio digital transmitidas por la UART de la FPGA,
sincroniza las muestras compuestas de 8 bytes y las guarda en formato
hexadecimal de 24 bits para que puedan ser comparadas con el Golden Model.
"""

import sys
import os
import argparse
import time

try:
    import serial
except ImportError:
    print("Error: Se requiere instalar 'pyserial'. Ejecuta: pip install pyserial")
    sys.exit(1)

def parse_args():
    parser = argparse.ArgumentParser(description="Captura de tramas de audio del crossover por UART.")
    parser.add_argument("-p", "--port", type=str, required=True, help="Puerto COM serial (ej. COM3 o /dev/ttyUSB0)")
    parser.add_argument("-b", "--baud", type=int, default=921600, help="Velocidad en baudios (por defecto 921600)")
    parser.add_argument("-n", "--samples", type=int, default=4096, help="Numero de muestras a capturar (por defecto 4096)")
    parser.add_argument("-o", "--output-dir", type=str, default="sim/data", help="Directorio de salida de los resultados")
    return parser.parse_args()

def main():
    args = parse_args()
    
    print("=" * 60)
    print(" ADQUISICION DE DATOS AUDIO CROSSOVER VIA UART")
    print("=" * 60)
    print(f"Puerto: {args.port}")
    print(f"Baudrate: {args.baud}")
    print(f"Muestras objetivo: {args.samples}")
    
    os.makedirs(args.output_dir, exist_ok=True)
    
    output_lpf_path = os.path.join(args.output_dir, "output_lpf_rtl.txt")
    output_hpf_path = os.path.join(args.output_dir, "output_hpf_rtl.txt")
    
    try:
        ser = serial.Serial(args.port, args.baud, timeout=2.0)
    except Exception as e:
        print(f"Error al abrir el puerto {args.port}: {e}")
        return
        
    print("Puerto abierto con exito. Esperando sincronizacion...")
    
    # Limpiar buffer de entrada para evitar lecturas antiguas
    ser.reset_input_buffer()
    
    # Enviar comando de inicio (CMD_START = 0x01) a la FPGA para arrancar
    print("Enviando comando de inicio START (0x01)...")
    ser.write(bytes([0x01]))
    ser.flush()
    
    lpf_samples = []
    hpf_samples = []
    
    # Marcadores de trama
    START_BYTE = 0xAA
    END_BYTE = 0x55
    
    captured_count = 0
    start_time = time.time()
    
    try:
        while captured_count < args.samples:
            # Buscar el byte de inicio de trama
            b = ser.read(1)
            if not b:
                # Timeout
                print("\nError: Timeout de lectura. Asegurate de que la placa esta encendida y transmitiendo.")
                break
                
            if ord(b) == START_BYTE:
                # Leer los 7 bytes restantes de la trama
                payload = ser.read(7)
                if len(payload) < 7:
                    continue # Trama incompleta por timeout
                    
                # Verificar byte finalizador
                if payload[6] == END_BYTE:
                    # Trama valida. Reconstruir valores de 24 bits
                    # Woofer: Bytes 0, 1, 2
                    val_lpf = (payload[0] << 16) | (payload[1] << 8) | payload[2]
                    # Tweeter: Bytes 3, 4, 5
                    val_hpf = (payload[3] << 16) | (payload[4] << 8) | payload[5]
                    
                    lpf_samples.append(val_lpf)
                    hpf_samples.append(val_hpf)
                    
                    captured_count += 1
                    
                    # Mostrar progreso en consola
                    if captured_count % 500 == 0 or captured_count == args.samples:
                        elapsed = time.time() - start_time
                        rate = captured_count / elapsed if elapsed > 0 else 0
                        print(f"Capturadas {captured_count}/{args.samples} muestras ({rate:.1f} muestras/s)...", end="\r")
                else:
                    # Desalineado, buscar el siguiente START_BYTE
                    continue
                    
    except KeyboardInterrupt:
        print("\nCaptura interrumpida por el usuario.")
    finally:
        ser.close()
        print("\nPuerto serie cerrado.")
        
    if captured_count > 0:
        # Guardar en ficheros en formato hexadecimal de 24-bit en texto plano
        print(f"\nGuardando {captured_count} muestras de salida...")
        
        with open(output_lpf_path, "w") as f:
            f.write(f"// Muestras Woofer LPF adquiridas por UART de la placa\n")
            for val in lpf_samples:
                f.write(f"{val:06X}\n")
                
        with open(output_hpf_path, "w") as f:
            f.write(f"// Muestras Tweeter HPF adquiridas por UART de la placa\n")
            for val in hpf_samples:
                f.write(f"{val:06X}\n")
                
        print(f"Salida LPF guardada en: {output_lpf_path}")
        print(f"Salida HPF guardada en: {output_hpf_path}")
        print("Adquisicion finalizada. Listo para ejecutar analyze_output.py.")
    else:
        print("No se capturaron muestras. Verifica el cableado y los pines.")

if __name__ == "__main__":
    main()
