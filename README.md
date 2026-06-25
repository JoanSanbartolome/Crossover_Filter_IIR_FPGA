# Crossover Digital IIR - Tang Nano 9K

Este proyecto implementa un filtro Crossover digital IIR (Linkwitz-Riley de 4o orden, LR4) de 2 vias (Woofer LPF y Tweeter HPF) en SystemVerilog, optimizado para la placa de desarrollo **Tang Nano 9K** (Gowin GW1NR-9C).

---

## Diagrama de Bloques del Sistema

El siguiente diagrama de bloques muestra la arquitectura de hardware implementada en la FPGA, incluyendo el flujo de datos UART, el motor DSP del crossover, la FSM de control global y la FIFO de salida:

```mermaid
graph TD
    %% Estilos de Nodos
    classDef clk fill:#1F2A38,stroke:#4E88FF,stroke-width:1px,color:#F0F0F0;
    classDef fsm fill:#4A2E3D,stroke:#FF6E6E,stroke-width:1px,color:#F0F0F0;
    classDef dsp fill:#1A332B,stroke:#00FF66,stroke-width:1px,color:#F0F0F0;
    classDef uart fill:#2C3E50,stroke:#3498DB,stroke-width:1px,color:#F0F0F0;
    classDef memory fill:#4D3C2B,stroke:#E67E22,stroke-width:1px,color:#F0F0F0;

    %% Puertos Externos
    CLK["clk_sys (27 MHz)"] ::: clk
    RST["rst_n (Reset KEY1)"] ::: clk
    RXD["uart_rxd (Pin 18)"] ::: uart
    TXD["uart_txd (Pin 17)"] ::: uart
    LEDS["o_leds_n (LEDs 0-5)"] ::: clk

    %% Submodulos
    CLKGEN["clk_gen (Clock Generator)"] ::: clk
    UARTCTRL["uart_ctrl (UART Transceiver)"] ::: uart
    GFSM["FSM de Control Global"] ::: fsm
    RXFRAME["Logica de Encuadre RX (Ventana Deslizante)"] ::: fsm
    DSPENGINE["crossover_engine (Filtros IIR LR4)"] ::: dsp
    OUTFIFO["FIFO de Salida (48-bit, 256 muestras)"] ::: memory

    %% Conexiones de Reloj y Reset
    CLK --> CLKGEN
    CLK --> UARTCTRL
    CLK --> GFSM
    CLK --> RXFRAME
    CLK --> DSPENGINE
    CLK --> OUTFIFO
    RST --> CLKGEN
    RST --> UARTCTRL
    RST --> GFSM
    RST --> RXFRAME
    RST --> DSPENGINE
    RST --> OUTFIFO

    %% Flujo UART RX
    RXD --> UARTCTRL
    UARTCTRL -- "oc_rx_cmd, oc_rx_valid" --> GFSM
    UARTCTRL -- "oc_rx_cmd, oc_rx_valid" --> RXFRAME

    %% FSM y Control
    GFSM -- "streaming_mode_r" --> RXFRAME
    GFSM -- "bypass_mode_r" --> OUTFIFO
    GFSM -- "LED status" --> LEDS

    %% Procesamiento DSP
    RXFRAME -- "dsp_input_sample_s, dsp_input_valid_s" --> DSPENGINE
    RXFRAME -- "dsp_input_sample_s (Bypass)" --> OUTFIFO
    RXFRAME -- "rx_sync_error_r" --> LEDS

    %% Multiplexacion y FIFO
    DSPENGINE -- "woofer_sample_s, tweeter_sample_s, engine_output_valid_s" --> OUTFIFO
    OUTFIFO -- "out_fifo_empty_s, out_fifo_full_s" --> LEDS

    %% Flujo UART TX
    OUTFIFO -- "woofer_tx_s, tweeter_tx_s" --> UARTCTRL
    UARTCTRL -- "oc_tx_busy" --> OUTFIFO
    OUTFIFO -- "uart_tx_trigger_s" --> UARTCTRL
    UARTCTRL --> TXD
```

---

## Caracteristicas del Sistema

*   **Procesamiento de Audio de Alto Rendimiento:**
    *   Frecuencia de muestreo ($F_s$): 48 kHz.
    *   Datapath con precision de 24 bits con signo para las muestras de audio.
    *   Coeficientes cuantizados a formato de punto fijo **Q4.36** (40 bits con signo) para garantizar maxima estabilidad y minima distorsion por redondeo.
    *   Acumuladores internos de 72 bits para absorber el crecimiento de bits (bit growth) sin saturacion.
*   **Transmision UART en Tiempo Real:**
    *   Recepcion y transmision bidireccional mediante interfaz serie (UART) a **921,600 bps**.
    *   Banderas de control en tramas de datos para sincronizacion robusta de bytes.
    *   Modo Bypass de diagnostico para verificacion rapida del canal UART.

---

## Uso de Recursos en la Tang Nano 9K (Gowin GW1NR-9C)

Los recursos fisicos consumidos en la FPGA tras la sintesis con Gowin EDA son:

| Modulo / Entidad | Registros | ALUs | LUTs | Multiplicadores (18x18) | Bloques BSRAM |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **top_crossover** (Total) | **782** | **129** | **750** | **4** (1 Mult + 3 Mult-Add) | **2** |
| `u_crossover_engine` (DSP) | 624 | 72 | 514 | 4 (1 Mult + 3 Mult-Add) | 0 |
| `u_uart_ctrl` (UART) | 66 | 0 | 140 | 0 | 0 |
| Reloj, FIFO y Control | 92 | 57 | 96 | 0 | 2 |

