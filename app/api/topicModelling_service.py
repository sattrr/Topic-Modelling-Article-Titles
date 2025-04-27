from fastapi import APIRouter, HTTPException
import subprocess
import sys
import os
from pathlib import Path
<<<<<<< HEAD
from fastapi import HTTPException

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[2]
input_path = BASE_DIR / "data" / "raw" / "scrapped_articles.json"
=======

router = APIRouter()

# Menghitung path relatif dari lokasi file ini
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # arahkan ke root project
input_path = BASE_DIR / "data" / "raw" / "scraped_articles.json"
>>>>>>> abiyyu-v-crawling

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
    if not input_path.exists():
        raise HTTPException(status_code=400, detail="Input path does not exist.")

    run_preprocessing(input_path)
    run_topic_modelling(input_path)

    return {"status": "success", "message": "Topic Modelling completed successfully!"}
