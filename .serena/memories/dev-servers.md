# Development Servers

## Running Both Backend and ADK Web Services

Both services use port 8000 by default, so they need different ports when running simultaneously.

### Backend Server (FastAPI)
- **Port**: 8000
- **URL**: http://localhost:8000
- **Command** (from project root):
  ```bash
  source .venv/bin/activate && python -m backend.server
  ```

### ADK Web Interface (Debugging)
- **Port**: 8001
- **URL**: http://localhost:8001
- **Command** (from backend directory):
  ```bash
  source ../.venv/bin/activate && adk web --port 8001 revive_agent
  ```

### Quick Start (Both Services)

```bash
# Terminal 1: Backend server (from project root)
source .venv/bin/activate && python -m backend.server
# Runs on http://localhost:8000

# Terminal 2: ADK web (from backend directory)
cd backend && source ../.venv/bin/activate && adk web --port 8001 revive_agent
# Runs on http://localhost:8001
```

### Checking Running Services
```bash
lsof -i :8000 -i :8001 | grep LISTEN
```
