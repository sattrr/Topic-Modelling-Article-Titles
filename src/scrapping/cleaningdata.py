import pandas as pd

def clean_authors(author_str):
    if pd.isna(author_str):
        return ""
    
    authors = [author.strip(" ;") for author in author_str.split(",") if author.strip(" ;")]
    unique_authors = ", ".join(sorted(set(authors)))
    return unique_authors

input_json_path = "../../data/raw/scraped_articles.json"
output_json_path = "../../data/cleaned/clean_title_articles.json"

df = pd.read_json(input_json_path)
df["Author"] = df["Author"].apply(clean_authors)
df = df.drop_duplicates(subset=["Judul"], keep="first")
df.to_json(output_json_path, orient="records", indent=4, force_ascii=False)

total_titles = len(df)
print(f"\nTotal judul setelah pembersihan: {total_titles}")
print(f"Hasil pembersihan disimpan di: {output_json_path}")
