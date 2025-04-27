import json
import time
import logging
from pathlib import Path
from threading import Lock, local
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from webdriver_manager.chrome import ChromeDriverManager

# =========================
# 🔧 KONFIGURASI GLOBAL
# =========================

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"
OUTPUT_DIR = DATA_DIR / "output"
DATA_PATH = DATA_DIR / "article_links.json"
OUTPUT_FILE = OUTPUT_DIR / "scraped_articles.json"
PROCESSED_ARTICLE_URLS_FILE = OUTPUT_DIR / "processed_article_urls.json"
import random

file_count = len(list(OUTPUT_DIR.glob("scraped_articles_*.json"))) + 1
output_file = OUTPUT_DIR / f"scraped_articles_{file_count}.json"


DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_thread_locals = local()
lock = Lock()
processed_article_urls = {}

# =========================
# 📋 SETUP LOGGING
# =========================

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
if not logger.hasHandlers():
    logger.addHandler(handler)

# =========================
# 🌐 SETUP SELENIUM DRIVER
# =========================

def get_driver():
    if not hasattr(_thread_locals, "driver"):
        service = Service(ChromeDriverManager().install())
        options = Options()
        ua = UserAgent()
        user_agent = ua.random

        options.add_argument("--headless")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--ignore-ssl-errors")
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-cache")
        options.add_argument(f"--user-agent={user_agent}")
        options.add_argument("--lang=en-US")
        options.add_argument("--disable-blink-features=AutomationControlled")
        _thread_locals.driver = webdriver.Chrome(service=service, options=options)
        logger.info("✅ [Thread] WebDriver dibuat baru.")
    return _thread_locals.driver

def close_driver():
    if hasattr(_thread_locals, "driver"):
        _thread_locals.driver.quit()
        delattr(_thread_locals, "driver")
        logger.info("🛑 WebDriver ditutup untuk thread.")

# =========================
# 📥 BACA FILE JSON
# =========================

def read_json(filepath):
    if Path(filepath).exists():
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return pd.DataFrame(data)
        except Exception as e:
            logger.error(f"❌ Gagal membaca file JSON: {e}")
    return pd.DataFrame()

def load_processed_article_urls():
    if PROCESSED_ARTICLE_URLS_FILE.exists():
        try:
            with open(PROCESSED_ARTICLE_URLS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"❌ Gagal membaca daftar URL artikel yang sudah diproses: {e}")
    return {}

def save_processed_article_urls():
    try:
        with open(PROCESSED_ARTICLE_URLS_FILE, "w", encoding="utf-8") as f:
            json.dump(processed_article_urls, f, ensure_ascii=False, indent=4)
        logger.info("✅ Daftar URL artikel yang sudah diproses berhasil disimpan.")
    except Exception as e:
        logger.error(f"❌ Gagal menyimpan URL artikel: {e}")

# =========================
# 💾 SIMPAN DATA KE FILE
# =========================

def save_article_separately(article_data, output_dir):
    try:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        file_count = len(list(output_dir.glob("scraped_articles_*.json"))) + 1
        output_file = output_dir / f"scraped_articles_{file_count}.json"

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(article_data, f, ensure_ascii=False, indent=4)

        logger.info(f"✅ Data artikel disimpan di {output_file}")
    except Exception as e:
        logger.error(f"❌ Gagal menyimpan artikel: {e}")

# =========================
# 🔍 SCRAPE DETAIL ARTIKEL
# =========================

def scrape_article_details(driver, article_url):
    try:
        driver.get(article_url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "document-title"))
        )

        soup = BeautifulSoup(driver.page_source, "html.parser")

        title = soup.find("h1", class_="document-title")
        title = title.get_text(strip=True) if title else "Title Not Found"

        abstract_section = soup.find("div", attrs={"xplmathjax": True})
        abstract = abstract_section.get_text(strip=True) if abstract_section else "Abstract Not Found"

        author_spans = soup.find_all("span", attrs={"_ngcontent-ng-c1131135293": True})
        authors = ", ".join(sorted(set(span.text.strip() for span in author_spans if span.text.strip())))

        journal_conference_name = "IEEE Access"
        publisher = "IEEE"
        
        year_div = soup.find("div", class_="doc-abstract-pubdate")
        year = year_div.get_text(strip=True).split()[-1] if year_div else "Year Not Found"

        doi_link = soup.find("div", class_="stats-document-abstract-doi")
        doi = doi_link.find("a", href=True)["href"] if doi_link and doi_link.find("a", href=True) else "DOI Not Found"

        group_name = "OpsA"

        return pd.DataFrame([{
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "journal_conference_name": journal_conference_name,
            "publisher": publisher,
            "year": year,
            "doi": doi,
            "group_name": group_name,
            "url": article_url
        }])
    except Exception as e:
        logger.error(f"❌ Gagal scrape detail artikel: {e}")
        return pd.DataFrame()

# =========================
# 🕸️ SCRAPE SEMUA URL
# =========================

def scrape_from_url(row, max_pages=15):
    base_url = row["URL"]
    driver = get_driver()

    try:
        logger.info(f"🔍 Mulai scraping {base_url}")
        page_number = 1

        while page_number <= max_pages:
            url = f"{base_url}&sortType=vol-only-newest&pageNumber={page_number}"
            logger.info(f"📄 Membuka halaman {page_number}: {url}")
            driver.get(url)

            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "col"))
                )
            except Exception:
                logger.warning(f"⛔ Halaman {page_number} gagal dimuat.")
                break

            time.sleep(5)

            soup = BeautifulSoup(driver.page_source, "html.parser")
            article_links = [
                f"https://ieeexplore.ieee.org{a['href']}"
                for a in soup.find_all("a", href=True)
                if "/document/" in a['href'] and "/citations" not in a['href']
            ]

            if not article_links:
                logger.warning("🚫 Tidak ada artikel ditemukan.")
                break

            logger.info(f"📚 {len(article_links)} artikel ditemukan di halaman {page_number}")

            for article_url in article_links:
                if processed_article_urls.get(article_url) == "berhasil":
                    logger.info(f"✅ Sudah diproses: {article_url}")
                    continue

                article_data = scrape_article_details(driver, article_url)
                if not article_data.empty:
                    save_article_separately(article_data.to_dict(orient="records")[0], OUTPUT_DIR)
                    with lock:
                        processed_article_urls[article_url] = "berhasil"
                else:
                    processed_article_urls[article_url] = "gagal"

                save_processed_article_urls()

            page_number += 1

        processed_article_urls[base_url] = "berhasil"
        save_processed_article_urls()

    except Exception as e:
        logger.error(f"❌ Error saat scraping {base_url}: {e}")
        processed_article_urls[base_url] = "gagal"
        save_processed_article_urls()
    finally:
        close_driver()

# =========================
# 🚀 MAIN FUNCTION
# =========================

def main():
    global processed_article_urls
    processed_article_urls = load_processed_article_urls()

    df = read_json(DATA_PATH)
    if df.empty:
        logger.error("❌ Tidak ada data URL untuk diproses.")
        return

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(scrape_from_url, row): row for _, row in df.iterrows()}
        for future in as_completed(futures):
            row = futures[future]
            try:
                future.result()
            except Exception as e:
                logger.error(f"❌ Gagal memproses URL {row['URL']}: {e}")

if __name__ == "__main__":
    main()
