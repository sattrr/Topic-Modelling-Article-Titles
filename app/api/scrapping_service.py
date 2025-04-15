from fastapi import APIRouter, BackgroundTasks
import subprocess
from pathlib import Path
import logging
from starlette.responses import StreamingResponse
import asyncio
import threading

# Inisialisasi router
router = APIRouter()

# Konfigurasi direktori
BASE_DIR = Path(__file__).resolve().parents[2]
SCRAPPING_DIR = BASE_DIR / "src" / "scrapping"
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Fungsi untuk stream log output
def stream_script(script_names: list):
    def generate():
        for script_name in script_names:
            script_path = SCRAPPING_DIR / script_name
            logger.info(f"Menjalankan script: {script_name}")

            process = subprocess.Popen(
                ["python", str(script_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
                universal_newlines=True
            )

            # Menangkap dan men-stream output
            for line in iter(process.stdout.readline, ''):
                logger.info(line.strip())
                yield line
            process.stdout.close()
            process.wait()
            logger.info(f"Script {script_name} selesai.\n")

    return generate

# Konfigurasi logging
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

# Fungsi untuk menjalankan script dan capture log output secara asynchronous
def run_script(script_name: str) -> str:
    script_path = SCRAPPING_DIR / script_name
    logger.info(f"Menjalankan script: {script_name}")
    
    # Menggunakan Popen untuk non-blocking
    result = subprocess.run(["python", str(script_path)], capture_output=True, text=True)

    if result.returncode == 0:
        logger.info(f"Script {script_name} selesai tanpa error.")
    else:
        logger.error(f"Script {script_name} gagal dijalankan.")
        logger.error(result.stderr)

    return result.stdout + result.stderr

# Fungsi gabungan untuk scraping judul dan cleaning
def run_title_and_cleaning():
    logger.info("Memulai scraping judul...")
    title_output = run_script("getTitle.py")
    
    logger.info("Memulai proses cleaning data...")
    cleaning_output = run_script("cleaningdata.py")

    logger.info("Scraping judul dan cleaning data selesai.")
    return title_output + "\n" + cleaning_output

# Fungsi untuk menjalankan seluruh proses secara berurutan
def run_all_processes():
    logger.info("Memulai seluruh rangkaian proses...")
    
    # Langkah 1: Scraping links
    logger.info("Memulai proses scraping link artikel...")
    links_output = run_script("getLinks.py")
    
    # Langkah 2: Scraping judul dan cleaning data
    title_and_cleaning_output = run_title_and_cleaning()

    logger.info("Seluruh proses selesai.")
    return links_output + title_and_cleaning_output  # Gabungkan hasil dari semua proses

# Endpoint untuk menjalankan seluruh proses
@router.post("/run-scrapping-processes/")
async def run_all(background_tasks: BackgroundTasks):
    logger.info("Menerima permintaan untuk menjalankan seluruh rangkaian proses.")
    
    # Menjalankan semua proses secara berurutan di background
    background_tasks.add_task(run_all_processes)
    
    return {"message": "Proses dijalankan di background, tunggu hingga selesai."}

# Endpoint untuk menjalankan scraping link artikel
@router.post("/scrape-links/")
async def scrape_links():
    logger.info("Memulai proses scraping link artikel...")
    output = run_script("getLinks.py")
    logger.info("Proses scraping link artikel selesai.")
    return {"output": output}

# Endpoint untuk menjalankan scraping judul dan cleaning
@router.post("/scrape-titles/")
async def scrape_titles(background_tasks: BackgroundTasks):
    logger.info("Menerima permintaan untuk streaming scraping judul dan cleaning.")
    
    # Memanggil stream_script untuk mendapatkan generator
    return StreamingResponse(
        stream_script(["getTitle.py", "cleaningdata.py"])(),
        media_type="text/plain"
    )
