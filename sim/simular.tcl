#=============================================================================
# Archivo   : simular.tcl
# Proyecto  : Filtro Crossover IIR - Tang Nano 9K
# Autor     : Joan (via Antigravity)
# Descripcion:
#   Script Tcl maestro para ModelSim. Disenado para ejecutarse desde la raiz
#   del proyecto. Compila el paquete global, el diseno RTL, los mocks y el 
#   testbench. Luego inicia la simulacion y carga las ondas.
#=============================================================================

# Obtener argumentos pasados al comando 'do'
# $1 -> Nombre del modulo a probar (ej: crossover_engine)
# $2 -> Nombre del testbench (ej: tb_crossover_engine)
set modulo ""
set testbench ""

if {$argc > 0} {
    set modulo $1
}
if {$argc > 1} {
    set testbench $2
}

echo "=========================================================="
echo " Starting ModelSim Compilation and Simulation Flow"
echo " Working Directory: [pwd]"
echo " Target Module    : $modulo"
echo " Target Testbench : $testbench"
echo "=========================================================="

# 1. Crear biblioteca de trabajo en 'sim/work' para no ensuciar la raiz
if {![file exists sim/work]} {
    vlib sim/work
}
vmap work sim/work

# 2. Compilar paquete global (crossover_pkg.sv) primero
if {[file exists rtl/pkg/crossover_pkg.sv]} {
    echo "Compilando paquete global..."
    vlog -sv -work work rtl/pkg/crossover_pkg.sv
}

# 3. Compilar todos los archivos RTL (.sv) para resolver dependencias
echo "Compilando codigo RTL de diseno..."
vlog -sv -work work rtl/*.sv

# 4. Compilar mocks de simulacion y testbenches
echo "Compilando archivos de simulacion y testbenches..."
if {[file exists sim/sd_controller_mock.sv]} {
    vlog -sv -work work sim/sd_controller_mock.sv
}

# Buscar y compilar el testbench especifico
set tb_encontrado 0

if {$testbench != ""} {
    # Buscar en carpeta sim
    if {[file exists sim/$testbench.sv]} {
        vlog -sv -work work sim/$testbench.sv
        set tb_encontrado 1
    }
    # Buscar en carpeta tsb
    if {[file exists tsb/$testbench.sv]} {
        vlog -sv -work work tsb/$testbench.sv
        set tb_encontrado 1
    }
}

# 5. Iniciar la simulacion si se encontro el testbench
if {$tb_encontrado} {
    echo "Iniciando simulacion del testbench: work.$testbench"
    vsim -voptargs="+acc" work.$testbench
    
    # Configurar ventana de ondas (Wave)
    # Cargar archivo de ondas especifico si existe
    if {[file exists sim/wave_$modulo.do]} {
        echo "Cargando archivo de ondas especifico: sim/wave_$modulo.do"
        do sim/wave_$modulo.do
    } else {
        echo "No se encontro wave_$modulo.do. Agregando senales por defecto..."
        add wave -position insertpoint sim:/$testbench/*
    }
    
    # Ejecutar la simulacion
    echo "Ejecutando simulacion..."
    run -all
} else {
    echo "WARNING: No se especifico o no se encontro el testbench '$testbench'."
    echo "Solo se ha realizado la compilacion de verificacion."
}
