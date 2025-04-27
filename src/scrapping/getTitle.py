from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import time
import json
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from webdriver_manager.chrome import ChromeDriverManager
from pathlib import Path

# =========================
# 🔧 KONFIGURASI GLOBAL
# =========================

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"
OUTPUT_DIR = BASE_DIR / "data" / "raw" / "output"  
PROCESSED_ARTICLE_URLS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "processed_article_urls.json"
processed_article_urls = {}
DATA_PATH = DATA_DIR / "article_links.json"

<<<<<<< HEAD
=======
# Membuat direktori jika belum ada
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)  # Membuat output jika belum ada

# =========================
# 📋 SETUP LOGGING
# ========================= 

>>>>>>> abiyyu-v-crawling
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
if not logger.hasHandlers():
    logger.addHandler(ch)

# =========================
# 🌐 SETUP SELENIUM DRIVER
# =========================

def setup_driver():
    try:
        service = Service(ChromeDriverManager().install())
        options = Options()
        ua = UserAgent()
        user_agent = ua.random

        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--ignore-ssl-errors")
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-cache")
        options.add_argument(f"--user-agent={user_agent}")
        options.add_argument("--window-size=200,150")
        options.add_argument("--lang=en-US")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")

        driver = webdriver.Chrome(service=service, options=options)
        logger.info("✅ WebDriver berhasil diinisialisasi.")
        return driver
    except Exception as e:
        logger.error(f"❌ Gagal setup WebDriver: {e}")
        raise

# =========================
# 📥 BACA FILE JSON INPUT
# =========================

def read_json(json_path):
    try:
        with open(json_path, "r", encoding="utf-8") as file:
            data = json.load(file)
        if "URL" not in data or not data["URL"]:
            raise ValueError("❌ JSON tidak mengandung key 'URL' atau isinya kosong.")
        return pd.DataFrame(data["URL"], columns=["URL"])
    except json.JSONDecodeError as e:
        logger.error(f"❌ Gagal decode JSON: {e}. Mengabaikan kesalahan dan lanjutkan.")
        return pd.DataFrame(columns=["URL"])
    except Exception as e:
        logger.critical(f"❌ Kesalahan lainnya saat membaca JSON: {e}")
        raise

# =========================
# 📤 BACA HASIL YANG SUDAH ADA
# =========================

def read_existing_output(output_path):
    if Path(output_path).exists():
<<<<<<< HEAD
        return pd.read_json(output_path)
    else:
        return pd.DataFrame(columns=["Judul", "Tahun", "Author"])

def append_and_save(new_data, output_path):
    existing_data = read_existing_output(output_path)
    combined_data = pd.concat([existing_data, new_data], ignore_index=True)
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    combined_data.to_json(output_path, orient="records", indent=4)
    print(f"Data dari halaman ini berhasil ditambahkan ke: {output_path}")

def scrape_titles_per_page(df, driver, output_path, max_pages=2):
    for index, row in df.iterrows():
=======
>>>>>>> abiyyu-v-crawling
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                content = f.read()
            cutoff_index = content.find("]") + 1
            cleaned_content = content[:cutoff_index]
            json_data = json.loads(cleaned_content)
            return pd.DataFrame(json_data)
        except Exception as e:
            logger.error(f"❌ Kesalahan saat membaca file: {e}. Mengabaikan kesalahan dan melanjutkan.")
            return pd.DataFrame(columns=["title", "abstract", "authors", "journal_conference_name", "publisher", "year", "doi", "group_name", "url"])
    else:
        logger.warning(f"⚠️ File tidak ditemukan, melanjutkan proses tanpa data.")
        return pd.DataFrame(columns=["title", "abstract", "authors", "journal_conference_name", "publisher", "year", "doi", "group_name", "url"])

# =========================
# 💾 SIMPAN DATA KE JSON TERPISAH
# =========================

