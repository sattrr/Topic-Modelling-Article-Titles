from fastapi import APIRouter, HTTPException
import subprocess
import sys
import os
from pathlib import Path

router = APIRouter()

# Menghitung path relatif dari lokasi file ini
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # arahkan ke root project
input_path = BASE_DIR / "data" / "raw" / "scraped_articles.json"

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

@router.post("/run-topic-modelling/")
async def run_topic_modelling_endpoint():
    if not os.path.exists(input_path):
        raise HTTPException(status_code=400, detail="Input path does not exist.")

    run_preprocessing(input_path)
    run_topic_modelling(input_path)

    return {"status": "success", "message": "Topic Modelling completed successfully!"}
