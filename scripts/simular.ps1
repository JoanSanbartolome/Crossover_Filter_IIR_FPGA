<#
.SYNOPSIS
    Lanza ModelSim y compila/simula un modulo especifico desde la raiz del proyecto.
.DESCRIPTION
    Este script analiza el modulo especificado, busca un testbench asociado,
    y ejecuta ModelSim en la raiz del espacio de trabajo cargando el script 'sim/simular.tcl'.
.PARAMETER Module
    Nombre del modulo de diseno o del testbench a simular (ej: crossover_engine o tb_crossover_engine).
.PARAMETER NoGui
    Si esta presente, inicia ModelSim en modo consola batch (sin interfaz grafica).
    Por defecto se inicia con la interfaz grafica (GUI).
.EXAMPLE
    .\scripts\simular.ps1 -Module crossover_engine
    .\scripts\simular.ps1 -Module crossover_engine -NoGui
#>

param (
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Module,

    [Parameter(Mandatory = $false)]
    [switch]$NoGui
)

# Limpiar extensiones si el usuario pasa el nombre del archivo completo (ej: crossover_engine.sv)
$ModuleName = [System.IO.Path]::GetFileNameWithoutExtension($Module)

# Inicializar variables
$TargetModule = $ModuleName
$TargetTestbench = ""

# Determinar si el modulo ingresado ya es un testbench
$IsTestbench = $false
if ($ModuleName.StartsWith("tb_") -or $ModuleName.EndsWith("_tb") -or $ModuleName.EndsWith("_mock")) {
    $IsTestbench = $true
    $TargetTestbench = $ModuleName
    # Intentar deducir el modulo de diseno quitando prefijos/sufijos
    if ($ModuleName.StartsWith("tb_")) {
        $TargetModule = $ModuleName.Substring(3)
    } elseif ($ModuleName.EndsWith("_tb")) {
        $TargetModule = $ModuleName.Substring(0, $ModuleName.Length - 3)
    }
} else {
    # El usuario ingreso el modulo de diseno. Buscar su testbench asociado.
    $PosiblesTBs = @(
        "tb_$ModuleName",
        "${ModuleName}_tb",
        "${ModuleName}_mock"
    )

    $SimDir = Join-Path $PSScriptRoot "..\sim"
    $TsbDir = Join-Path $PSScriptRoot "..\tsb"

    foreach ($tb in $PosiblesTBs) {
        if (Test-Path (Join-Path $SimDir "$tb.sv")) {
            $TargetTestbench = $tb
            break
        }
        if (Test-Path (Join-Path $TsbDir "$tb.sv")) {
            $TargetTestbench = $tb
            break
        }
    }
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Iniciando Script de Simulacion Automatizada (Raiz)" -ForegroundColor Cyan
Write-Host " Modulo de Diseno: $TargetModule" -ForegroundColor Yellow
if ($TargetTestbench) {
    Write-Host " Testbench Elegido: $TargetTestbench" -ForegroundColor Green
} else {
    Write-Host " Testbench Elegido: [Ninguno encontrado, solo verificacion de compilacion]" -ForegroundColor Red
}
Write-Host "==========================================================" -ForegroundColor Cyan

try {
    # Ejecutamos vsim en la ubicacion actual (que debe ser la raiz del proyecto)
    # Redirigimos el log a 'sim/transcript.log' para mantener limpia la raiz.
    if (-not $NoGui) {
        Write-Host "Lanzando ModelSim GUI..." -ForegroundColor Gray
        vsim -l sim/transcript.log -do "do sim/simular.tcl $TargetModule $TargetTestbench"
    } else {
        Write-Host "Lanzando ModelSim en modo consola (Batch)..." -ForegroundColor Gray
        vsim -c -l sim/transcript.log -do "do sim/simular.tcl $TargetModule $TargetTestbench; quit -f"
    }
}
catch {
    Write-Error "Ocurrio un error al lanzar ModelSim: $_"
}
