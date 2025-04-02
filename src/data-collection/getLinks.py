import pandas as pd
import time
import json
import os
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

def setup_driver():
    service = Service(ChromeDriverManager().install())
    options = Options()
    options.add_argument("--disable-gpu")
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

def scrape_ieee_links():
    driver = setup_driver()
    try:
        target_url = "https://ieeexplore.ieee.org/xpl/issues?punumber=6287639&isnumber=10820123"
        driver.get(target_url)

        time.sleep(5)

        posts = driver.find_elements(By.CLASS_NAME, "issue-details-past-tabs")
        volume_links = set()

        for post in posts:
            link_tags = post.find_elements(By.TAG_NAME, "a")
            
            for link_tag in link_tags:
                href = link_tag.get_attribute("href")
                if href:
                    base_link = "https://ieeexplore.ieee.org" + href if href.startswith("/xpl") else href
                    volume_links.add(base_link)

        print(f"Ditemukan {len(volume_links)} link artikel unik:")
        for link in volume_links:
            print(link)

        os.makedirs(DATA_DIR, exist_ok=True)

        with open(DATA_PATH, "w", encoding="utf-8") as file:
            json.dump({"URL": list(volume_links)}, file, indent=4)

        print(f"Berhasil menyimpan {len(volume_links)} link ke {DATA_PATH}")
    
    finally:
        driver.quit()

if __name__ == "__main__":
    scrape_ieee_links()