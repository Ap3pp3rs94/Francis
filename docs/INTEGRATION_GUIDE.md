# Integration Guide

## Requirements
- Python 3.11+
- Windows PowerShell (for scripts)
- Optional: `uv` for dependency management

## Install (recommended)
```powershell
cd D:\francis
uv venv
uv pip install -e .
```

## Run API
```powershell
python -m uvicorn francis.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

## Run CLI
```powershell
python -m francis
python -m francis healthcheck
```

## Run Tests
```powershell
python -m pytest D:\francis\tests
```

## Environment Notes
- `FRANCIS_ALLOWED_ORIGINS` controls CORS for the API.
- Logs and artifacts are written under `D:\francis\data\logs`.
