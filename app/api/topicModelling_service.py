from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form
from pydantic import BaseModel
from pathlib import Path
from prometheus_client import Summary, Gauge
import asyncio
import json
import uuid
import logging
import shutil

from src.modelling.TopicModelling import (
    run_modelling,
    predict_topics,
    get_available_models,
    DATA_PATHS,
)
from src.modelling.preprocessing import clean_and_combine, clean_data

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[2]
CLEAN_DATA_DIR = BASE_DIR / "data" / "cleaned"
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
ARXIV_RAW_PATH = BASE_DIR / "data" / "raw" / "output" / "scraped_articles.json"
IEEE_RAW_PATH  = BASE_DIR / "data" / "raw" / "scraped_articles_ieee.json"

logger = logging.getLogger(__name__)
logger.propagate = False

MODELLING_DURATION = Summary("modelling_duration_seconds", "Duration of modelling")
SILHOUETTE_SCORE = Gauge("silhouette_score", "Silhouette score")
COHERENCE_SCORE = Gauge("coherence_score", "Average coherence score")

modelling_jobs: dict = {}

class ModellingRequest(BaseModel):
    n_clusters: int = 3
    use_arxiv: bool = True
    use_ieee: bool = True

class PredictRequest(BaseModel):
    texts: list[str]
    cluster_id: int = 0

@router.get("/data-status/")
async def data_status():
    return {
        "scraped_arxiv":    ARXIV_RAW_PATH.exists() and ARXIV_RAW_PATH.stat().st_size > 0,
        "scraped_ieee":     IEEE_RAW_PATH.exists() and IEEE_RAW_PATH.stat().st_size > 0,
        "cleaned_combined": (
            (BASE_DIR / "data" / "cleaned" / "cleaned_articles_combined.json").exists() and
            (BASE_DIR / "data" / "cleaned" / "cleaned_articles_combined.json").stat().st_size > 0
        ),
    }

@router.post("/upload-data/")
async def upload_data(file: UploadFile = File(...), source: str = Form(...)):
    if source not in ("arxiv", "ieee"):
        raise HTTPException(status_code=400, detail="source must be 'arxiv' or 'ieee'.")

    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="File must be in .json format.")

    save_path = ARXIV_RAW_PATH if source == "arxiv" else IEEE_RAW_PATH
    save_path.parent.mkdir(parents=True, exist_ok=True)

    content = await file.read()
    try:
        data = json.loads(content)
        if not isinstance(data, list):
            raise HTTPException(status_code=400, detail="JSON file must be an array of objects.")
        if len(data) == 0:
            raise HTTPException(status_code=400, detail="Empty JSON file.")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Not a valid JSON file.")

    with open(save_path, "wb") as f:
        f.write(content)

    logger.info(f"Uploaded {source} data: {len(data)} records → {save_path}")
    return {
        "message": f"{len(data)} records saved as {source} data.",
        "path": str(save_path),
        "total": len(data)
    }

@router.post("/run-topic-modelling/")
async def run_topic_modelling_endpoint(body: ModellingRequest):
    job_id = str(uuid.uuid4())
    modelling_jobs[job_id] = {
        "status": "running",
        "step": "starting",
        "message": "Pipeline started...",
        "result": None
    }

    async def pipeline():
        try:
            modelling_jobs[job_id]["step"] = "preprocessing"
            modelling_jobs[job_id]["message"] = "Step 1/2 — Preprocessing & combining data..."

            arxiv_raw = BASE_DIR / "data" / "raw" / "output" / "scraped_articles.json"
            ieee_raw = BASE_DIR / "data" / "cleaned" / "cleaned_articles_ieee.json"

            df_combined = await asyncio.to_thread(
                clean_and_combine,
                arxiv_raw if body.use_arxiv else None,
                ieee_raw if body.use_ieee else None,
                "cleaned_articles_combined.json"
            )

            modelling_jobs[job_id]["message"] = (
                f"Step 1/2 — Done. "
                f"{len(df_combined)} articles combined. "
                f"Sources: {df_combined['source'].value_counts().to_dict()}"
            )
            logger.info(f"Preprocessing done: {len(df_combined)} articles.")

            modelling_jobs[job_id]["step"] = "modelling"
            modelling_jobs[job_id]["message"] = (
                f"Step 2/2 — Training BERTopic "
                f"({body.n_clusters} clusters, {len(df_combined)} articles)..."
            )

            with MODELLING_DURATION.time():
                results = await asyncio.to_thread(
                    run_modelling, body.n_clusters,
                    {"combined": CLEAN_DATA_DIR / "cleaned_articles_combined.json"}
                )

            silhouette = results.get("silhouette_score", 0.0)
            SILHOUETTE_SCORE.set(silhouette)
            
            global_coherence = results.get("coherence_score")
            
            if global_coherence is not None:
                COHERENCE_SCORE.set(float(global_coherence))
            else:
                coherence_scores = [
                    c.get("coherence_score", c.get("coherence", 0.0)) 
                    for c in results.get("clusters", {}).values()
                ]
                if coherence_scores:
                    avg_coherence = sum(coherence_scores) / len(coherence_scores)
                    COHERENCE_SCORE.set(avg_coherence)
                    results["coherence_score"] = avg_coherence
                else:
                    COHERENCE_SCORE.set(0.0)
                    results["coherence_score"] = 0.0

            modelling_jobs[job_id]["status"] = "done"
            modelling_jobs[job_id]["step"] = "done"
            modelling_jobs[job_id]["message"] = (
                f"Pipeline finished. "
                f"{results.get('num_articles', 0)} articles, "
                f"silhouette: {silhouette:.4f}"
            )
            modelling_jobs[job_id]["result"] = results
            
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            modelling_jobs[job_id]["status"] = "failed"
            modelling_jobs[job_id]["message"] = str(e)

    asyncio.create_task(pipeline())
    return {"job_id": job_id, "message": "Pipeline started."}

@router.get("/run-topic-modelling/status/{job_id}")
async def modelling_status(job_id: str):
    if job_id not in modelling_jobs:
        raise HTTPException(status_code=404, detail="Job not found.")
    return modelling_jobs[job_id]

@router.post("/predict/")
async def predict_endpoint(body: PredictRequest):
    available = get_available_models()
    if not available:
        raise HTTPException(
            status_code=404,
            detail="No saved models. Run /run-topic-modelling/ first."
        )
    if body.cluster_id not in available:
        raise HTTPException(
            status_code=400,
            detail=f"Model cluster {body.cluster_id} not found. Available: {available}"
        )
    try:
        results = await asyncio.to_thread(predict_topics, body.texts, body.cluster_id)
        return {"cluster_id": body.cluster_id, "predictions": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models/")
async def list_models():
    available = get_available_models()
    return {"available_models": available, "total": len(available)}

@router.get("/topic-info/")
async def get_topic_info():
    topic_info_path = LOG_DIR / "topic_info.json"
    if not topic_info_path.exists():
        raise HTTPException(
            status_code=404,
            detail="topic_info.json not found. Run /run-topic-modelling/ first."
        )
    with open(topic_info_path, "r", encoding="utf-8") as f:
        return json.load(f)