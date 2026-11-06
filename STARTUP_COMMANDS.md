# Balbird Intelligence — Startup Commands Guide

This document contains the exact commands required to run the **Balbird Intelligence** full-stack application (Backend + Frontend) and how to handle port conflicts or background processes.

---

## Prerequisites Check

Before starting, ensure you have Python 3.12+ and Node.js 18+ installed:

```powershell
python --version
node --version
```

---

## 1. Quick Startup (Two Terminals)

Open two separate **PowerShell** windows:

### Terminal 1 — Backend (FastAPI + Supabase + OpenRouter)

```powershell
cd C:\Programming\EmailSeg\backend
$env:PYTHONPATH="C:\Programming\EmailSeg\backend"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

* **Backend Base URL:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
* **Interactive Swagger API Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **Health Check:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

### Terminal 2 — Frontend (React 19 + TypeScript + Vite)

```powershell
cd C:\Programming\EmailSeg\frontend
npm run dev
```

* **Frontend Web Application:** [http://localhost:5173](http://localhost:5173)

---

## 2. One-Liner Startup Script (Optional)

If you prefer to start both with a single PowerShell script, create a file named `run_all.ps1` in the project root:

```powershell
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Programming\EmailSeg\backend; `$env:PYTHONPATH='C:\Programming\EmailSeg\backend'; python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Programming\EmailSeg\frontend; npm run dev"
```

Then run:
```powershell
.\run_all.ps1
```

---

## 3. Useful Commands & Troubleshooting

### Port 8000 Already in Use Error (`[WinError 10013]`)

If port 8000 is occupied by another process, find and kill it:

```powershell
# 1. Find process ID using port 8000
netstat -ano | findstr :8000

# 2. Kill the process (replace <PID> with number from rightmost column)
taskkill /F /PID <PID>
```

*Alternative:* Run on port 8001:
```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

### Run Automated Test Suites

```powershell
cd C:\Programming\EmailSeg
python -m pytest backend/tests -v
```

### Re-seed Demo Data into Supabase

If you ever need to reset or re-seed the initial operational dataset into Supabase:

```powershell
cd C:\Programming\EmailSeg
$env:PYTHONPATH="C:\Programming\EmailSeg\backend"
python backend\scripts\seed_demo_data.py
```

### Rebuild Frontend Production Bundle

```powershell
cd C:\Programming\EmailSeg\frontend
npm run build
```
