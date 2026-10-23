import pandas as pd
import time
import json
import logging
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from urllib.parse import urlparse
from pathlib import Path

# =========================
# CONFIGURATION
# =========================

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"
OUTPUT_DIR = BASE_DIR / "data" / "raw" / "output"
LOG_DIR = BASE_DIR / "logs"
PROCESSED_ARTICLE_URLS_FILE = DATA_DIR / "processed_article_urls.json"
OUTPUT_PATH = OUTPUT_DIR / "scraped_articles.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# =========================
# LOGGING
# =========================

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.hasHandlers():
    ch = logging.StreamHandler()
    fh = logging.FileHandler(LOG_DIR / "scraping.log", encoding="utf-8")
    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    ch.setFormatter(fmt)
    fh.setFormatter(fmt)
    logger.addHandler(ch)
    logger.addHandler(fh)

REPOSITORY_STRATEGIES = {
    "ieeexplore.ieee.org": {
        "article_list_selector": ("CLASS_NAME", "List-results-items"),
        "wait_timeout": 10,
        "article_link_filter": lambda href: "/document/" in href and "/citations" not in href,
        "detail": {
            "wait_selector": ("CLASS_NAME", "document-title"),
            "title": lambda soup: (soup.find("h1", class_="document-title") or None),
            "abstract": lambda soup: soup.find("div", attrs={"xplmathjax": True}),
            "authors": lambda soup: ", ".join(sorted(set(
                s.text.strip() for s in soup.find_all("span", attrs={"_ngcontent-ng-c1131135293": True})
                if s.text.strip()
            ))),
            "year": lambda soup: (soup.find("div", class_="doc-abstract-pubdate").get_text(strip=True).split()[-1]
                                  if soup.find("div", class_="doc-abstract-pubdate") else "Year Not Found"
                                  ),
            "doi": lambda soup: (soup.find("div", class_="stats-document-abstract-doi").find("a", href=True)["href"]
                                  if soup.find("div", class_="stats-document-abstract-doi") else "DOI Not Found"
                                  ),
            "publisher": "IEEE",
            "journal": "IEEE Access"
        },
        "pagination": True,
        "next_btn_selector": "li.next-btn > button[class^='stats-Pagination_arrow_next_']",
        "page_param": "pageNumber",
        "rows_param": "rowsPerPage=100",
    },

    "arxiv.org": {
        "article_list_selector": ("ID", "articles"),
        "wait_timeout": 10,
        "article_link_filter": lambda href: (
            "/abs/" in href and not any(x in href for x in ["/search", "/find", "/help", "/about", "?"])
        ),
        "detail": {
            "wait_selector": ("TAG_NAME", "h1"),
            "title": lambda soup: soup.find("h1", class_="title"),
            "abstract": lambda soup: soup.find("blockquote", class_="abstract"),
            "authors": lambda soup: (
                ", ".join(
                    m["content"] for m in soup.find_all("meta", attrs={"name": "citation_author"})
                ) or
                ", ".join(
                    a.text.strip() for a in soup.find_all(
                        "a", href=lambda h: h and "searchtype=author" in h
                    )
                ) or
                "Authors Not Found"
            ),
            "year": lambda soup: (
                (m["content"][:4] if (m := soup.find("meta", attrs={"name": "citation_date"})) else None) or
                next(
                    (line.strip().split()[-1]
                    for line in soup.find("div", class_="submission-history").get_text().splitlines()
                    if "Submitted" in line),
                    None
                ) if soup.find("div", class_="submission-history") else None or
                "Year Not Found"
            ),
            "doi": lambda soup: (
                m["content"]
                if (m := soup.find("meta", attrs={"name": "citation_doi"})) 
                else (
                    f"arXiv:{m['content']}" if (m := soup.find("meta", attrs={"name": "citation_arxiv_id"}))
                    else "DOI Not Found"
                )
            ),
            "publisher": "arXiv",
            "journal": lambda soup: (
                m["content"]
                if (m := soup.find("meta", attrs={"name": "citation_journal_title"})) 
                else "arXiv"
            )
        },
        "pagination": True,
        "next_btn_selector": "a.pagination-next",
        "page_param": "start",
        "rows_param": None,
    },
}

