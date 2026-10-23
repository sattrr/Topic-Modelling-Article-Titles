import pandas as pd
import time
import json
import os
import argparse
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urlparse, urljoin

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"
DATA_PATH = DATA_DIR / "article_links.json"

logger = logging.getLogger(__name__)

LINK_STRATEGIES = {
    "ieeexplore.ieee.org": lambda href: (
        ("/xpl/issues" in href or "/xpl/tocresult" in href) and
        "punumber" in href
    ),
    "arxiv.org": lambda href: (
        "/list" in href or
        ("/search/" in href and "query=" in href) or
        (
            "/abs/" in href and not any(x in href for x in ["/search", "/find", "/help", "/about", "?"])
        )
    ),
}

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

def scrape_links(url: str) -> list[str]:
    parsed = urlparse(url)
    base_domain = f"{parsed.scheme}://{parsed.netloc}"
    domain = parsed.netloc.replace("www.", "")

    link_filter = LINK_STRATEGIES.get(domain)

    driver = setup_driver()
    try:
        driver.get(url)
        time.sleep(5)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        volume_links = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            full_url = href if href.startswith("http") else base_domain + href

            if link_filter:
                if link_filter(full_url):
                    volume_links.add(full_url)
            else:
                if (full_url.startswith(base_domain) and
                    not any(x in full_url for x in ["/search", "/find", "/help", "/about", "?"])):
                    volume_links.add(full_url)
        
        logger.info(f"Scraped {len(volume_links)} links from {url}")
        return list(volume_links)
    
    finally:
        driver.quit()

def save_links(links: list[str], output_path: str = str(DATA_PATH)):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"URL": links}, f, indent=4)
    logger.info(f"Saved {len(links)} links to {output_path}")                 