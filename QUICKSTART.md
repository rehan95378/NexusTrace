# NexusTrace — Quickstart & Deployment Guide

## ⚡ Quick Start (Copy-Paste)

### Prerequisites
- Python 3.10+, Node.js 16+, Neo4j (or seed mode)

### Step 1: Backend Setup
```bash
cd /home/rehnx/Desktop/.R/S/backend
cp .env.example .env
# Edit .env: set JWT_SECRET, NEO4J_* credentials (or leave as-is for seed mode)
./venv/bin/python -m pip install -r requirements.txt
JWT_SECRET=dev ./venv/bin/python -m uvicorn app:app --reload --port 8000
```
**Expected:** `Uvicorn running on http://127.0.0.1:8000`

### Step 2: Frontend Setup (new terminal)
```bash
cd /home/rehnx/Desktop/.R/S/frontend
npm install
VITE_API_URL=http://localhost:8000 npm run dev
```
**Expected:** `Local: http://localhost:5173`

### Step 3: Open & Demo
1. Go to http://localhost:5173
2. **Sign Up:** any email/password (demo mode)
3. **Upload:** drag a CSV/JSON/PDF from `backend/data/raw/`
4. **View:** graph auto-loads, entities/relationships appear
5. **Explore:** click nodes, approve/reject anomalies

---

## 🚀 Deployment (Production)

### Option A: Local/Docker

```dockerfile
# Dockerfile (backend)
FROM python:3.10
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ .
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

```dockerfile
# Dockerfile (frontend)
FROM node:16 AS build
WORKDIR /app
COPY frontend/package*.json .
RUN npm install
COPY frontend/ .
RUN npm run build

FROM nginx:latest
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
```

### Option B: Cloud (Render/Railway/Vercel)

**Backend (Render):**
- Build: `pip install -r backend/requirements.txt`
- Start: `cd backend && gunicorn app:app --bind 0.0.0.0:$PORT`
- Env vars: `JWT_SECRET`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `GRAPH_MODE=neo4j`

**Frontend (Vercel):**
- Build: `cd frontend && npm run build`
- Output: `dist/`
- Env: `VITE_API_URL=https://your-backend-url.com`

---

## ✅ Pre-Demo Checklist

- [ ] Backend running on port 8000
- [ ] Frontend running on port 5173
- [ ] `.env` has `JWT_SECRET` set (not `CHANGE_ME`)
- [ ] Tests pass: `pytest test/ -q` → 40/40 ✓
- [ ] Pipeline runs: `JWT_SECRET=dev python -m pipeline.run_pipeline` → extracts entities ✓
- [ ] Auth page loads: http://localhost:5173
- [ ] Upload works: drag a file, see entities/relationships appear
- [ ] Graph renders: nodes visible, anomalies flagged red/purple
- [ ] Approve/reject works: graph updates live after action

---

## 📊 What Judges Will See (Demo Script)

1. **Auth Flow** (10s)
   - "Sign up as an investigator"
   - Create account, land on dashboard

2. **Upload & Extract** (30s)
   - "Here's a criminal FIR report (JSON)"
   - Drag `backend/data/raw/sample_fir.json` to upload panel
   - "System extracts 5 people, 2 locations, identifies key links"

3. **Graph Visualization** (20s)
   - "Each node is a suspect or location"
   - "Node size = how central they are in the network"
   - "Red border = high-centrality anomaly"
   - Click a node → detail panel shows centrality + anomaly flags

4. **Entity Breakdown** (15s)
   - Switch to "Entities" tab
   - "5 people extracted, deduplicated across documents"
   - Show confidence scores per entity

5. **Relationships** (15s)
   - Switch to "Relationships" tab
   - "2 high-confidence (FINANCIAL, FAMILY)"
   - "6 low-confidence (ASSOCIATION) routed to review queue"

6. **Analyst Workflow** (20s)
   - Switch to "Anomalies" tab
   - "Show flagged items: high-centrality Ramesh Kumar, cross-case phone"
   - "Investigator can approve → item enters main graph"
   - Upload another report, graph grows in real-time

7. **Close** (30s)
   - "No manual link-chasing. System surfaces hidden connections."
   - "Confidence-scored so investigators know what to trust."
   - "Handles fragmented data: FIR, CDR, PDF, all unified."

---

## 🔧 Troubleshooting

| Issue | Fix |
|---|---|
| `JWT_SECRET was never set` | Set `JWT_SECRET=something` in `.env` or shell |
| `NEO4J_USER mismatch` | Ensure `.env` uses `NEO4J_USER` (not `NEO4J_USERNAME`) |
| `cross_case_identifier never flags` | Seed mode analytics now on; upload 2 reports with same phone |
| Graph doesn't refresh after approve | Frontend now re-fetches on action (fixed) |
| Duplicate pipeline logic | Now uses shared `run_stages.py` (fixed) |
| Upload fails on large file | 10 MiB cap enforced; send smaller report |
| spaCy very slow | Model now cached; first call slow, rest fast (fixed) |

---

## 📚 Key Files

**Backend:**
- `app.py` — FastAPI entrypoint (has JWT security check)
- `api/config.py` — loads `.env` via `load_dotenv()`
- `api/graph_service.py` — graph queries + `promote()` + `_recompute_seed_flags()`
- `pipeline/run_stages.py` — shared stages 2–8 (used by CLI + HTTP)
- `pipeline/graph/writer.py` — Neo4j writes + relationship type safety

**Frontend:**
- `src/App.jsx` — root component, auth/dashboard logic
- `src/pages/AuthPage.jsx` — signup/login form
- `src/pages/DashboardPage.jsx` — main dashboard
- `src/components/GraphVisualization.jsx` — force-graph renderer
- `src/components/{Upload,Entity,Relationship,Alerts}Panel.jsx` — content views

---

## 📈 Expected Metrics (From Tests)

```
✓ Entity F1: 1.0 (on validation set)
✓ Relationship F1: 1.0 (confident tier)
✓ 6 ASSOCIATION edges routed to review (low-conf, not claimed as verified)
✓ 2 verified relationships in main graph
✓ Cross-case detection: flags phones with 2+ Person neighbors
✓ Centrality: normalized [0,1] per node
```

---

## 🎯 SIH 26189 PS Mapping

| PS Need | NexusTrace Solution |
|---|---|
| Extract entities from fragmented data | Stages 1–3: multi-source ingest + regex/spaCy/gazetteer |
| Build relationship maps | Stage 5 + Neo4j graph |
| Identify key individuals | Stage 7 centrality, UI node size |
| Detect suspicious patterns | Stage 7 anomalies + cross-case flags |
| Provide visual insights | React dashboard + force-graph |
| Track investigation | Analyst review queue + approve workflow |

---

## 🚨 Security Notes

- **Auth:** Replace demo auth with real user store before production
- **CORS:** Change from `*` to specific frontend origin
- **Secrets:** Use `.env` (git-ignored), never commit live credentials
- **Encryption:** Add TLS/HTTPS for production
- **Audit:** Log all access + graph mutations (recommended for gov)

---

## 📞 Support

All 10 fixes verified ✅  
Tests: 40/40 passing ✅  
Pipeline: end-to-end working ✅  
Ready for demo/deployment ✅

**Built for SIH26189 — Ministry of Home Affairs, NCRB Women Safety Division**
