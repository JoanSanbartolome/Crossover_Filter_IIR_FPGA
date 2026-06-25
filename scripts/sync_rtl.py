#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_rtl.py
Copia de forma automatizada y plana todos los archivos de diseño RTL (.sv, .v)
desde la carpeta 'rtl/' del proyecto hacia el directorio de origen de Gowin EDA
en 'gowin/Crossover/src/'.
"""

import os
import shutil
import glob

def main():
    src_dir = "rtl"
    dest_dir = os.path.join("gowin", "Crossover", "src")
    
    print("=" * 60)
    # Buscamos todos los archivos .sv y .v recursivamente en la carpeta 'rtl'
    files_to_copy = []
    for ext in ("/**/*.sv", "/**/*.v"):
        files_to_copy.extend(glob.glob(src_dir + ext, recursive=True))
        
    if not files_to_copy:
        print(f"[WARN] No se encontraron archivos RTL (.sv, .v) en '{src_dir}'.")
        return

    # Verificar que el directorio destino exista, si no se crea
    os.makedirs(dest_dir, exist_ok=True)

    print(f"Sincronizando {len(files_to_copy)} archivos a: {dest_dir}")
    print("-" * 60)

    for fpath in files_to_copy:
        filename = os.path.basename(fpath)
        dest_path = os.path.join(dest_dir, filename)
        
        try:
            # Copiar archivo preservando metadatos
            shutil.copy2(fpath, dest_path)
            print(f"  [OK]  {fpath} -> {dest_path}")
        except Exception as e:
            print(f"  [ERR] Error al copiar {fpath}: {e}")

    print("-" * 60)
    print("Sincronizacion completada con exito.")
    print("=" * 60)

if __name__ == "__main__":
    main()
