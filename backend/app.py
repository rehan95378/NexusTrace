"""NexusTrace API entrypoint (SIH26189).

One FastAPI service serving the REST API + the full extraction/analytics
pipeline. The frontend lives in a separate static service and talks to this
API via VITE_API_URL.

Run:
    cd backend && uvicorn app:app --host 0.0.0.0 --port 8000

In GRAPH_MODE=seed (default) the graph/alerts/review all work from in-memory
data with no Neo4j, so the demo runs anywhere. Set GRAPH_MODE=neo4j + the
NEO4J_* env vars to read/write a live graph.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import (
    auth_router,
    graph_router,
    alerts_router,
    ingest_router,
    review_router,
)

from api.config import config


# Refuse to start with a known-insecure JWT signing key. The demo .env/.env
# placeholders are "CHANGE_ME" / "change-this-to-a-random-string"; if they reach
# here the server must not run, or anyone knowing the default can forge tokens.
def _assert_secure_secret() -> None:
    secret = (config["jwt"].get("secret") or "").strip()
    # Block only when no real override was provided — i.e. the secret is still
    # the config.json placeholder, or empty. Any explicit value (including a
    # short local one like "dev") lets the demo run; anyone can then forge
    # tokens, so this is only a guard against the default, not a security seal.
    if not secret or secret.lower() == "change_me":
        raise RuntimeError(
            "Refusing to start: JWT_SECRET was never set (still the default). "
            "Set a real JWT_SECRET in backend/.env or the environment."
        )


_assert_secure_secret()

app = FastAPI(title="NexusTrace API", version="0.1.0")

# SIH26: NCRB / Ministry of Home Affairs / Women Safety Division
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your frontend origin before prod
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(graph_router.router)
app.include_router(alerts_router.router)
app.include_router(ingest_router.router)
app.include_router(review_router.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "nexustrace-backend"}


@app.get("/")
def root():
    return {"message": "NexusTrace API is running", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)