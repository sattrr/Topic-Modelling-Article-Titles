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
from webdriver_manager.chrome import ChromeDriverManager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"
DATA_PATH = DATA_DIR / "article_links.json"
OUTPUT_JSON_PATH = DATA_DIR / "scraped_articles.json"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

def setup_driver():
    service = Service(ChromeDriverManager().install())
    options = Options()
    options.add_argument("--disable-gpu")
    # options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-cache")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    return webdriver.Chrome(service=service, options=options)

def read_json(json_path):
    with open(json_path, "r", encoding="utf-8") as file:
        data = json.load(file)
    return pd.DataFrame(data["URL"], columns=["URL"])

def read_existing_output(output_path):
    if Path(output_path).exists():
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
        try:
            base_url = row["URL"]
            logger.info(f"Mulai scraping dari: {base_url}")

            page_number = 1
            while not max_pages or page_number <= max_pages:
                url = f"{base_url}&sortType=vol-only-newest&pageNumber={page_number}"
                logger.info(f"Membuka halaman {page_number}: {url}")

                driver.get(url)
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "col"))
                    )
                except:
                    logger.error(f"Halaman {page_number} gagal dimuat. Melanjutkan ke URL berikutnya.")
                    break

                time.sleep(3)

                soup = BeautifulSoup(driver.page_source, "html.parser")
                articles = soup.find_all("div", class_="col result-item-align px-3")

                if not articles:
                    logger.warning(f"Tidak ada artikel ditemukan di halaman {page_number}.")
                    break

                titles = []
                years = []
                authors = []

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
                page_number += 1

        except Exception as e:
            logger.error(f"Terjadi kesalahan saat scraping {row['URL']}: {e}")


if __name__ == "__main__":
    driver = setup_driver()
    try:
        df = read_json(DATA_PATH)
        scrape_titles_per_page(df, driver, OUTPUT_JSON_PATH)
    finally:
        driver.quit()