def get_strategy(url: str) -> dict:
    domain = urlparse(url).netloc.replace("www.", "")
    strategy = REPOSITORY_STRATEGIES.get(domain)
    if not strategy:
        logger.warning(f"Domain '{domain}' not recognized. Using default strategy.")
    return strategy

def setup_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--enable-unsafe-swiftshader")
    options.add_argument("--disable-cache")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(options=options)
    logger.info("WebDriver initialized")

    return driver

def load_processed_urls() -> dict:
    if PROCESSED_ARTICLE_URLS_FILE.exists():
        with open(PROCESSED_ARTICLE_URLS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_processed_urls(processed_urls: dict):
    with open(PROCESSED_ARTICLE_URLS_FILE, "w", encoding="utf-8") as f:
        json.dump(processed_urls, f, ensure_ascii=False, indent=4)

def append_and_save(new_data: pd.DataFrame, output_path: Path):
    output_path = Path(output_path)

    existing = pd.DataFrame()
    if output_path.exists() and output_path.stat().st_size > 0:
        try:
            existing = pd.read_json(output_path)
        except ValueError:
            logger.warning(f"File corrupt: {output_path}. Backuping and starting new file.")
            output_path.rename(output_path.with_suffix(".backup.json"))
            existing = pd.DataFrame()

    combined = pd.concat([existing, new_data], ignore_index=True) if not existing.empty else new_data
    combined = combined.drop_duplicates(subset=["url"], keep="first")
    combined = combined.loc[:, ~combined.columns.str.match(r'^\d+$')]

    output_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = output_path.with_suffix(".tmp.json")
    combined.to_json(tmp_path, orient="records", indent=4)

    os.replace(tmp_path, output_path)
    logger.info(f"Saved {len(combined)} articles to {output_path}")

def get_arxiv_list_selector(url: str) -> tuple:
    if "/search" in url:
        return ("CLASS_NAME", "arxiv-result")
    elif "/list/" in url:
        return ("ID", "articles")
    elif "/abs/" in url:
        return ("TAG_NAME", "h1")
    else:
        return ("TAG_NAME", "body")

def scrape_article_details(driver, article_url: str, strategy: dict) -> pd.DataFrame:
    driver.get(article_url)
    detail = strategy["detail"]

    wait_by, wait_val = detail["wait_selector"]
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((getattr(By, wait_by), wait_val))
        )
    except Exception:
        logger.warning(f"Timeout waiting for article details to load: {article_url}")
        return pd.DataFrame()
    
    time.sleep(1)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    def extract(field):
        result = detail[field](soup)
        if result is None:
            return f"{field.capitalize()} Not Found"
        if isinstance(result, str):
            return result
        text = result.get_text(strip=True)
        for prefix in ["Title:", "Abstract:"]:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
        return text

    title    = extract("title")
    abstract = extract("abstract")
    authors  = extract("authors")
    year     = extract("year")
    doi      = extract("doi")

    journal = detail["journal"](soup) if callable(detail["journal"]) else detail["journal"]
    publisher = detail["publisher"](soup) if callable(detail["publisher"]) else detail["publisher"]

    return pd.DataFrame([{
        "title": title,
        "abstract": abstract,
        "authors": authors,
        "year": year,
        "doi": doi,
        "publisher": publisher,
        "journal_conference_name": journal,
        "url": article_url,
    }])

def build_page_url(base_url: str, strategy: dict, page_number: int) -> str:
    domain = urlparse(base_url).netloc.replace("www.", "")

    if domain == "ieeexplore.ieee.org":
        rows = strategy.get("rows_param", "rowsPerPage=100")
        param = strategy.get("page_param", "pageNumber")
        return f"{base_url}&{rows}&{param}={page_number}"
    
    elif domain == "arxiv.org":
        rows_per_page = 25
        start = (page_number - 1) * rows_per_page
        separator = "&" if "?" in base_url else "?"
        return f"{base_url}{separator}start={start}"
    
    else:
        if strategy and strategy.get("page_param"):
            separator = "&" if "?" in base_url else "?"
            return f"{base_url}{separator}{strategy['page_param']}={page_number}"
        return base_url
    
