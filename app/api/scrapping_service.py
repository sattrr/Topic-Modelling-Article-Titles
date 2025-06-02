import subprocess
import logging
import sys
import os
import time
import json
from prometheus_client import Summary, Gauge
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, HTTPException
from starlette.responses import StreamingResponse

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[2]
SCRAPPING_DIR = BASE_DIR / "src" / "scrapping"
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data" / "raw"
OUTPUT_DIR = DATA_DIR / "output"
CLEANED_DIR = BASE_DIR / "data" / "cleaned"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

log_file_path = LOGS_DIR / "scraping.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file_path),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Prometheus metrics
SCRAPING_DURATION = Summary("scraping_duration_seconds", "Waktu scraping artikel (getTitle)")
SCRAPED_ARTICLE_COUNT = Gauge("scraped_article_count", "Jumlah artikel hasil scraping (sebelum cleaning)")
CLEANED_ARTICLE_COUNT = Gauge("cleaned_article_count", "Jumlah artikel setelah cleaning")

def run_script(script_name: str) -> str:
    script_path = SCRAPPING_DIR / script_name

    if not script_path.exists():
        logger.error(f"Script {script_name} tidak ditemukan di {script_path}")
        raise HTTPException(status_code=400, detail=f"Script {script_name} tidak ditemukan.")

    logger.info(f"Menjalankan script: {script_name}")
    
    # Only measure scraping duration for getTitle.py
    if script_name == "getTitle.py":
        with SCRAPING_DURATION.time():
            process = subprocess.Popen(
                [sys.executable, str(script_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            output = ""
            for line in iter(process.stdout.readline, ''):
                logger.info(line.strip())
                output += line

            process.stdout.close()
            process.wait()
    else:
        process = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        output = ""
        for line in iter(process.stdout.readline, ''):
            logger.info(line.strip())
            output += line

        process.stdout.close()
        process.wait()

    if process.returncode == 0:
        logger.info(f"Script {script_name} selesai tanpa error.\n")
    else:
        logger.error(f"Script {script_name} gagal dijalankan.\n")
        raise HTTPException(status_code=500, detail=f"Script {script_name} gagal dijalankan.")

    # Update metrics after successful execution
    if script_name == "getTitle.py":
        try:
            # Count total scraped articles from output directory
            total_scraped = 0
            if OUTPUT_DIR.exists():
                for json_file in OUTPUT_DIR.glob("scraped_articles_*.json"):
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            article_data = json.load(f)
                            if isinstance(article_data, dict):
                                total_scraped += 1
                            elif isinstance(article_data, list):
                                total_scraped += len(article_data)
                    except Exception as e:
                        logger.error(f"Error reading {json_file}: {e}")
                        continue
            
            SCRAPED_ARTICLE_COUNT.set(total_scraped)
            logger.info(f"Updated scraped article count: {total_scraped}")
        except Exception as e:
            logger.error(f"Error updating scraped article count metric: {e}")
    
    elif script_name == "cleaningdata.py":
        try:
            # Count cleaned articles from cleaned_articles.json
            cleaned_file = CLEANED_DIR / "cleaned_articles.json"
            total_cleaned = 0
            if cleaned_file.exists():
                with open(cleaned_file, 'r', encoding='utf-8') as f:
                    cleaned_data = json.load(f)
                    if isinstance(cleaned_data, list):
                        total_cleaned = len(cleaned_data)
                    elif isinstance(cleaned_data, dict):
                        total_cleaned = 1
            
            CLEANED_ARTICLE_COUNT.set(total_cleaned)
            logger.info(f"Updated cleaned article count: {total_cleaned}")
        except Exception as e:
            logger.error(f"Error updating cleaned article count metric: {e}")

    return output

def run_title_and_cleaning():
    logger.info("Memulai scraping judul...")
    title_output = run_script("getTitle.py")

    logger.info("Memulai proses cleaning data...")
    cleaning_output = run_script("cleaningdata.py")

    logger.info("Scraping judul dan cleaning data selesai.")
    return title_output + "\n" + cleaning_output

def run_all_processes():
    logger.info("Memulai seluruh rangkaian proses...")

    logger.info("Memulai proses scraping link artikel...")
    links_output = run_script("getLinks.py")

    title_and_cleaning_output = run_title_and_cleaning()

    logger.info("Seluruh proses selesai.")
    return links_output + title_and_cleaning_output

@router.post("/run-scrapping-processes/")
async def run_all(background_tasks: BackgroundTasks):
    logger.info("Menerima permintaan untuk menjalankan seluruh rangkaian proses.")

    logger.info(f"Base directory: {BASE_DIR}")
    logger.info(f"Scrapping directory: {SCRAPPING_DIR}")
    logger.info(f"Isi folder scrapping: {os.listdir(SCRAPPING_DIR) if SCRAPPING_DIR.exists() else 'Directory not found'}")

    try:
        background_tasks.add_task(run_all_processes)
        logger.info("Background task berhasil ditambahkan.")
    except Exception as e:
        logger.exception("Gagal menambahkan background task!")
        raise HTTPException(status_code=500, detail=str(e))

    return {"message": "Proses dijalankan di background, tunggu hingga selesai."}

@router.post("/scrape-links/")
async def scrape_links():
    logger.info("Memulai proses scraping link artikel...")
    output = run_script("getLinks.py")
    logger.info("Proses scraping link artikel selesai.")
    return {"output": output}

@router.post("/scrape-titles/")
async def scrape_titles():
    logger.info("Memulai scraping judul")
    output = run_script("getTitle.py")
    logger.info("Scraping judul selesai.")
    return StreamingResponse(iter([output]), media_type="text/plain")

@router.post("/cleaning-only/")
async def run_cleaning_only():
    logger.info("Menjalankan proses cleaning data saja...")
    output = run_script("cleaningdata.py")
    logger.info("Cleaning data selesai.")
    return StreamingResponse(iter([output]), media_type="text/plain")