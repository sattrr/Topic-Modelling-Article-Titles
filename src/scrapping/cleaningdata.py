import pandas as pd
import json
import os
from pathlib import Path

# Define the base and data directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "raw" / "output"  # This should be defined
CLEANED_DIR = BASE_DIR / "data" / "cleaned"  # Set the cleaned directory path

# Function to remove backslashes and escape characters from strings
def remove_backslashes(data):
    if isinstance(data, str):
        # Remove escape characters for JSON-safe strings: \/ and backslash \\
        data = data.replace("\\/", "/").replace("\\", "")
    return data  # Return non-string data unchanged

# Function to clean authors
def clean_authors(author_str):
    if pd.isna(author_str):
        return ""
    
    # Clean the author string by removing unwanted characters
    authors = [author.strip(" ;") for author in author_str.split(",") if author.strip(" ;")]
    unique_authors = ", ".join(sorted(set(authors)))  # Remove duplicates and sort the names
    return unique_authors

# Function to clean each JSON file
def clean_json_file(json_file_path):
    try:
        # Read the raw JSON data
        with open(json_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        # Check if data is a list of dictionaries
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            # If data is a dictionary, wrap it in a list to make it processable
            df = pd.DataFrame([data])
        else:
            print(f"❌ Invalid structure in {json_file_path}. Skipping this file.")
            return None  # Invalid structure
       
        # Clean the 'authors' column
        if 'authors' in df.columns:
            df["authors"] = df["authors"].apply(clean_authors)
        
        # Clean DOI to remove escape characters
        if 'doi' in df.columns:
            df["doi"] = df["doi"].apply(remove_backslashes)
        
        # Drop the 'url' column if it exists
        if 'url' in df.columns:
            df = df.drop(columns=['url'])
        
        # Drop duplicates based on 'title' column
        if 'title' in df.columns:
            df = df.drop_duplicates(subset=["title"], keep="first")
        
        # Remove backslashes in all string fields
        df = df.applymap(remove_backslashes)
        
        return df
    except (json.JSONDecodeError, ValueError) as e:
        print(f"❌ Error reading {json_file_path}: {e}")
        return None  
    
def delete_problematic_file(file_path):
    try:
        os.remove(file_path)
        print(f"✅ Successfully deleted problematic file: {file_path}")
    except Exception as e:
        print(f"❌ Failed to delete problematic file {file_path}. Error: {e}")

# Function to merge and clean data
def merge_and_clean_data():
    all_articles = []

    # List all the JSON files in the output directory
    scraped_files = list(OUTPUT_DIR.glob("scraped_articles_*.json"))
    
    # Process each file
    for scraped_file in scraped_files:
        cleaned_df = clean_json_file(scraped_file)
        if cleaned_df is not None:
            all_articles.append(cleaned_df)
        else:
            print(f"❌ Skipping invalid file: {scraped_file}")
            delete_problematic_file(scraped_file)  # Delete problematic file

    # Check if any data was collected
    if not all_articles:
        print("No valid data found after cleaning. Exiting.")
        return

    # Concatenate all DataFrames into one
    merged_df = pd.concat(all_articles, ignore_index=True)

    # Hapus duplikat berdasarkan DOI, hanya menyimpan satu artikel per DOI
    if 'doi' in merged_df.columns:
        merged_df = merged_df.drop_duplicates(subset=["doi"], keep="first")

    # Drop the 'url' column if it exists
    if 'url' in merged_df.columns:
        merged_df = merged_df.drop(columns=['url'])

    # Save the cleaned and merged data to a JSON file
    output_cleaned_path = CLEANED_DIR / "cleaned_articles.json"
    
    # Make the output directory if it doesn't exist
    os.makedirs(CLEANED_DIR, exist_ok=True)

    # Use a custom method to dump JSON without escape characters for URLs and DOI
    with open(output_cleaned_path, 'w', encoding='utf-8') as f:
        json.dump(merged_df.to_dict(orient="records"), f, ensure_ascii=False, indent=4)

    total_titles = len(merged_df)
    print(f"\n✅ Total titles after cleaning: {total_titles}")
    print(f"✅ The merged and cleaned data has been saved to: {output_cleaned_path}")

# Run the script
if __name__ == "__main__":
    merge_and_clean_data()  # Merge and clean the data
