$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe  = Join-Path $ScriptDir ".venv\Scripts\python.exe"
$MainScript = Join-Path $ScriptDir "main.py"
$LogFile    = Join-Path $ScriptDir "data\tracker.log"
$TaskName   = "TCL_65C6K_PriceTracker"

New-Item -ItemType Directory -Force -Path (Join-Path $ScriptDir "data") | Out-Null

$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "`"$MainScript`"" `
    -WorkingDirectory $ScriptDir

$Trigger = New-ScheduledTaskTrigger -Daily -At "23:00"

$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -RestartCount 1 `
    -RestartInterval (New-TimeSpan -Minutes 10) `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "TCL 65C6K daily price scraper" `
    -Force

Write-Host "Tarea creada: $TaskName"
Write-Host "Se ejecutara todos los dias a las 23:00"