def save_article_separately(article_data, output_dir):
    try:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Dapatkan nomor urut file
        file_count = len(list(output_dir.glob("scraped_articles_*.json"))) + 1
        output_file = output_dir / f"scraped_articles_{file_count}.json"

        # Simpan artikel ke dalam file JSON terpisah
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(article_data, f, ensure_ascii=False, indent=4)
        
        logger.info(f"✅ Data berhasil disimpan ke: {output_file}")
    except Exception as e:
        logger.error(f"❌ Gagal menyimpan artikel: {e}")

# =========================
# 🧹 LOAD AND SAVE PROCESSED ARTICLE URL
# =========================

def load_processed_article_urls():
    if PROCESSED_ARTICLE_URLS_FILE.exists():
        try:
            with open(PROCESSED_ARTICLE_URLS_FILE, "r", encoding="utf-8") as f:
                processed_article_urls = json.load(f)
            return processed_article_urls  # Mengembalikan dictionary
        except Exception as e:
            logger.error(f"❌ Gagal membaca daftar URL artikel yang sudah diproses: {e}")
            return {}  # Mengembalikan dictionary kosong jika gagal
    return {}  # Mengembalikan dictionary kosong jika file tidak ada

def save_processed_article_urls():
    try:
        with open(PROCESSED_ARTICLE_URLS_FILE, "w", encoding="utf-8") as f:
            json.dump(processed_article_urls, f, ensure_ascii=False, indent=4)
        logger.info("✅ Daftar URL artikel yang sudah diproses berhasil disimpan.")
    except Exception as e:
        logger.error(f"❌ Gagal menyimpan URL artikel yang sudah diproses: {e}")

def scrape_from_url(row, max_pages=5, max_retries=3):
    base_url = row["URL"]

    # Cek jika URL sudah diproses dan berhasil
    if base_url in processed_article_urls and processed_article_urls[base_url] == "berhasil":
        logger.info(f"⚠️ URL sudah diproses sebelumnya dan berhasil: {base_url}, melewati scraping.")
        return

    retry_count = 0
    while retry_count < max_retries:
        driver = setup_driver()
        try:
            logger.info(f"🔍 Mulai scraping: {base_url} (Percobaan ke-{retry_count + 1})")
            page_number = 1
            while page_number <= max_pages:
                url = f"{base_url}&sortType=vol-only-newest&pageNumber={page_number}"
<<<<<<< HEAD
                logger.info(f"Membuka halaman {page_number}: {url}")

=======
                logger.info(f"📄 Membuka halaman {page_number}: {url}")
>>>>>>> abiyyu-v-crawling
                driver.get(url)

                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "col"))
                    )
                except:
<<<<<<< HEAD
                    logger.error(f"Halaman {page_number} gagal dimuat. Melanjutkan ke URL berikutnya.")
=======
                    logger.warning(f"⛔ Halaman {page_number} gagal dimuat.")
                    driver.save_screenshot(f"screenshot_gagal_page_{page_number}_retry{retry_count + 1}.png")
>>>>>>> abiyyu-v-crawling
                    break

                time.sleep(15)
                soup = BeautifulSoup(driver.page_source, "html.parser")
<<<<<<< HEAD
                articles = soup.find_all("div", class_="col result-item-align px-3")

                if not articles:
                    logger.warning(f"Tidak ada artikel ditemukan di halaman {page_number}.")
=======
                
                # Ambil semua link artikel dari halaman
                article_links = [
                    f"https://ieeexplore.ieee.org{link['href']}" 
                    for link in soup.find_all('a', href=True) 
                    if "/document/" in link['href'] and "/citations" not in link['href']
                ]
                
                if not article_links:
                    logger.warning(f"🚫 Tidak ada artikel di halaman {page_number}.")
>>>>>>> abiyyu-v-crawling
                    break

                # Ambil detail artikel untuk setiap link
                for article_url in article_links:
                    # Pastikan kita memproses hanya link ke artikel
                    if "/document/" in article_url:
                        logger.info(f"🔗 Mengunjungi artikel: {article_url}")
                        article_data = scrape_article_details(driver, article_url)
                        if not article_data.empty:
                            # Simpan artikel secara terpisah
                            save_article_separately(article_data.to_dict(orient='records')[0], OUTPUT_DIR)

