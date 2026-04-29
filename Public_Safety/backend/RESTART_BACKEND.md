# Backend Restart / Stable Start

Use this stable startup command on Windows to avoid Flask reloader/watchdog crashes:

```powershell
cd "C:\Users\inchara P\crowdmanagement\Public_Safety\backend"
.\.venv\Scripts\python.exe run_backend.py
```

## Default behavior

- `debug=False`
- `use_reloader=False`
- `host=127.0.0.1`
- `port=5000`

This is intentional for reliable local startup when heavy ML modules are imported.

## Optional overrides

```powershell
$env:BACKEND_DEBUG="1"
$env:BACKEND_USE_RELOADER="1"
$env:BACKEND_HOST="127.0.0.1"
$env:BACKEND_PORT="5000"
.\.venv\Scripts\python.exe run_backend.py
```
