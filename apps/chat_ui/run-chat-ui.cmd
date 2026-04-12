@echo off
setlocal
cd /d "%~dp0"
call powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\..\scripts\assert-runtime-root.ps1"
if errorlevel 1 exit /b %errorlevel%
if not exist "node_modules" (
  echo Installing chat UI dependencies...
  call npm install
)
npm run dev
