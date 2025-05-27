import subprocess
import logging
import sys
import os
import time
from prometheus_client import Summary, Gauge
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, HTTPException
from starlette.responses import StreamingResponse

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[2]
SCRAPPING_DIR = BASE_DIR / "src" / "scrapping"
LOGS_DIR = BASE_DIR / "logs"
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

SCRAPING_DURATION = Summary("scraping_duration_seconds", "Waktu scraping keseluruhan")
SCRAPED_ARTICLE_COUNT = Gauge("scraped_article_count", "Jumlah artikel hasil scraping")

@SCRAPING_DURATION.time()
def run_script(script_name: str) -> str:
    script_path = SCRAPPING_DIR / script_name

    if not script_path.exists():
        logger.error(f"Script {script_name} tidak ditemukan di {script_path}")
        raise HTTPException(status_code=400, detail=f"Script {script_name} tidak ditemukan.")

    logger.info(f"Menjalankan script: {script_name}")
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

    if script_name == "getLinks.py":
        try:
            with open("data/raw/article_links.json") as f:
                data = json.load(f)
                SCRAPED_ARTICLE_COUNT.set(len(data))
        except:
            pass

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
    logger.info(f"Isi folder scrapping: {os.listdir(SCRAPPING_DIR)}")

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
    logger.info("Memulai scraping judul dan cleaning...")

    output = run_title_and_cleaning()

    return StreamingResponse(iter([output]), media_type="text/plain")