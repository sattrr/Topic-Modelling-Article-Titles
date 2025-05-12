import pandas as pd
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "raw" / "output"
CLEANED_DIR = BASE_DIR / "data" / "cleaned"

def remove_backslashes(data):
    if isinstance(data, str):
        data = data.replace("\\/", "/").replace("\\", "")
    return data

def clean_authors(author_str):
    if pd.isna(author_str):
        return ""
    
    authors = [author.strip(" ;") for author in author_str.split(",") if author.strip(" ;")]
    unique_authors = ", ".join(sorted(set(authors)))
    return unique_authors

def clean_json_file(json_file_path):
    try:
        with open(json_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            df = pd.DataFrame([data])
        else:
            print(f"Invalid structure in {json_file_path}. Skipping this file.")
            return None
       
        if 'authors' in df.columns:
            df["authors"] = df["authors"].apply(clean_authors)
        
        if 'doi' in df.columns:
            df["doi"] = df["doi"].apply(remove_backslashes)
        
        if 'url' in df.columns:
            df = df.drop(columns=['url'])
        
        if 'title' in df.columns:
            df = df.drop_duplicates(subset=["title"], keep="first")
        
        df = df.applymap(remove_backslashes)
        
        return df
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error reading {json_file_path}: {e}")
        return None  
    
def delete_problematic_file(file_path):
    try:
        os.remove(file_path)
        print(f"Successfully deleted problematic file: {file_path}")
    except Exception as e:
        print(f"Failed to delete problematic file {file_path}. Error: {e}")

def merge_and_clean_data():
    all_articles = []
    scraped_files = list(OUTPUT_DIR.glob("scraped_articles_*.json"))
    
    for scraped_file in scraped_files:
        cleaned_df = clean_json_file(scraped_file)
        if cleaned_df is not None:
            all_articles.append(cleaned_df)
        else:
            print(f"Skipping invalid file: {scraped_file}")
            delete_problematic_file(scraped_file) 

    if not all_articles:
        print("No valid data found after cleaning. Exiting.")
        return

    merged_df = pd.concat(all_articles, ignore_index=True)

    if 'doi' in merged_df.columns:
        merged_df = merged_df.drop_duplicates(subset=["doi"], keep="first")

    if 'url' in merged_df.columns:
        merged_df = merged_df.drop(columns=['url'])

    output_cleaned_path = CLEANED_DIR / "cleaned_articles.json"
    
    os.makedirs(CLEANED_DIR, exist_ok=True)

    with open(output_cleaned_path, 'w', encoding='utf-8') as f:
        json.dump(merged_df.to_dict(orient="records"), f, ensure_ascii=False, indent=4)

    total_titles = len(merged_df)
    print(f"\nTotal titles after cleaning: {total_titles}")
    print(f"The merged and cleaned data has been saved to: {output_cleaned_path}")

if __name__ == "__main__":
    merge_and_clean_data()
