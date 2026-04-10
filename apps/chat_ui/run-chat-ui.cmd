@echo off
setlocal
cd /d "%~dp0"
if not exist "node_modules" (
  echo Installing chat UI dependencies...
  call npm install
)
npm run dev
