#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crossover_gui.py
Interfaz grafica para la adquisicion de datos UART, analisis de respuesta espectral,
y comparacion con la respuesta en frecuencia teorica del Crossover IIR.
"""

import sys
import os
import time
import datetime
import threading
import glob
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import numpy as np
from scipy import signal

# Intentar importar dependencias de GUI y Serial
try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("Error: Se requiere 'pyserial'. Ejecuta: .venv\\Scripts\\pip.exe install pyserial")
    sys.exit(1)

try:
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
except ImportError:
    print("Error: Se requiere 'matplotlib'. Ejecuta: .venv\\Scripts\\pip.exe install matplotlib")
    sys.exit(1)

class CrossoverGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Tang Nano 9K - Crossover IIR DSP Validator")
        self.root.geometry("1400x850")
        self.root.minsize(1200, 700)
        
        # Frecuencia de muestreo del sistema
        self.FS = 48000

        # Variables de control
        self.port_var = tk.StringVar()
        self.baud_var = tk.StringVar(value="921600")
        self.samples_var = tk.StringVar(value="4096")
        self.fc_var = tk.StringVar(value="2000.0")
        self.status_var = tk.StringVar(value="Listo.")
        self.progress_var = tk.DoubleVar(value=0.0)
        self.mode_var = tk.StringVar(value="TF")  # "PSD" o "TF" (Transfer Function)
        self.op_mode_var = tk.StringVar(value="Normal") # "Normal" (crossover) o "Bypass" (directo)

        # Visibilidad de senales en el grafico (selector de leyenda)
        self.vis_lpf_teorica  = tk.BooleanVar(value=True)
        self.vis_hpf_teorica  = tk.BooleanVar(value=True)
        self.vis_lpf_obs      = tk.BooleanVar(value=True)
        self.vis_hpf_obs      = tk.BooleanVar(value=True)
        self.vis_input_noise  = tk.BooleanVar(value=True)

        # Variables para el monitor UART en vivo
        self.uart_monitor_var = tk.StringVar(value="Monitor UART (Ultimas tramas de bajada):\nEsperando transmision...")
        self.last_frames = [] # Guardara las ultimas 5 tramas decodificadas de 8 bytes

        self.is_capturing = False
        self.captured_lpf = []
        self.captured_hpf = []

        # Directorio separado para capturas fisicas (no sobreescribe sim/data/)
        self.capture_dir = "captures"
        os.makedirs(self.capture_dir, exist_ok=True)

        # Ruta de la captura activa en el grafico
        self.active_capture_lpf = None
        self.active_capture_hpf = None

        # Referencias a las lineas matplotlib (para toggle sin redibujar todo)
        self._plot_lines = {}
        
        self.create_styles()
        self.create_widgets()
        self.refresh_ports()
        
    def create_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        # Paleta de colores Premium (Modo Oscuro)
        self.bg_color = "#1E1E24"
        self.panel_bg = "#2A2A35"
        self.accent_color = "#4E88FF"
        self.text_color = "#F0F0F0"
        self.highlight_color = "#3A3A4A"
        
        self.root.configure(bg=self.bg_color)
        
        style.configure(".", bg=self.bg_color, fg=self.text_color, fieldbackground=self.panel_bg)
        style.configure("TFrame", background=self.bg_color)
        style.configure("Panel.TFrame", background=self.panel_bg, relief="flat")
        
        style.configure("TLabel", background=self.bg_color, foreground=self.text_color, font=("Segoe UI", 12))
        style.configure("Panel.TLabel", background=self.panel_bg, foreground=self.text_color, font=("Segoe UI", 12))
        style.configure("Header.TLabel", background=self.panel_bg, foreground=self.accent_color, font=("Segoe UI Semibold", 15))
        style.configure("Title.TLabel", background=self.bg_color, foreground=self.text_color, font=("Segoe UI Semibold", 20))
        
        style.configure("TButton", font=("Segoe UI Semibold", 12), borderwidth=1, focuscolor=self.accent_color)
        style.map("TButton",
                  background=[('active', self.accent_color), ('!disabled', self.highlight_color)],
                  foreground=[('active', '#FFFFFF'), ('!disabled', self.text_color)])
                  
        style.configure("Accent.TButton", font=("Segoe UI Semibold", 12, "bold"), borderwidth=1)
        style.map("Accent.TButton",
                  background=[('active', '#3570E5'), ('!disabled', self.accent_color)],
                  foreground=[('active', '#FFFFFF'), ('!disabled', '#FFFFFF')])

        style.configure("TCombobox", fieldbackground=self.panel_bg, background=self.highlight_color, foreground=self.text_color, font=("Segoe UI", 12))
        style.configure("TEntry", fieldbackground=self.panel_bg, foreground=self.text_color, insertcolor=self.text_color, font=("Segoe UI", 12))

    def create_widgets(self):
        # Contenedor principal de rejilla
        self.root.columnconfigure(0, weight=0, minsize=320)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=0)
        
        # ================= LEFT PANEL (Configuraciones) =================
        left_panel = ttk.Frame(self.root, style="Panel.TFrame")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        left_panel.columnconfigure(0, weight=1)
        
        # Titulo del panel
        lbl_title = ttk.Label(left_panel, text="Configuracion UART & Crossover", style="Header.TLabel")
        lbl_title.grid(row=0, column=0, sticky="w", padx=15, pady=15)
        
        # Puerto COM
        lbl_port = ttk.Label(left_panel, text="Puerto Serie (COM):", style="Panel.TLabel")
        lbl_port.grid(row=1, column=0, sticky="w", padx=15, pady=2)
        
        self.combo_ports = ttk.Combobox(left_panel, textvariable=self.port_var, state="readonly")
        self.combo_ports.grid(row=2, column=0, sticky="ew", padx=15, pady=5)
        
        btn_refresh = ttk.Button(left_panel, text="Buscar Puertos", command=self.refresh_ports)
        btn_refresh.grid(row=3, column=0, sticky="ew", padx=15, pady=5)
        
        # Velocidad en Baudios
        lbl_baud = ttk.Label(left_panel, text="Velocidad (Baudios):", style="Panel.TLabel")
        lbl_baud.grid(row=4, column=0, sticky="w", padx=15, pady=2)
        self.entry_baud = ttk.Entry(left_panel, textvariable=self.baud_var)
        self.entry_baud.grid(row=5, column=0, sticky="ew", padx=15, pady=5)
        
        # Muestras a Capturar
        lbl_samples = ttk.Label(left_panel, text="Numero de Muestras:", style="Panel.TLabel")
        lbl_samples.grid(row=6, column=0, sticky="w", padx=15, pady=2)
        self.entry_samples = ttk.Entry(left_panel, textvariable=self.samples_var)
        self.entry_samples.grid(row=7, column=0, sticky="ew", padx=15, pady=5)

        # Frecuencia de Corte (Hz)
        lbl_fc = ttk.Label(left_panel, text="Frecuencia de Corte (Hz):", style="Panel.TLabel")
        lbl_fc.grid(row=8, column=0, sticky="w", padx=15, pady=2)
        self.entry_fc = ttk.Entry(left_panel, textvariable=self.fc_var)
        self.entry_fc.grid(row=9, column=0, sticky="ew", padx=15, pady=5)

        # Frame contenedor para el flujo de simulacion
        sim_frame = ttk.Frame(left_panel, style="Panel.TFrame")
        sim_frame.grid(row=10, column=0, sticky="ew", padx=15, pady=5)
        sim_frame.columnconfigure(0, weight=1)
        sim_frame.columnconfigure(1, weight=1)
        
        # Boton de Generacion de Estimulos
        btn_gen_stim = ttk.Button(sim_frame, text="1. Gen. Estimulos", command=self.generate_stimulus_gui)
        btn_gen_stim.grid(row=0, column=0, sticky="ew", padx=2, pady=3)
        
        # Boton de Golden Model
        btn_golden = ttk.Button(sim_frame, text="2. Golden Model", command=self.run_golden_model_gui)
        btn_golden.grid(row=0, column=1, sticky="ew", padx=2, pady=3)
        
        # Boton de Simulacion RTL
        btn_sim_rtl = ttk.Button(sim_frame, text="3. Simular RTL", command=self.run_simulation_gui)
        btn_sim_rtl.grid(row=1, column=0, sticky="ew", padx=2, pady=3)

        # Boton de Flujo Completo
        btn_full_flow = ttk.Button(sim_frame, text="Flujo Completo", command=self.run_complete_flow_gui)
        btn_full_flow.grid(row=1, column=1, sticky="ew", padx=2, pady=3)
        
        # Separador
        sep = ttk.Separator(left_panel, orient="horizontal")
        sep.grid(row=11, column=0, sticky="ew", padx=10, pady=15)
        
        # Modo de Operacion FPGA
        lbl_op_mode = ttk.Label(left_panel, text="Modo de Operacion FPGA:", style="Panel.TLabel")
        lbl_op_mode.grid(row=12, column=0, sticky="w", padx=15, pady=2)
        
        self.r_op_normal = ttk.Radiobutton(left_panel, text="Crossover DSP Activo", variable=self.op_mode_var, value="Normal")
        self.r_op_normal.grid(row=13, column=0, sticky="w", padx=20, pady=4)
        
        self.r_op_bypass = ttk.Radiobutton(left_panel, text="Bypass de DSP (Diagnostico)", variable=self.op_mode_var, value="Bypass")
        self.r_op_bypass.grid(row=14, column=0, sticky="w", padx=20, pady=4)
        
        # Separador
        sep_op = ttk.Separator(left_panel, orient="horizontal")
        sep_op.grid(row=15, column=0, sticky="ew", padx=10, pady=10)
        
        # Modo de visualizacion
        lbl_mode = ttk.Label(left_panel, text="Modo de Visualizacion:", style="Panel.TLabel")
        lbl_mode.grid(row=16, column=0, sticky="w", padx=15, pady=2)
        
        self.r_tf = ttk.Radiobutton(left_panel, text="Funcion de Transferencia (H(f))", variable=self.mode_var, value="TF", command=self.update_plot)
        self.r_tf.grid(row=17, column=0, sticky="w", padx=20, pady=4)
        
        self.r_psd = ttk.Radiobutton(left_panel, text="Densidad Espectral (PSD Welch)", variable=self.mode_var, value="PSD", command=self.update_plot)
        self.r_psd.grid(row=18, column=0, sticky="w", padx=20, pady=4)
        
        # Botones de Accion
        self.btn_stream = ttk.Button(left_panel, text="Iniciar Filtrado (Streaming UART)", style="Accent.TButton", command=self.start_stream_thread)
        self.btn_stream.grid(row=19, column=0, sticky="ew", padx=15, pady=10)
        
        self.btn_analyze = ttk.Button(left_panel, text="Recargar Analisis", command=self.update_plot)
        self.btn_analyze.grid(row=20, column=0, sticky="ew", padx=15, pady=5)
        
        # Barra de progreso
        self.prog_bar = ttk.Progressbar(left_panel, variable=self.progress_var, maximum=100)
        self.prog_bar.grid(row=21, column=0, sticky="ew", padx=15, pady=15)
        
        # Separador
        sep2 = ttk.Separator(left_panel, orient="horizontal")
        sep2.grid(row=22, column=0, sticky="ew", padx=10, pady=10)

        # Selector de captura historica
        lbl_hist = ttk.Label(left_panel, text="Captura a Analizar:", style="Panel.TLabel")
        lbl_hist.grid(row=23, column=0, sticky="w", padx=15, pady=2)

        self.capture_var = tk.StringVar(value="(ultima captura)")
        self.combo_captures = ttk.Combobox(left_panel, textvariable=self.capture_var, state="readonly")
        self.combo_captures.grid(row=24, column=0, sticky="ew", padx=15, pady=5)
        self.combo_captures.bind("<<ComboboxSelected>>", lambda e: self._on_capture_selected())

        btn_refresh_cap = ttk.Button(left_panel, text="Actualizar Lista", command=self.refresh_captures)
        btn_refresh_cap.grid(row=25, column=0, sticky="ew", padx=15, pady=3)

        self.lbl_capture_path = ttk.Label(left_panel, text="", style="Panel.TLabel",
                                           wraplength=280, foreground="#8C8C8C",
                                           font=("Segoe UI", 10))
        self.lbl_capture_path.grid(row=26, column=0, sticky="w", padx=15, pady=2)

        # Inicializar lista de capturas
        self.refresh_captures()

        # Selector de Leyenda
        sep3 = ttk.Separator(left_panel, orient="horizontal")
        sep3.grid(row=27, column=0, sticky="ew", padx=10, pady=10)

        lbl_legend = ttk.Label(left_panel, text="Visibilidad de Senales:", style="Panel.TLabel")
        lbl_legend.grid(row=28, column=0, sticky="w", padx=15, pady=2)

        legend_items = [
            (self.vis_lpf_teorica, "Teorica LPF (Woofer)",   "#4E88FF"),
            (self.vis_hpf_teorica, "Teorica HPF (Tweeter)",  "#FF6E6E"),
            (self.vis_lpf_obs,     "Obs. LPF (Woofer)",     "#0052D9"),
            (self.vis_hpf_obs,     "Obs. HPF (Tweeter)",    "#D9001B"),
            (self.vis_input_noise, "Entrada (Ruido Blanco)","#A0A0A0"),
        ]
        for i, (var, text, color) in enumerate(legend_items):
            cb = tk.Checkbutton(
                left_panel, text=text, variable=var,
                command=self._apply_visibility,
                bg=self.panel_bg, fg=color, selectcolor=self.panel_bg,
                activebackground=self.panel_bg, activeforeground=color,
                font=("Segoe UI", 11), anchor="w", cursor="hand2"
            )
            cb.grid(row=29 + i, column=0, sticky="ew", padx=15, pady=1)

        # ================= RIGHT PANEL (Grafico Matplotlib) =================
        right_panel = ttk.Frame(self.root)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(0, weight=0)
        right_panel.rowconfigure(1, weight=0)
        right_panel.rowconfigure(2, weight=1)

        # Cabecera del panel derecho: titulo + Fs
        header_frame = ttk.Frame(right_panel)
        header_frame.grid(row=0, column=0, sticky="ew", pady=(5, 0))
        header_frame.columnconfigure(0, weight=1)

        lbl_graph_title = ttk.Label(header_frame, text="Validacion de Respuesta en Frecuencia: Teorica vs. Capturada", style="Title.TLabel")
        lbl_graph_title.grid(row=0, column=0, sticky="w")

        # Badge Fs — siempre visible, con estilo pill
        fs_frame = tk.Frame(header_frame, bg="#1A2E4A", bd=0)
        fs_frame.grid(row=0, column=1, sticky="e", padx=10)
        lbl_fs = tk.Label(
            fs_frame,
            text=f"  Fs = {self.FS:,} Hz  ",
            bg="#1A2E4A", fg="#4E88FF",
            font=("Segoe UI Semibold", 12), padx=8, pady=3
        )
        lbl_fs.pack()

        # Separador visual
        sep_right = ttk.Separator(right_panel, orient="horizontal")
        sep_right.grid(row=1, column=0, sticky="ew", pady=4)
        
        # Contenedor de Matplotlib
        self.graph_frame = ttk.Frame(right_panel)
        self.graph_frame.grid(row=2, column=0, sticky="nsew")
        self.graph_frame.columnconfigure(0, weight=1)
        self.graph_frame.rowconfigure(0, weight=1)

        # Inicializar grafico vacio
        self.fig, self.ax = plt.subplots(figsize=(8, 5))
        self.fig.patch.set_facecolor(self.bg_color)
        self.ax.set_facecolor(self.panel_bg)
        self.ax.tick_params(colors=self.text_color)
        self.ax.xaxis.label.set_color(self.text_color)
        self.ax.yaxis.label.set_color(self.text_color)
        self.ax.title.set_color(self.text_color)
        self.ax.grid(True, which="both", ls="-", color="#3A3A4A")

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        # ================= MONITOR DE DIAGNOSTICO DINAMICO =================
        right_panel.rowconfigure(3, weight=0)
        monitor_frame = ttk.Frame(right_panel, style="Panel.TFrame")
        monitor_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        monitor_frame.columnconfigure(0, weight=1)
        monitor_frame.columnconfigure(1, weight=0)
        
        lbl_mon_title = ttk.Label(monitor_frame, text="Monitor de Diagnostico:", 
                                  style="Panel.TLabel", foreground=self.accent_color, font=("Segoe UI Semibold", 11))
        lbl_mon_title.grid(row=0, column=0, sticky="w", padx=15, pady=(5, 2))
        
        # Selector de tipo de log
        self.mon_mode_var = tk.StringVar(value="UART")
        
        mode_selectors_frame = ttk.Frame(monitor_frame, style="Panel.TFrame")
        mode_selectors_frame.grid(row=0, column=1, sticky="e", padx=15)
        
        r_mon_uart = ttk.Radiobutton(mode_selectors_frame, text="Tramas UART", variable=self.mon_mode_var, value="UART", command=self.update_monitor_view)
        r_mon_uart.pack(side="left", padx=5)
        
        r_mon_ms = ttk.Radiobutton(mode_selectors_frame, text="Log ModelSim", variable=self.mon_mode_var, value="MODELSIM", command=self.update_monitor_view)
        r_mon_ms.pack(side="left", padx=5)
        
        r_mon_sc = ttk.Radiobutton(mode_selectors_frame, text="Log Scripts", variable=self.mon_mode_var, value="SCRIPTS", command=self.update_monitor_view)
        r_mon_sc.pack(side="left", padx=5)
        
        # ScrolledText para la consola
        self.txt_monitor = scrolledtext.ScrolledText(
            monitor_frame,
            bg="#121216", fg="#00FF66",
            insertbackground="#00FF66",
            font=("Consolas", 10),
            height=6,
            relief="sunken", bd=1,
            state="disabled"
        )
        self.txt_monitor.grid(row=1, column=0, columnspan=2, sticky="ew", padx=15, pady=(2, 8))
        
        # Inicializar acumulador de logs vacio
        self.scripts_log_accumulator = "Historial de ejecucion de scripts vacio.\n"

        # ================= BOTTOM STATUS BAR =================
        status_bar = ttk.Frame(self.root, style="Panel.TFrame")
        status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        status_bar.columnconfigure(0, weight=1)

        lbl_status = ttk.Label(status_bar, textvariable=self.status_var, style="Panel.TLabel", font=("Segoe UI", 11))
        lbl_status.grid(row=0, column=0, sticky="w", padx=15, pady=5)

        # Graficar grafico por defecto
        self.update_plot()

    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        port_list = [p.device for p in ports]
        self.combo_ports['values'] = port_list
        if port_list:
            if "COM6" in port_list:
                self.port_var.set("COM6")
            else:
                self.port_var.set(port_list[0])
        else:
            self.port_var.set("")
            self.status_var.set("Advertencia: No se detectaron puertos COM.")

    def refresh_captures(self):
        """Escanea el directorio captures/ y actualiza el combobox."""
        pattern = os.path.join(self.capture_dir, "capture_*_lpf.txt")
        files = sorted(glob.glob(pattern), reverse=True)  # mas reciente primero
        timestamps = []
        for f in files:
            ts = os.path.basename(f).replace("capture_", "").replace("_lpf.txt", "")
            timestamps.append(ts)

        if timestamps:
            self.combo_captures['values'] = timestamps
            self.capture_var.set(timestamps[0])
            self._load_capture_by_timestamp(timestamps[0])
        else:
            self.combo_captures['values'] = []
            self.capture_var.set("(sin capturas)")
            self.active_capture_lpf = None
            self.active_capture_hpf = None
            self.lbl_capture_path.config(text="No hay capturas en captures/")

    def _on_capture_selected(self):
        ts = self.capture_var.get()
        if ts and ts != "(sin capturas)":
            self._load_capture_by_timestamp(ts)
            self.update_plot()

    def _load_capture_by_timestamp(self, ts):
        lpf = os.path.join(self.capture_dir, f"capture_{ts}_lpf.txt")
        hpf = os.path.join(self.capture_dir, f"capture_{ts}_hpf.txt")
        if os.path.exists(lpf) and os.path.exists(hpf):
            self.active_capture_lpf = lpf
            self.active_capture_hpf = hpf
            self.lbl_capture_path.config(
                text=f"Captura: {ts}\n{lpf}",
                foreground="#4CAF50"
            )
        else:
            self.active_capture_lpf = None
            self.active_capture_hpf = None
            self.lbl_capture_path.config(text="Archivos no encontrados.", foreground="#F44336")

    def generate_stimulus_gui(self):
        try:
            samples = int(self.samples_var.get())
        except ValueError:
            samples = 4096
            
        self.status_var.set("Generando estimulos...")
        self.progress_var.set(20.0)
        
        def worker():
            try:
                res = subprocess.run([sys.executable, "scripts/gen_stimulus.py", str(samples)], capture_output=True, text=True, check=True)
                self.append_script_log(f"--- Generar Estimulos ({samples} muestras) ---\n" + res.stdout + "\n" + (res.stderr if res.stderr else ""))
                self.root.after(0, lambda: self.status_var.set(f"✓ Estimulos generados: {samples} muestras."))
                self.root.after(0, lambda: self.progress_var.set(100.0))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Fallo al generar estimulos: {e}"))
                self.root.after(0, lambda: self.status_var.set("Error al generar estimulos."))
                self.root.after(0, lambda: self.progress_var.set(0.0))
                
        threading.Thread(target=worker, daemon=True).start()

    def start_stream_thread(self):
        if self.is_capturing:
            self.is_capturing = False
            return
            
        port = self.port_var.get()
        if not port:
            messagebox.showerror("Error", "Por favor selecciona un puerto COM valido.")
            return
            
        try:
            baud = int(self.baud_var.get())
        except ValueError:
            messagebox.showerror("Error", "La velocidad en baudios debe ser un numero entero.")
            return
            
        self.is_capturing = True
        self.btn_stream.config(text="Cancelar Streaming", style="TButton")
        self.status_var.set("Iniciando Streaming en tiempo real por UART...")
        
        t = threading.Thread(target=self.capture_stream, args=(port, baud), daemon=True)
        t.start()

    def capture_stream(self, port, baud):
        CMD_STREAM = 0x03
        CMD_BYPASS = 0x04
        noise_path = "sim/data/noise.bin"
        
        op_mode = self.op_mode_var.get()
        cmd_to_send = CMD_STREAM if op_mode == "Normal" else CMD_BYPASS
        
        self.last_frames = []
        self.root.after(0, lambda: self.write_to_monitor("Monitor UART: Iniciando streaming y esperando datos..."))
        
        if not os.path.exists(noise_path):
            self.root.after(0, lambda: messagebox.showerror("Error de Archivo", f"No se encuentra el archivo de estimulo '{noise_path}'. Usa 'Generar Estimulos' primero."))
            self.root.after(0, self.reset_stream_ui)
            return
            
        # Leer las muestras del archivo noise.bin (texto binario de 0s y 1s de 16-bit)
        try:
            samples = []
            with open(noise_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("//"):
                        continue
                    val = int(line, 2)
                    if val >= (1 << 15):
                        val = val - (1 << 16)
                    samples.append(val)
            samples = np.array(samples, dtype=np.int16)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error de Lectura", f"Error al procesar '{noise_path}': {e}"))
            self.root.after(0, self.reset_stream_ui)
            return
            
        try:
            target_samples = int(self.samples_var.get())
        except ValueError:
            target_samples = 4096
            
        target_samples = min(target_samples, len(samples))
        
        try:
            ser = serial.Serial(port, baud, timeout=0.5)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error de Puerto", f"No se pudo abrir el puerto {port}: {e}"))
            self.root.after(0, self.reset_stream_ui)
            return

        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # Enviar comando de inicio (CMD_STREAM = 0x03 o CMD_BYPASS = 0x04)
        ser.write(bytes([cmd_to_send]))
        ser.flush()
        
        # Pausa para dar tiempo a la FPGA a pasar de estado
        time.sleep(0.01)
        
        lpf_samples = []
        hpf_samples = []
        
        start_time = time.time()
        
        for idx in range(target_samples):
            if not self.is_capturing:
                break
                
            # Convertir muestra a 16-bit unsigned (complemento a dos)
            s_val = int(samples[idx])
            if s_val < 0:
                s_val += 65536
                
            # Enviar trama de 4 bytes: [0xAA, MSB, LSB, 0x55]
            tx_bytes = bytes([0xAA, (s_val >> 8) & 0xFF, s_val & 0xFF, 0x55])
            ser.write(tx_bytes)
            ser.flush()
            
            # Recibir trama de 8 bytes de respuesta con ventana deslizante para sincronismo
            buffer = bytearray()
            frame_found = False
            t_sample_start = time.time()
            
            while time.time() - t_sample_start < 0.2: # timeout de 200 ms por muestra
                if ser.in_waiting > 0:
                    b = ser.read(1)
                    buffer.extend(b)
                    if len(buffer) >= 8:
                        if buffer[0] == 0xAA and buffer[7] == 0x55:
                            val_lpf = (buffer[1] << 16) | (buffer[2] << 8) | buffer[3]
                            val_hpf = (buffer[4] << 16) | (buffer[5] << 8) | buffer[6]
                            lpf_samples.append(val_lpf)
                            hpf_samples.append(val_hpf)
                            frame_found = True
                            
                            # Actualizar el monitor en vivo con las ultimas tramas
                            if idx % 15 == 0:
                                frame_bytes = list(buffer)
                                self.last_frames.append(frame_bytes)
                                if len(self.last_frames) > 30: # Mantener las ultimas 30 tramas
                                    self.last_frames.pop(0)
                                if self.mon_mode_var.get() == "UART":
                                    self.root.after(0, self.update_monitor_view)
                                
                            break
                        else:
                            buffer.pop(0)
                else:
                    time.sleep(0.0001)
                    
            if not frame_found:
                self.root.after(0, lambda: self.status_var.set("Error: Timeout de trama en Streaming UART."))
                break
                
            # Actualizar progreso periodicamente
            if (idx + 1) % 100 == 0 or (idx + 1) == target_samples:
                pct = ((idx + 1) / target_samples) * 100.0
                elapsed = time.time() - start_time
                rate = (idx + 1) / elapsed if elapsed > 0 else 0
                self.root.after(0, lambda p=pct, c=(idx + 1), t=target_samples, r=rate: 
                    self.status_var.set(f"Procesadas {c:,}/{t:,} muestras ({r:.1f} m/s)..."))
                self.progress_var.set(pct)
                
        ser.close()
        self.is_capturing = False
        
        if len(lpf_samples) > 0:
            # Guardar resultados en captures/
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            os.makedirs(self.capture_dir, exist_ok=True)
            
            lpf_path = os.path.join(self.capture_dir, f"capture_{ts}_lpf.txt")
            hpf_path = os.path.join(self.capture_dir, f"capture_{ts}_hpf.txt")
            
            with open(lpf_path, "w") as f:
                f.write(f"// Streaming UART Woofer LPF - {ts} - {len(lpf_samples)} muestras - Modo: {op_mode}\n")
                for val in lpf_samples:
                    f.write(f"{val:06X}\n")
                    
            with open(hpf_path, "w") as f:
                f.write(f"// Streaming UART Tweeter HPF - {ts} - {len(hpf_samples)} muestras - Modo: {op_mode}\n")
                for val in hpf_samples:
                    f.write(f"{val:06X}\n")
                    
            self.active_capture_lpf = lpf_path
            self.active_capture_hpf = hpf_path
            
            self.root.after(0, lambda: self.status_var.set(f"Streaming completado: {len(lpf_samples)} muestras procesadas fisicamente en modo {op_mode}."))
            self.root.after(0, self.refresh_captures)
            self.root.after(0, self.update_plot)
        else:
            self.root.after(0, lambda: self.status_var.set("Error: No se procesaron muestras en streaming."))
            
        self.root.after(0, self.reset_stream_ui)

    def reset_stream_ui(self):
        self.btn_stream.config(text="Iniciar Filtrado (Streaming UART)", style="Accent.TButton")
        self.progress_var.set(0.0)
        self.is_capturing = False

    def load_hex_file(self, filepath, bits=24, base=16):
        if not os.path.exists(filepath):
            return None
        vals = []
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("//"):
                    continue
                val = int(line, base)
                # Complemento a dos de N bits
                if val >= (1 << (bits - 1)):
                    val = val - (1 << bits)
                vals.append(val)
        return np.array(vals, dtype=np.int32)

    def load_coeffs(self, filepath):
        if not os.path.exists(filepath):
            return None
        coeffs = []
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("//"):
                    continue
                val = int(line, 16)
                if val >= (1 << 39):
                    val = val - (1 << 40)
                # Convertir de Q4.36 a float
                coeffs.append(val / (2**36))
        return coeffs

    def _apply_visibility(self):
        """Aplica el estado de los checkboxes a las lineas ya dibujadas (sin redibujar todo)."""
        mapping = {
            "lpf_teorica": self.vis_lpf_teorica,
            "hpf_teorica": self.vis_hpf_teorica,
            "lpf_obs":     self.vis_lpf_obs,
            "hpf_obs":     self.vis_hpf_obs,
            "input_noise": self.vis_input_noise,
        }
        for key, var in mapping.items():
            if key in self._plot_lines:
                self._plot_lines[key].set_visible(var.get())
        # Actualizar leyenda (solo muestra las visibles)
        handles = [l for l in self.ax.get_lines() if l.get_visible() and l.get_label() and not l.get_label().startswith("_")]
        self.ax.legend(handles=handles, loc="lower left",
                       facecolor=self.panel_bg, edgecolor=self.highlight_color,
                       labelcolor=self.text_color)
        self.canvas.draw_idle()

    def update_plot(self):
        # Limpiar grafico y referencias de lineas previas
        self.ax.clear()
        self._plot_lines = {}
        self.ax.set_facecolor(self.panel_bg)

        fs = self.FS
        NPERSEG = 1024  # Resolucion espectral Welch

        # ── 1. Respuesta TEORICA a partir de coeficientes ─────────────────────
        coeff_lpf_path = "sim/data/coeff_lpf_48k.txt"
        coeff_hpf_path = "sim/data/coeff_hpf_48k.txt"
        db_lpf_teorica = db_hpf_teorica = w_teorica = None

        if os.path.exists(coeff_lpf_path):
            c_lpf = self.load_coeffs(coeff_lpf_path)
            b_lpf = c_lpf[0:3]
            a_lpf = [1.0, -c_lpf[3], -c_lpf[4]]
            w_teorica, h_lpf_s = signal.freqz(b_lpf, a_lpf, worN=2048, fs=fs)
            h_lpf_teorica = h_lpf_s * h_lpf_s  # 2 biquads en cascada -> LR4
            db_lpf_teorica = 20 * np.log10(np.abs(h_lpf_teorica) + 1e-15)

        if os.path.exists(coeff_hpf_path):
            c_hpf = self.load_coeffs(coeff_hpf_path)
            b_hpf = c_hpf[0:3]
            a_hpf = [1.0, -c_hpf[3], -c_hpf[4]]
            _, h_hpf_s = signal.freqz(b_hpf, a_hpf, worN=2048, fs=fs)
            h_hpf_teorica = h_hpf_s * h_hpf_s
            db_hpf_teorica = 20 * np.log10(np.abs(h_hpf_teorica) + 1e-15)

        if db_lpf_teorica is not None:
            line, = self.ax.semilogx(w_teorica, db_lpf_teorica,
                label="Teorica LPF (Woofer)", color="#4E88FF",
                linestyle="--", linewidth=2.5, alpha=0.85,
                visible=self.vis_lpf_teorica.get())
            self._plot_lines["lpf_teorica"] = line
        if db_hpf_teorica is not None:
            line, = self.ax.semilogx(w_teorica, db_hpf_teorica,
                label="Teorica HPF (Tweeter)", color="#FF6E6E",
                linestyle="--", linewidth=2.5, alpha=0.85,
                visible=self.vis_hpf_teorica.get())
            self._plot_lines["hpf_teorica"] = line

        # ── 2. Datos OBSERVADOS (FPGA captura o RTL sim) ───────────────────────
        r_lpf = r_hpf = r_in = None
        data_source_label = ""

        if self.active_capture_lpf and os.path.exists(self.active_capture_lpf):
            r_lpf = self.load_hex_file(self.active_capture_lpf)
            r_hpf = self.load_hex_file(self.active_capture_hpf)
            ts_label = os.path.basename(self.active_capture_lpf) \
                           .replace("capture_", "").replace("_lpf.txt", "")
            data_source_label = f"FPGA - {ts_label}"
        elif os.path.exists("sim/data/output_lpf_rtl.txt"):
            # En la simulacion RTL, las muestras se guardan en binario (0s y 1s)
            r_lpf = self.load_hex_file("sim/data/output_lpf_rtl.txt", base=2)
            r_hpf = self.load_hex_file("sim/data/output_hpf_rtl.txt", base=2)
            data_source_label = "RTL Sim (ModelSim)"

        if r_lpf is not None and len(r_lpf) > 128:
            # Estimulo de entrada (ruido blanco, 16 bits)
            r_in = self.load_hex_file("sim/data/stimulus_hex.txt", bits=16)
            
            # Alinear longitudes para evitar discrepancias de nperseg en Welch
            if r_in is not None and len(r_in) > 128:
                min_len = min(len(r_lpf), len(r_in))
                r_lpf = r_lpf[:min_len]
                r_hpf = r_hpf[:min_len]
                r_in = r_in[:min_len]
            else:
                min_len = len(r_lpf)
                
            # Ajustar nperseg dinamicamente si la senal es mas corta que NPERSEG
            nperseg_act = min(NPERSEG, min_len)

            # Normalizar salidas de 24 bits (complemento a 2, escala a [-1, 1])
            r_lpf_norm = r_lpf / 8388608.0
            r_hpf_norm = r_hpf / 8388608.0

            # Analisis Welch de salidas
            f_out, psd_lpf = signal.welch(r_lpf_norm, fs, nperseg=nperseg_act)
            _,     psd_hpf = signal.welch(r_hpf_norm, fs, nperseg=nperseg_act)
            db_lpf_obs = 10 * np.log10(psd_lpf + 1e-15)
            db_hpf_obs = 10 * np.log10(psd_hpf + 1e-15)

            mode = self.mode_var.get()
            db_in_plot = None

            if mode == "TF" and r_in is not None:
                # ── Modo TF: H(f) = PSD_out - PSD_in  ────────────────────────
                r_in_norm = r_in / 32768.0
                f_in, psd_in = signal.welch(r_in_norm, fs, nperseg=nperseg_act)
                db_in_raw = 10 * np.log10(psd_in + 1e-15)

                db_lpf_plot = db_lpf_obs - db_in_raw
                db_hpf_plot = db_hpf_obs - db_in_raw

                # Normalizar al 0 dB de cada banda de paso
                db_lpf_plot -= np.max(db_lpf_plot[:50])
                db_hpf_plot -= np.max(db_hpf_plot[-50:])

                # Entrada plana -> 0 dB por definicion de H(f)
                db_in_plot = np.zeros_like(f_in)

                y_label = "|H(f)| - Funcion de Transferencia (dB)"
                title   = f"Funcion de Transferencia - {data_source_label}  |  Fs = {fs:,} Hz"
            else:
                # ── Modo PSD: espectros sin normalizar por entrada ─────────────
                offset = -np.max(db_lpf_obs)
                db_lpf_plot = db_lpf_obs + offset
                db_hpf_plot = db_hpf_obs + offset

                if r_in is not None:
                    r_in_norm = r_in / 32768.0
                    f_in, psd_in = signal.welch(r_in_norm, fs, nperseg=nperseg_act)
                    db_in_raw = 10 * np.log10(psd_in + 1e-15)
                    db_in_plot = db_in_raw + offset  # misma escala que salidas
                else:
                    f_in = f_out
                    db_in_plot = None

                y_label = "PSD Normalizada (dB)"
                title   = f"Espectro Welch - {data_source_label}  |  Fs = {fs:,} Hz"

            # ── 3. Senal de ENTRADA (ruido blanco) ────────────────────────────
            if db_in_plot is not None:
                line, = self.ax.semilogx(
                    f_in, db_in_plot,
                    label="Entrada (Ruido Blanco)", color="#A0A0A0",
                    linestyle=":", linewidth=1.5, alpha=0.75,
                    visible=self.vis_input_noise.get())
                self._plot_lines["input_noise"] = line

            # ── 4. Salidas observadas ─────────────────────────────────────────
            line, = self.ax.semilogx(
                f_out, db_lpf_plot,
                label=f"Woofer LPF ({data_source_label})", color="#0052D9",
                linewidth=2.0, visible=self.vis_lpf_obs.get())
            self._plot_lines["lpf_obs"] = line

            line, = self.ax.semilogx(
                f_out, db_hpf_plot,
                label=f"Tweeter HPF ({data_source_label})", color="#D9001B",
                linewidth=2.0, visible=self.vis_hpf_obs.get())
            self._plot_lines["hpf_obs"] = line

            # Guardar PNG
            os.makedirs("doc/plots", exist_ok=True)
            plt.savefig("doc/plots/crossover_response.png", dpi=300, facecolor=self.bg_color)
            self.status_var.set(f"Grafico actualizado ({data_source_label}) -> doc/plots/crossover_response.png")
        else:
            self.ax.text(0.5, 0.5,
                "Sin muestras observadas.\nUsa 'Iniciar Filtrado (Streaming UART)' para leer de la Tang Nano 9K.",
                color=self.text_color, ha="center", va="center",
                fontsize=12, transform=self.ax.transAxes)
            y_label = "Magnitud (dB)"
            title   = f"Esperando Datos...  |  Fs = {fs:,} Hz"

        # ── Decoracion del eje ────────────────────────────────────────────────
        try:
            fc_val_plot = float(self.fc_var.get())
        except ValueError:
            fc_val_plot = 2000.0
        self.ax.axvline(fc_val_plot, color="#FFB347", linestyle=":", linewidth=1.2,
                        label=f"Fc = {fc_val_plot/1000.0:.2f} kHz", zorder=2)

        octave_freqs  = [20, 31.25, 62.5, 125, 250, 500, 1000, 2000, 4000, 8000, 16000, 20000]
        octave_labels = ["20", "31",  "63",  "125","250","500","1k", "2k", "4k",  "8k",  "16k",  "20k"]
        self.ax.set_xscale("log")
        self.ax.set_xticks(octave_freqs)
        self.ax.set_xticklabels(octave_labels)
        self.ax.tick_params(colors=self.text_color)

        self.ax.set_title(title, color=self.text_color, fontsize=11, fontweight="bold")
        self.ax.set_xlabel("Frecuencia (Hz) - Escala de Octavas ISO 266", color=self.text_color)
        self.ax.set_ylabel(y_label, color=self.text_color)
        self.ax.grid(True, which="both", ls="-", color="#3A3A4A", alpha=0.6)
        self.ax.set_xlim(20, 22000)
        self.ax.set_ylim(-60, 5)

        # Leyenda - solo lineas visibles
        handles = [l for l in self.ax.get_lines()
                   if l.get_visible() and l.get_label() and not l.get_label().startswith("_")]
        self.ax.legend(handles=handles, loc="lower left",
                       facecolor=self.panel_bg, edgecolor=self.highlight_color,
                       labelcolor=self.text_color, fontsize=9)

        self.canvas.draw()

    def run_golden_model_gui(self):
        fc_val = self.fc_var.get().strip()
        try:
            fc_float = float(fc_val)
            if fc_float <= 0 or fc_float >= 24000:
                messagebox.showerror("Error de Rango", "La frecuencia de corte debe estar entre 0 y 24000 Hz (excluidos).")
                return
        except ValueError:
            messagebox.showerror("Error de Entrada", "La frecuencia de corte debe ser un numero decimal valido.")
            return

        self.status_var.set("Ejecutando Golden Model...")
        self.progress_var.set(20.0)
        
        def worker():
            try:
                # Ejecutar scripts/calc_coefficients.py primero
                res_c = subprocess.run([sys.executable, "scripts/calc_coefficients.py", fc_val], capture_output=True, text=True)
                self.append_script_log("--- Calcular Coeficientes ---\n" + res_c.stdout + "\n" + (res_c.stderr if res_c.stderr else ""))
                
                if res_c.returncode == 2:
                    self.root.after(0, lambda: messagebox.showerror("Filtro Inestable", "¡Advertencia! Los coeficientes cuantizados en formato Q4.36 resultan en un filtro INESTABLE (algun polo >= 1.0).\n\nPor favor, elija otra frecuencia de corte."))
                    self.root.after(0, lambda: self.status_var.set("Error: Filtro cuantizado inestable."))
                    self.root.after(0, lambda: self.progress_var.set(0.0))
                    return
                elif res_c.returncode != 0:
                    self.root.after(0, lambda: messagebox.showerror("Error", f"Error al calcular coeficientes:\n{res_c.stderr}"))
                    self.root.after(0, lambda: self.status_var.set("Error al calcular coeficientes."))
                    self.root.after(0, lambda: self.progress_var.set(0.0))
                    return
                
                self.progress_var.set(50.0)
                
                # Ejecutar scripts/golden_model.py
                res_g = subprocess.run([sys.executable, "scripts/golden_model.py", fc_val], capture_output=True, text=True, check=True)
                self.append_script_log("--- Golden Model ---\n" + res_g.stdout + "\n" + (res_g.stderr if res_g.stderr else ""))
                
                self.root.after(0, lambda: self.status_var.set("✓ Golden Model completado con exito."))
                self.root.after(0, lambda: self.progress_var.set(100.0))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Fallo al ejecutar Golden Model: {e}"))
                self.root.after(0, lambda: self.status_var.set("Error en Golden Model."))
                self.root.after(0, lambda: self.progress_var.set(0.0))
                
        threading.Thread(target=worker, daemon=True).start()

    def run_simulation_gui(self):
        self.status_var.set("Ejecutando simulacion RTL en ModelSim...")
        self.progress_var.set(30.0)
        
        def worker():
            try:
                # Ejecutar scripts/simular.ps1 con powershell en modo NoGui
                cmd = ["powershell", "-File", "scripts/simular.ps1", "-Module", "top_crossover", "-NoGui"]
                res = subprocess.run(cmd, capture_output=True, text=True, check=True)
                self.append_script_log("--- Simulacion RTL (ModelSim) ---\n" + res.stdout + "\n" + (res.stderr if res.stderr else ""))
                
                self.root.after(0, lambda: self.status_var.set("✓ Simulacion RTL completada con exito."))
                self.root.after(0, lambda: self.progress_var.set(100.0))
                self.root.after(0, self.update_plot)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Fallo al ejecutar simulacion RTL: {e}"))
                self.root.after(0, lambda: self.status_var.set("Error en simulacion RTL."))
                self.root.after(0, lambda: self.progress_var.set(0.0))
                
        threading.Thread(target=worker, daemon=True).start()

    def run_complete_flow_gui(self):
        try:
            samples = int(self.samples_var.get())
        except ValueError:
            samples = 4096

        fc_val = self.fc_var.get().strip()
        try:
            fc_float = float(fc_val)
            if fc_float <= 0 or fc_float >= 24000:
                messagebox.showerror("Error de Rango", "La frecuencia de corte debe estar entre 0 y 24000 Hz (excluidos).")
                return
        except ValueError:
            messagebox.showerror("Error de Entrada", "La frecuencia de corte debe ser un numero decimal valido.")
            return
            
        self.status_var.set("Iniciando flujo completo (Generacion -> Coeficientes -> Golden -> Simulacion)...")
        self.progress_var.set(10.0)
        
        def worker():
            try:
                # 1. Generar Estimulos
                self.root.after(0, lambda: self.status_var.set("1/4 Generando estimulos..."))
                res_s = subprocess.run([sys.executable, "scripts/gen_stimulus.py", str(samples)], capture_output=True, text=True, check=True)
                self.append_script_log(f"--- Generar Estimulos ({samples} muestras) ---\n" + res_s.stdout + "\n" + (res_s.stderr if res_s.stderr else ""))
                self.progress_var.set(25.0)
                
                # 2. Calcular Coeficientes
                self.root.after(0, lambda: self.status_var.set("2/4 Calculando coeficientes..."))
                res_c = subprocess.run([sys.executable, "scripts/calc_coefficients.py", fc_val], capture_output=True, text=True)
                self.append_script_log("--- Calcular Coeficientes ---\n" + res_c.stdout + "\n" + (res_c.stderr if res_c.stderr else ""))
                
                if res_c.returncode == 2:
                    self.root.after(0, lambda: messagebox.showerror("Filtro Inestable", "¡Advertencia! Los coeficientes cuantizados en formato Q4.36 resultan en un filtro INESTABLE (algun polo >= 1.0).\n\nPor favor, elija otra frecuencia de corte."))
                    self.root.after(0, lambda: self.status_var.set("Error: Filtro cuantizado inestable."))
                    self.root.after(0, lambda: self.progress_var.set(0.0))
                    return
                elif res_c.returncode != 0:
                    self.root.after(0, lambda: messagebox.showerror("Error", f"Error al calcular coeficientes:\n{res_c.stderr}"))
                    self.root.after(0, lambda: self.status_var.set("Error al calcular coeficientes."))
                    self.root.after(0, lambda: self.progress_var.set(0.0))
                    return
                
                self.progress_var.set(50.0)
                
                # 3. Golden Model
                self.root.after(0, lambda: self.status_var.set("3/4 Ejecutando Golden Model..."))
                res_g = subprocess.run([sys.executable, "scripts/golden_model.py", fc_val], capture_output=True, text=True, check=True)
                self.append_script_log("--- Golden Model ---\n" + res_g.stdout + "\n" + (res_g.stderr if res_g.stderr else ""))
                self.progress_var.set(75.0)
                
                # 4. Simulacion ModelSim
                self.root.after(0, lambda: self.status_var.set("4/4 Ejecutando simulacion RTL..."))
                cmd = ["powershell", "-File", "scripts/simular.ps1", "-Module", "top_crossover", "-NoGui"]
                res_sim = subprocess.run(cmd, capture_output=True, text=True, check=True)
                self.append_script_log("--- Simulacion RTL (ModelSim) ---\n" + res_sim.stdout + "\n" + (res_sim.stderr if res_sim.stderr else ""))
                
                self.root.after(0, lambda: self.status_var.set("✓ Flujo completo de simulacion finalizado."))
                self.root.after(0, lambda: self.progress_var.set(100.0))
                self.root.after(0, self.update_plot)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Fallo en el flujo de simulacion: {e}"))
                self.root.after(0, lambda: self.status_var.set("Error en el flujo de simulacion."))
                self.root.after(0, lambda: self.progress_var.set(0.0))
                
        threading.Thread(target=worker, daemon=True).start()

    def write_to_monitor(self, text):
        self.txt_monitor.config(state="normal")
        self.txt_monitor.delete("1.0", tk.END)
        self.txt_monitor.insert(tk.END, text)
        self.txt_monitor.config(state="disabled")
        self.txt_monitor.see(tk.END)

    def update_monitor_view(self):
        mode = self.mon_mode_var.get()
        if mode == "UART":
            if self.last_frames:
                lines = []
                for f in self.last_frames:
                    lines.append(" ".join(f"{b:02X}" for b in f))
                monitor_text = "\n".join(lines)
            else:
                monitor_text = "Esperando transmision UART..."
            self.write_to_monitor(monitor_text)
        elif mode == "MODELSIM":
            log_path = "sim/transcript.log"
            if os.path.exists(log_path):
                try:
                    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    lines = content.splitlines()
                    self.write_to_monitor("\n".join(lines[-100:]))
                except Exception as e:
                    self.write_to_monitor(f"Error al leer log de ModelSim: {e}")
            else:
                self.write_to_monitor("No se encuentra sim/transcript.log.")
        elif mode == "SCRIPTS":
            if hasattr(self, "scripts_log_accumulator") and self.scripts_log_accumulator:
                self.write_to_monitor(self.scripts_log_accumulator)
            else:
                self.write_to_monitor("No hay ejecuciones de scripts registradas aun.")

    def append_script_log(self, text):
        if not hasattr(self, "scripts_log_accumulator"):
            self.scripts_log_accumulator = ""
        # Limitar tamano del acumulador a 50KB
        if len(self.scripts_log_accumulator) > 50000:
            self.scripts_log_accumulator = self.scripts_log_accumulator[-30000:]
        self.scripts_log_accumulator += text + "\n"
        if self.mon_mode_var.get() == "SCRIPTS":
            self.update_monitor_view()

def main():
    # Habilitar soporte High DPI en Windows
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2) # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    root = tk.Tk()
    app = CrossoverGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
