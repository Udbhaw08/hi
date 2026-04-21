# start_drishti.ps1
# Unified startup script for Drishti Surveillance System

Write-Host '🚀 Starting Drishti Multi-Service Environment...' -ForegroundColor Cyan

# 0. Cleanup existing processes on ports 5000, 5173, 8000, 8001
Write-Host '🧹 Cleaning up existing processes on ports 5000, 5173, 8000, 8001...' -ForegroundColor Yellow
$ports = 5000, 5173, 8000, 8001
foreach ($port in $ports) {
    $procId = (Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue).OwningProcess | Select-Object -Unique
    if ($procId) {
        Write-Host "Stopping process $procId on port $port..." -ForegroundColor Gray
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
}
sleep 1

# 1. Start MongoDB if not running
Write-Host '🔍 Checking MongoDB status...' -ForegroundColor Yellow
$mongoService = Get-Service -Name 'MongoDB' -ErrorAction SilentlyContinue
if ($mongoService) {
    if ($mongoService.Status -ne 'Running') {
        Write-Host '▶️ Starting MongoDB service...' -ForegroundColor Cyan
        Start-Service -Name 'MongoDB'
    } else {
        Write-Host '✅ MongoDB is already running.' -ForegroundColor Green
    }
} else {
    Write-Host '⚠️ MongoDB service not found. Attempting to start mongod process...' -ForegroundColor Red
    Start-Process -FilePath 'mongod' -ArgumentList '--dbpath ./data/db' -NoNewWindow
}

# 2. Start Main Backend (Port 8000)
Write-Host '📦 Starting Main Backend (Port 8000)...' -ForegroundColor Cyan
Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-Command", "python -m backend.main" -WindowStyle Minimized

# 3. Start Assistant Backend (Port 8001)
Write-Host '🤖 Starting Assistant Backend (Port 8001)...' -ForegroundColor Cyan
Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-Command", "cd ./drishti-assistant/vigil; uvicorn main:app --host 0.0.0.0 --port 8001" -WindowStyle Minimized

# 4. Start Detection System Backend (Port 5000)
Write-Host '🔍 Starting Detection System Backend (Port 5000)...' -ForegroundColor Cyan
Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-Command", "cd ./detection-system/backend; node server.js" -WindowStyle Minimized

# 5. Start Frontend (Port 5173 - Dev mode)
Write-Host '🌐 Starting Frontend (Vite)...' -ForegroundColor Green
Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-Command", "cd ./frontend; npm run dev" -WindowStyle Minimized

Write-Host '✨ All systems initialized.' -ForegroundColor Green
Write-Host '--------------------------------------------------' -ForegroundColor Gray
Write-Host 'Main UI:       http://localhost:5173' -ForegroundColor White
Write-Host 'Main API:      http://localhost:8000' -ForegroundColor White
Write-Host 'Assistant API: http://localhost:8001' -ForegroundColor White
Write-Host 'Detection API: http://localhost:5000' -ForegroundColor White
Write-Host '--------------------------------------------------' -ForegroundColor Gray
Write-Host 'Ready. (Services are running minimized in the taskbar)' -ForegroundColor Gray
