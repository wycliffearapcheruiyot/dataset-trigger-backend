"""
main.py -- standalone Dataset Trigger backend (FastAPI).

Endpoints
  GET  /health            liveness check (no auth)
  POST /dataset/ensure    is the dataset on Kaggle? if not, start HF -> Kaggle run
  GET  /dataset/status    same answer, never starts a run

Run locally:   uvicorn main:app --reload
On Render:     uvicorn main:app --host 0.0.0.0 --port $PORT
"""

import os

from fastapi import FastAPI
from pymongo import MongoClient

from dataset_manager import DatasetError
from dataset_routes import build_router

app = FastAPI(title="Dataset Trigger Backend")

_client = None


def get_db():
    """Lazily connect to MongoDB (Atlas or otherwise) and return the database."""
    global _client
    if _client is None:
        uri = os.environ.get("MONGODB_URI", "").strip()
        if not uri:
            raise DatasetError("MONGODB_URI is not set.")
        _client = MongoClient(uri, serverSelectionTimeoutMS=8000)
    return _client[os.environ.get("MONGODB_DB", "dataset_backend")]


app.include_router(build_router(get_db))


@app.get("/health")
def health():
    return {"ok": True}
