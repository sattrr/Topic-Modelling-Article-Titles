import pandas as pd
import json
import os
from pathlib import Path

# Define base and data directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "raw" / "output"
CLEANED_DIR = BASE_DIR / "data" / "cleaned"
CLEANED_FILE = CLEANED_DIR / "cleaned_articles.json"

# Function to remove backslashes and escape characters
def remove_backslashes(data):
    if isinstance(data, str):
        return data.replace("\\/", "/").replace("\\", "")
    return data

# Function to clean authors
def clean_authors(author_str):
    if pd.isna(author_str):
        return ""
    authors = [author.strip(" ;") for author in author_str.split(",") if author.strip(" ;")]
    return ", ".join(sorted(set(authors)))

# Function to clean individual JSON file
def clean_json_file(json_file_path):
    try:
        with open(json_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        if isinstance(data, list):
            if len(data) == 0:
                print(f"❌ Empty list in {json_file_path.name}. Skipping.")
                return None
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            df = pd.DataFrame([data])
        else:
            print(f"❌ Invalid JSON structure in {json_file_path.name}. Skipping.")
            return None
        
        if df.empty:
            print(f"❌ Empty dataframe after loading {json_file_path.name}. Skipping.")
            return None

        # Cleaning columns
        if 'authors' in df.columns:
            df['authors'] = df['authors'].apply(clean_authors)
        if 'doi' in df.columns:
            df['doi'] = df['doi'].apply(remove_backslashes)
        if 'url' in df.columns:
            df = df.drop(columns=['url'])

        df = df.drop_duplicates(subset=['title'], keep='first')
        df = df.applymap(remove_backslashes)

        return df

    except (json.JSONDecodeError, ValueError) as e:
        print(f"❌ Error reading {json_file_path.name}: {e}")
        return None

def delete_file(file_path):
    try:
        os.remove(file_path)
        print(f"✅ Deleted file: {file_path.name}")
    except Exception as e:
        print(f"❌ Failed to delete {file_path.name}. Error: {e}")

# Function to merge and clean data
def merge_and_clean_data():
    all_articles = []

    scraped_files = list(OUTPUT_DIR.glob("scraped_article_*.json"))  # << diperbaiki DI SINI
    
    if not scraped_files:
        print("❌ No scraped files found to clean. Exiting.")
        return

    for scraped_file in scraped_files:
        cleaned_df = clean_json_file(scraped_file)
        if cleaned_df is not None:
            all_articles.append(cleaned_df)
        else:
            delete_file(scraped_file)

    if not all_articles:
        print("❌ No valid data found after cleaning. Exiting.")
        return

    new_data_df = pd.concat(all_articles, ignore_index=True)

    # Load existing cleaned data if exists
    if CLEANED_FILE.exists():
        print("📂 Loading existing cleaned data...")
        try:
            existing_data_df = pd.read_json(CLEANED_FILE)
            combined_df = pd.concat([existing_data_df, new_data_df], ignore_index=True)

            # Drop duplicates
            if 'doi' in combined_df.columns:
                combined_df = combined_df.drop_duplicates(subset=['doi'], keep='first')
            else:
                combined_df = combined_df.drop_duplicates(subset=['title'], keep='first')
        except Exception as e:
            print(f"❌ Error loading existing cleaned file: {e}")
            combined_df = new_data_df
    else:
        print("📂 No existing cleaned file found. Creating new one...")
        combined_df = new_data_df

    # Final cleaning
    if 'url' in combined_df.columns:
        combined_df = combined_df.drop(columns=['url'])

    os.makedirs(CLEANED_DIR, exist_ok=True)

    # Save cleaned data
    with open(CLEANED_FILE, 'w', encoding='utf-8') as f:
        json.dump(combined_df.to_dict(orient='records'), f, ensure_ascii=False, indent=4)

    print(f"\n✅ Total titles after cleaning: {len(combined_df)}")
    print(f"✅ Cleaned data saved to: {CLEANED_FILE}")

    # After successful save, delete all scraped files
    print("\n🧹 Cleaning up scraped files...")
    for scraped_file in scraped_files:
        delete_file(scraped_file)

# Run the script
if __name__ == "__main__":
    merge_and_clean_data()
