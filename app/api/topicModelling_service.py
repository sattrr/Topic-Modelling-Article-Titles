from fastapi import APIRouter
import subprocess
import sys
import os
from pathlib import Path
from fastapi import HTTPException
from prometheus_client import Summary, Gauge

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[2]
input_path = BASE_DIR / "data" / "raw" / "scrapped_articles.json"

MODELLING_DURATION = Summary("modelling_duration_seconds", "Duration of modeling training")
SILHOUETTE_SCORE = Gauge("silhouette_score", "Silhouette score")
COHERENCE_SCORE = Gauge("coherence_score", "Average coherence score")

def run_preprocessing(input_path: str):
    try:
        subprocess.run([sys.executable, 'src/modelling/preprocessing.py', input_path], check=True)
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail="Preprocessing failed")

def run_topic_modelling(input_path: str):
    try:
        subprocess.run([sys.executable, 'src/modelling/TopicModelling.py', input_path], check=True)
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail="Topic Modelling failed")

    topic_info_path = BASE_DIR / "logs" / "topic_info.json"
    if topic_info_path.exists():
        import json
        with open(topic_info_path, "r", encoding="utf-8") as f:
            topic_data = json.load(f)
            scores = [cl["coherence_score"] for cl in topic_data.values()]
            if scores:
                avg_coherence = sum(scores) / len(scores)
                COHERENCE_SCORE.set(avg_coherence)

    silhouette_path = BASE_DIR / "mlruns" / "0" / "*/metrics/silhouette_score"

@router.post("/run-topic-modelling/")
async def run_topic_modelling_endpoint():
    if not input_path.exists():
        raise HTTPException(status_code=400, detail="Input path does not exist.")

    run_preprocessing(input_path)
    run_topic_modelling(input_path)

    return {"status": "success", "message": "Topic Modelling completed successfully!"}
