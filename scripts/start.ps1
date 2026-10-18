$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
$backendPython = Join-Path $projectPath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $backendPython)) { throw 'Run scripts\setup.ps1 first.' }
Set-Location -LiteralPath $projectPath
# Background helpers are hidden; the browser is opened explicitly for interaction.
$backendProcess = Start-Process -FilePath $backendPython -ArgumentList '-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $projectPath -WindowStyle Hidden -PassThru
$frontendPath = Join-Path $projectPath 'frontend'
$frontendCommand = 'Set-Location -LiteralPath ''' + $frontendPath.Replace("'", "''") + '''; npm.cmd run dev'
$frontendProcess = Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile','-Command',$frontendCommand -WindowStyle Hidden -PassThru
try {
    Write-Host 'DataForge starting: http://127.0.0.1:5173'
    Write-Host 'Press Ctrl+C here to stop the backend. Frontend process ID:' $frontendProcess.Id
    Start-Sleep -Seconds 3
    Start-Process 'http://127.0.0.1:5173'
    Wait-Process -Id $backendProcess.Id
} finally {
    if (-not $backendProcess.HasExited) { Stop-Process -Id $backendProcess.Id -ErrorAction SilentlyContinue }
    # Stop the launched frontend process tree, not unrelated Node sessions.
    & taskkill.exe /PID $frontendProcess.Id /T /F 2>$null
}