<<<<<<< HEAD
                for article in articles:
                    h2_tag = article.find("h2")
                    title = h2_tag.find("a").text.strip() if h2_tag and h2_tag.find("a") else "Judul Tidak Ditemukan"

                    year_container = article.find("div", class_="description text-base-md-lh")
                    year = year_container.find("span").text.strip() if year_container and year_container.find("span") else "Tahun Tidak Ditemukan"

                    author_spans = article.find_all("span", attrs={"_ngcontent-ng-c893371016": True})
                    author_text = ", ".join(set(span.text.strip() for span in author_spans)).replace(";", "").strip(", ")

                    titles.append(title)
                    years.append(year)
                    authors.append(author_text)

                new_df = pd.DataFrame({
                    "Judul": titles,
                    "Tahun": years,
                    "Author": authors
                })

                append_and_save(new_df, output_path)
                logger.info(f"{len(articles)} artikel dari halaman {page_number} berhasil disimpan.")
=======
>>>>>>> abiyyu-v-crawling
                page_number += 1

            # Tandai URL sebagai sudah diproses dan berhasil
            processed_article_urls[base_url] = "berhasil"
            save_processed_article_urls()
            break
        except Exception as e:
<<<<<<< HEAD
            logger.error(f"Terjadi kesalahan saat scraping {row['URL']}: {e}")
=======
            logger.error(f"❌ Error scraping {base_url}: {e}")
            processed_article_urls[base_url] = "gagal"
            save_processed_article_urls()
        finally:
            driver.quit()
            logger.info("🛑 WebDriver ditutup.")
            retry_count += 1
>>>>>>> abiyyu-v-crawling

    if retry_count >= max_retries:
        logger.warning(f"⚠️ Melewati URL: {base_url}")
        processed_article_urls[base_url] = "gagal"
        save_processed_article_urls()

# =========================
# SCRAPE DETAIL ARTIKEL
# =========================

def scrape_article_details(driver, article_url):
    driver.get(article_url)
    
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "document-title"))
        )
    except Exception as e:
        logger.warning(f"⛔ Gagal memuat detail artikel: {article_url} - Error: {e}")
        return pd.DataFrame()

    time.sleep(1)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    
    title = soup.find("h1", class_="document-title")
    title = title.get_text(strip=True) if title else "Title Not Found"
    
    abstract_section = soup.find("div", attrs={"xplmathjax": True})
    abstract = abstract_section.get_text(strip=True) if abstract_section else "Abstract Not Found"
    
    author_spans = soup.find_all("span", attrs={"_ngcontent-ng-c1131135293": True})
    authors = ", ".join(sorted(set(span.text.strip() for span in author_spans if span.text.strip()))).strip(", ")

    journal_conference_name = "IEEE Access"
    publisher = "IEEE"
    year = soup.find("div", class_="doc-abstract-pubdate").get_text(strip=True).split()[-1] if soup.find("div", class_="doc-abstract-pubdate") else "Year Not Found"
    
    doi_link = soup.find("div", class_="stats-document-abstract-doi")
    doi = doi_link.find("a", href=True)["href"] if doi_link and doi_link.find("a", href=True) else "DOI Not Found"
    
    group_name = "OpsA"

    article_data = {
        "title": title,
        "abstract": abstract,
        "authors": authors,
        "journal_conference_name": journal_conference_name,
        "publisher": publisher,
        "year": year,
        "doi": doi,
        "group_name": group_name,
        "url": article_url
    }

    return pd.DataFrame([article_data])

# =========================
# 🚀 MAIN FUNCTION
# =========================

def main():
    try:
        global processed_article_urls
        processed_article_urls = load_processed_article_urls()  # Memuat URL yang sudah diproses
        df = read_json(DATA_PATH)
        logger.info(f"📊 Total URL yang akan diproses: {len(df)}")
        logger.info(f"Contoh URL pertama: {df['URL'].iloc[0]}")
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(scrape_from_url, row) for row in df.to_dict("records")]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"❌ Exception dalam thread: {e}")
    except Exception as e:
        logger.critical(f"❌ Program gagal dijalankan: {e}")

if __name__ == "__main__":
    main()