def scrape_titles_from_url(base_url: str, output_path: Path = OUTPUT_PATH, processed: dict = None) -> list[dict]:
    if processed is None:
        processed = load_processed_urls()
    
    strategy = get_strategy(base_url)

    if strategy is None:
        strategy = GENERIC_STRATEGY

    base_domain = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"
    domain = urlparse(base_url).netloc.replace("www.", "")

    driver = setup_driver()
    all_articles = []
    page_number = 1

    try:
        while True:         
            url = build_page_url(base_url, strategy, page_number)
            logger.info(f"Scraping page {page_number}: {url}")
            driver.get(url)

            if domain == "arxiv.org":
                wait_by, wait_val = get_arxiv_list_selector(url)
            else:
                wait_by, wait_val = strategy["article_list_selector"]

            try:
                WebDriverWait(driver, strategy.get("wait_timeout", 5)).until(
                    EC.presence_of_element_located((getattr(By, wait_by), wait_val))
                )
            except Exception:
                logger.warning(f"Failed to load page {page_number}. Ending pagination.")
                break
                
            time.sleep(1)
            soup = BeautifulSoup(driver.page_source, "html.parser")

            link_filter = strategy.get("article_link_filter", lambda href: True)
            article_links = list(set([
                href if href.startswith("http") else base_domain + href
                for a in soup.find_all("a", href=True)
                if link_filter(a["href"])
                for href in [a["href"]]
            ]))

            if not article_links:
                logger.warning(f"No article links found on page {page_number}.")
                break

            logger.info(f"{len(article_links)} article links found on page {page_number}.")

            for article_url in article_links:
                if processed.get(article_url) == "success":
                    logger.info(f"Already processed (success): {article_url}")
                    continue

                article_df = scrape_article_details(driver, article_url, strategy)
                if not article_df.empty:
                    article_dict = article_df.to_dict(orient="records")[0]
                    all_articles.append(article_dict)
                    processed[article_url] = "success"

                    append_and_save(pd.DataFrame([article_dict]), output_path)
                    logger.info(f"Saved: {article_dict['title']}")
                else:
                    processed[article_url] = "failed"

                save_processed_urls(processed)
            
            if strategy.get("pagination"):
                next_btn = soup.select_one(strategy["next_btn_selector"])
                if next_btn:
                    page_number += 1
                    logger.info(f"Moving to page {page_number}")
                else:
                    logger.info("No next page button found.")
                    break
            else:
                break

        if all_articles:
            processed[base_url] = "success"
        else:
            processed[base_url] = "failed"
        save_processed_urls(processed)

    except Exception as e:
        logger.error(f"Error scraping {base_url}: {e}")
        processed[base_url] = "failed"
        save_processed_urls(processed)

    finally:
        driver.quit()
        logger.info("WebDriver closed.")
    
    return all_articles

def scrape_titles(base_urls: list[str], output_path: Path = OUTPUT_PATH) -> list[dict]:
    processed = load_processed_urls()
    all_results = []

    for url in base_urls:
        logger.info(f"Starting scrape for: {url}")
        results = scrape_titles_from_url(url, output_path, processed)
        all_results.extend(results)
        logger.info(f"Finished scrape for: {url}")

    return all_results

if __name__ == "__main__":
    import argparse
    from getLinks import scrape_links

    parser = argparse.ArgumentParser()
    parser.add_argument("--urls", nargs="+", help="List of base URLs to scrape titles from")
    parser.add_argument("--from-json", action="store_true", help="Baca URLs dari article_links.json")
    args = parser.parse_args()

    if args.urls:
        scrape_titles(args.urls)
    elif args.from_json:
        DATA_PATH = DATA_DIR / "article_links.json"
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        scrape_titles(data["URL"])
    else:
        print("Please provide URLs with --urls or use --from-json to read from article_links.json")/4/4