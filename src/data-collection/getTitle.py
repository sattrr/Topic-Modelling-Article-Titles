import pandas as pd
import time
import json
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

def scrape_titles(df, driver, max_pages=5):
    all_titles = []
    all_years = []
    all_authors = []
    
    for index, row in df.iterrows():
        try:
            base_url = row["URL"]
            print(f"\nScraping artikel dari: {base_url}")

            page_number = 1
            while not max_pages or page_number <= max_pages:
                url = f"{base_url}&sortType=vol-only-newest&pageNumber={page_number}"
                print(f"Membuka halaman {page_number}: {url}")

                driver.get(url)
                
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "col"))
                    )
                except:
                    print(f"Halaman {page_number} gagal dimuat, lanjut ke URL berikutnya.")
                    break
                
                time.sleep(3)
                
                soup = BeautifulSoup(driver.page_source, "html.parser")
                articles = soup.find_all("div", class_="col result-item-align px-3")
                
                if not articles:
                    print(f"Halaman {page_number} kosong atau tidak ditemukan artikel baru.")
                    break
                
                for article in articles:
                    h2_tag = article.find("h2")
                    title = h2_tag.find("a").text.strip() if h2_tag and h2_tag.find("a") else "Judul Tidak Ditemukan"
                    
                    year_container = article.find("div", class_="description text-base-md-lh")
                    year = year_container.find("span").text.strip() if year_container and year_container.find("span") else "Tahun Tidak Ditemukan"
                    
                    author_spans = article.find_all("span", attrs={"_ngcontent-ng-c893371016": True})
                    authors = ", ".join(set(span.text.strip() for span in author_spans)).replace(";", "").strip(", ")
                    
                    all_titles.append(title)
                    all_years.append(year)
                    all_authors.append(authors)
                
                print(f"Berhasil scraping {len(articles)} artikel dari halaman {page_number}")
                page_number += 1
        
        except KeyError as e:
            print(f"Error: Kolom 'URL' tidak ditemukan. Error: {e}")
        except Exception as e:
            print(f"Terjadi kesalahan saat scraping {base_url}: {e}")
    
    return pd.DataFrame({
        'Judul': all_titles,
        'Tahun': all_years,
        'Author': all_authors
    })

def save_to_json(output_df, output_json_path):
    output_dir = Path(output_json_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    output_df.to_json(output_json_path, orient="records", indent=4)
    print(f"\nHasil scraping telah disimpan ke: {output_json_path}")

if __name__ == "__main__":
    driver = setup_driver()
    try:
        df = read_json(DATA_PATH)
        output_df = scrape_titles(df, driver)
        save_to_json(output_df, OUTPUT_JSON_PATH)
    finally:
        driver.quit()