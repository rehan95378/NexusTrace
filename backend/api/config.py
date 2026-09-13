import json
import os
import pathlib

from dotenv import load_dotenv

# Load backend/.env BEFORE reading any config/env below so NEO4J_*, JWT_SECRET,
# port etc. are honoured locally. Idempotent + safe if the file is absent.
load_dotenv()

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "")
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def load_config():
    with open(ROOT / "config" / "config.json") as f:
        cfg = json.load(f)
    # allow env overrides (e.g. NEO4J_PASSWORD, JWT_SECRET)
    if os.getenv("NEO4J_PASSWORD"):
        cfg["neo4j"]["password"] = os.getenv("NEO4J_PASSWORD")
    if os.getenv("JWT_SECRET"):
        cfg["jwt"]["secret"] = os.getenv("JWT_SECRET")
    return cfg


config = load_config()