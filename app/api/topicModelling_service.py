from fastapi import APIRouter, HTTPException
import subprocess
import sys
from pathlib import Path

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
input_path = BASE_DIR / "data" / "cleaned" / "cleaned_articles.json"

def run_topic_modelling(input_path: str):
    try:
        subprocess.run([sys.executable, 'src/modelling/TopicModelling.py', str(input_path)], check=True)
    except subprocess.CalledProcessError:
        raise HTTPException(status_code=500, detail="Topic Modelling failed")

@router.post("/run-topic-modelling/")
async def run_topic_modelling_endpoint():
    if not input_path.exists():
        raise HTTPException(status_code=400, detail=f"Input path does not exist: {input_path}")

    run_topic_modelling(input_path)

    return {"status": "success", "message": "Topic Modelling completed successfully!"}