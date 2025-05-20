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
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# =========================
# CONFIGURATION
# =========================

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"
OUTPUT_DIR = BASE_DIR / "data" / "raw" / "output"  
LOG_DIR = BASE_DIR / "logs"
PROCESSED_ARTICLE_URLS_FILE = BASE_DIR / "data" / "raw" / "processed_article_urls.json"
processed_article_urls = {}
DATA_PATH = DATA_DIR / "article_links.json"
OUTPUT_PATH = OUTPUT_DIR / "scraped_articles.json"
log_file_path = LOG_DIR / "scraping.log"

DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# =========================
# LOGGING SETUP
# ========================= 

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ch = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
fh = logging.FileHandler(log_file_path, encoding="utf-8")
fh.setFormatter(formatter)

if not logger.hasHandlers():
    logger.addHandler(ch)
    logger.addHandler(fh)

# =========================
# SELENIUM DRIVER SETUP
# =========================

def setup_driver():
    try:
        service = Service(ChromeDriverManager(driver_version="135.0.7049.115").install())
        options = Options()
        ua = UserAgent()
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--ignore-ssl-errors")
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-cache")
        options.add_argument("--enable-unsafe-swiftshader")
        options.add_argument(f"--user-agent={user_agent}")
        options.add_argument("--window-size=1200,800") 
        options.add_argument("--lang=en-US")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--headless=new")

        driver = webdriver.Chrome(service=service, options=options)
        logger.info("WebDriver Initialized.")
        return driver
    except Exception as e:
        logger.error(f"Failed to setup WebDriver: {e}")
        raise

# =========================
# READ JSON INPUT FILE
# =========================

def read_json(json_path):
    try:
        with open(json_path, "r", encoding="utf-8") as file:
            data = json.load(file)
        if "URL" not in data or not data["URL"]:
            raise ValueError("JSON doesn't have key 'URL' or empty.")
        return pd.DataFrame(data["URL"], columns=["URL"])
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON: {e}. Process Continued.")
        return pd.DataFrame(columns=["URL"])
    except Exception as e:
        logger.critical(f"Another failed while reaading JSON: {e}")
        raise

def read_existing_output(output_path):
    if Path(output_path).exists():
        return pd.read_json(output_path)
    else:
        return pd.DataFrame(columns=["Judul", "Tahun", "Author"])

def append_and_save(new_data, output_path):
    output_path = Path(output_path)

    if output_path.is_dir():
        raise ValueError(f"output_path must be file, not folder: {output_path}")
    
    existing_data = read_existing_output(output_path)
    combined_data = pd.concat([existing_data, new_data], ignore_index=True)
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    combined_data.to_json(output_path, orient="records", indent=4)
    print(f"Data from this page added to: {output_path}")

def save_article_separately(article_data, output_dir):
    try:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        file_count = len(list(output_dir.glob("scraped_articles_*.json"))) + 1
        output_file = output_dir / f"scraped_articles_{file_count}.json"

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(article_data, f, ensure_ascii=False, indent=4)
        
        logger.info(f"Data saved into: {output_file}")
    except Exception as e:
        logger.error(f"Failed to save article: {e}")

def load_processed_article_urls():
    if PROCESSED_ARTICLE_URLS_FILE.exists():
        try:
            with open(PROCESSED_ARTICLE_URLS_FILE, "r", encoding="utf-8") as f:
                processed_article_urls = json.load(f)
            return processed_article_urls 
        except Exception as e:
            logger.error(f"Failed to read processed article list: {e}")
            return {}
    return {}

def save_processed_article_urls():
    try:
        with open(PROCESSED_ARTICLE_URLS_FILE, "w", encoding="utf-8") as f:
            json.dump(processed_article_urls, f, ensure_ascii=False, indent=4)
        logger.info("Saved processed URL list.")
    except Exception as e:
        logger.error(f"Failed to save processed URL list: {e}")

def scrape_article_details(driver, article_url):
    driver.get(article_url)
    
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CLASS_NAME, "document-title"))
        )
    except Exception as e:
        logger.warning(f"Failed to load details of article: {article_url} - Error: {e}")
        return pd.DataFrame()

    time.sleep(3)
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

def scrape_from_url(row, driver, output_path):
    base_url = row["URL"]

    try:
        logger.info(f"Scraping start: {base_url}")
        page_number = 1
        visited_page_urls = []

        while True:
            url = f"{base_url}&sortType=vol-only-newest&rowsPerPage=100&pageNumber={page_number}"
            logger.info(f"Open page {page_number}: {url}")
            driver.get(url)

            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "List-results-items"))
                )
            except Exception:
                logger.warning(f"Page {page_number} failed to load.")
                break

            time.sleep(3)

            soup = BeautifulSoup(driver.page_source, "html.parser")
            article_links = list(set([
                f"https://ieeexplore.ieee.org{a['href']}"
                for a in soup.find_all("a", href=True)
                if "/document/" in a['href'] and "/citations" not in a['href']
            ]))

            if not article_links:
                logger.warning(f"No articles found in page {page_number}.")
                break

            logger.info(f"{len(article_links)} article found in page {page_number}")

            titles, years, authors = [], [], []

            for article_url in article_links:
                if processed_article_urls.get(article_url) == "success":
                    logger.info(f"Already processed: {article_url}")
                    continue

                article_data = scrape_article_details(driver, article_url)
                if not article_data.empty:
                    save_article_separately(article_data.to_dict(orient="records")[0], OUTPUT_DIR)
                    processed_article_urls[article_url] = "success"
                else:
                    processed_article_urls[article_url] = "fail"

                save_processed_article_urls()

                title = article_data["title"].values[0] if not article_data.empty else "Title not found"
                year = article_data["year"].values[0] if not article_data.empty else "Year not found"
                author = article_data["authors"].values[0] if not article_data.empty else ""

                titles.append(title)
                years.append(year)
                authors.append(author)

            new_df = pd.DataFrame({
                "Judul": titles,
                "Tahun": years,
                "Author": authors
            })
            append_and_save(new_df, output_path)

            visited_page_urls.append(url)

            next_btn_soup = soup.select_one("li.next-btn > button[class^='stats-Pagination_arrow_next_']")
            if next_btn_soup:
                logger.info("Next (>) button found, go to next page.")
                page_number += 1
            else:
                logger.info("Next (>) button not found. Finished scraping this base URL.")
                break

        processed_article_urls[base_url] = "success"
        save_processed_article_urls()

        logger.info(f"{len(visited_page_urls)} page is processed from base URL: {base_url}")

        del visited_page_urls

    except Exception as e:
        logger.error(f"Error saat scraping {base_url}: {e}")
        processed_article_urls[base_url] = "fail"
        save_processed_article_urls()

# =========================
# MAIN FUNCTION
# =========================

def main():
    try:
        global processed_article_urls
        processed_article_urls = load_processed_article_urls()
        df = read_json(DATA_PATH)
        logger.info(f"Number of URL: {len(df)}")
        df_unprocessed = df[~df["URL"].isin(processed_article_urls.keys())]
        logger.info(f"Number of URL not processed yet: {len(df_unprocessed)}")
        driver = setup_driver()
        try:
            for row in df_unprocessed.to_dict("records"):
                scrape_from_url(row, driver, OUTPUT_PATH)
        finally:
            driver.quit()
            logger.info("WebDriver closed.")

        save_processed_article_urls()

    except Exception as e:
        logger.critical(f"Program failed: {e}")

if __name__ == "__main__":
    main()