---

## Mapeo de Pines Fisicos (tang_nano_9k.cst)

El mapeo de puertos del modulo top-level a los pines fisicos de la placa de desarrollo es:

| Puerto en HDL | Pin Fisico | Estandar I/O | Modo Pull | Descripcion / Componente |
| :--- | :---: | :---: | :---: | :--- |
| `clk_sys` | **52** | LVCMOS33 | NONE | Oscilador de cristal de 27 MHz |
| `rst_n` | **3** | LVCMOS18 | UP | Boton de reset fisico (KEY1) |
| `uart_txd` | **17** | LVCMOS33 | NONE | Transmision UART (Salida de la FPGA al puente CH552) |
| `uart_rxd` | **18** | LVCMOS33 | UP | Recepcion UART (Entrada a la FPGA desde el puente CH552) |
| `o_leds_n[0]` | **10** | LVCMOS18 | UP | LED 0 (Encendido si hay error de sincronismo UART) |
| `o_leds_n[1]` | **11** | LVCMOS18 | UP | LED 1 (Encendido en estado de espera IDLE) |
| `o_leds_n[2]` | **13** | LVCMOS18 | UP | LED 2 (Encendido en modo activo Streaming/Bypass) |
| `o_leds_n[3]` | **14** | LVCMOS18 | UP | LED 3 (Apagado en modo Bypass de diagnostico) |
| `o_leds_n[4]` | **15** | LVCMOS18 | UP | LED 4 (Encendido en caso de que la FIFO de salida este llena) |
| `o_leds_n[5]` | **16** | LVCMOS18 | UP | LED 5 (Latido / Heartbeat oscilante a ~0.8 Hz) |

*Nota: Los LEDs integrados en la Tang Nano 9K son activos bajo (se encienden al poner la salida a nivel bajo `0`).*

---

## Protocolo de Comunicacion UART

### Tramas de Datos (Handshake Serie)
*   **Trama de Bajada (PC -> FPGA - Entrada de Audio):**
    Consta de 4 bytes a 921,600 bps:
    `[0xAA, sample_msb, sample_lsb, 0x55]` (sample es una muestra de audio de 16 bits con signo).
*   **Trama de Subida (FPGA -> PC - Salida Filtrada):**
    Consta de 8 bytes a 921,600 bps:
    `[0xAA, woofer_b2, woofer_b1, woofer_b0, tweeter_b2, tweeter_b1, tweeter_b0, 0x55]` (las muestras del woofer y tweeter estan en formato de 24 bits con signo).

### Comandos de Operacion (1 Byte de Inicializacion)
Antes de enviar el flujo de audio, se debe transmitir un byte de comando a la FPGA:
*   `0x03` (**CMD_STREAM**): Inicia el procesamiento activo a traves de los filtros IIR.
*   `0x04` (**CMD_BYPASS**): Inicia el modo de diagnostico por bypass (las muestras de entrada de 16 bits se retransmiten directamente a 24 bits en la salida sin filtrar).

---

## Librerias de Python Requeridas

Para ejecutar la GUI y los scripts de validacion, es necesario instalar las siguientes librerias de Python:

```bash
pip install numpy scipy matplotlib pyserial
```

---

## Comandos de Verificacion y Simulacion

### 1. Ejecucion de la Interfaz Grafica (GUI)
Lanza la aplicacion grafica para controlar la placa, capturar datos y visualizar graficos Welch/TF:
```bash
python scripts/crossover_gui.py
```

### 2. Ejecucion del Flujo de Simulacion y Validacion RTL
Si deseas simular el diseno de hardware en ModelSim y validar la exactitud matematica del diseno RTL frente al modelo ideal:
1.  **Generar Estimulos:**
    ```bash
    python scripts/gen_stimulus.py 10000
    ```
2.  **Calcular Coeficientes y Comprobar Estabilidad:**
    ```bash
    python scripts/calc_coefficients.py 2000
    ```
3.  **Ejecutar Golden Model:**
    ```bash
    python scripts/golden_model.py 2000
    ```
4.  **Ejecutar Simulacion en ModelSim (Modo Consola):**
    ```powershell
    powershell -File scripts/simular.ps1 -Module top_crossover -NoGui
    ```
5.  **Ejecutar Analisis de Resultados:**
    ```bash
    python scripts/analyze_output.py
    ```

---

## Metricas de Calidad de Audio (Validacion Punto Fijo)

El modelo de referencia calcula la relacion senal a ruido de cuantizacion (**SQNR**) al cuantizar los coeficientes teoricos ideales a Q4.36 (40 bits):

*   **SQNR Canal LPF (Woofer):** **`82.36 dB`**
*   **SQNR Canal HPF (Tweeter):** **`99.35 dB`**

Esto garantiza una excelente relacion de fidelidad de audio libre de distorsiones armonicas apreciables, superando con creces las especificaciones fisicas de la mayoria de DACs comerciales de audio de consumo.

---

## Creditos y Agradecimientos

Este proyecto esta basado y adaptado a partir del diseno de crossover estereo para FPGA de:
*   [har-in-air/FPGA_STEREO_CROSSOVER](https://github.com/har-in-air/FPGA_STEREO_CROSSOVER)

