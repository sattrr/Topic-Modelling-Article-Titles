import os
import json
import pandas as pd
import re
import nltk
import argparse
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sentence_transformers import SentenceTransformer
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer
from nltk.stem import PorterStemmer

nltk.download("punkt")
nltk.download("stopwords")
nltk.download("wordnet")
nltk.download("punkt_tab")

BASE_DIR = Path(__file__).resolve().parent.parent.parent 
RAW_DATA_DIR = BASE_DIR / "data" / "raw"
OUTPUT_DIR = RAW_DATA_DIR / "output"
CLEANED_DATA_DIR = BASE_DIR / "data" / "cleaned"
CLEANED_DATA_DIR.mkdir(parents=True, exist_ok=True)

DATA_PATHS = [
    OUTPUT_DIR / "scraped_articles.json",
    RAW_DATA_DIR / "scraped_articles.json",
]

stop_words = set(stopwords.words("english"))
stop_words.update(["using"])
lemmatizer = WordNetLemmatizer()

def find_data_file() -> Path:
    for path in DATA_PATHS:
        if path.exists() and path.stat().st_size > 0:
            print(f"Using data file: {path}")
            return path
    raise FileNotFoundError(
        f"No scraping files found. Please ensure one of the following exists:\n" +
        "\n".join(f"  - {p}" for p in DATA_PATHS)
    )

def clean_authors(author_str: str) -> str:
    if pd.isna(author_str) or not str(author_str).strip():
        return ""
    authors = [a.strip(" ;,") for a in str(author_str).split(",") if a.strip(" ;,")]
    return ", ".join(sorted(set(authors)))

def preprocess_text(text: str) -> str:
    text = str(text).lower()
    text = re.sub(r"[^a-z\s]", "", text)
    tokens = word_tokenize(text)
    cleaned = [lemmatizer.lemmatize(w) for w in tokens if w not in stop_words]
    return " ".join(cleaned)

STANDARD_COLUMNS = [
    "title", "abstract", "authors",
    "journal_conference_name", "publisher",
    "year", "doi", "group_name", "url"
]

def normalize_record(record: dict) -> dict:
    title = (
        record.get("title") or record.get("Title") or record.get("judul") or "Title Not Found"
    )

    abstract = (
        record.get("abstract") or record.get("Abstract") or "Abstract Not Found"
    )

    authors = (
        record.get("authors") or record.get("Author") or "Author Not Found"
    )

    journal = (
        record.get("journal_conference_name") or record.get("Journal") or "Journal/Conference Not Found"
    )

    publisher = (
        record.get("publisher") or record.get("Publisher") or "Publisher Not Found"
    )

    year = (
        record.get("year") or record.get("Year") or record.get("Tahun") or "Year Not Found"
    )

    doi = record.get("doi", "DOI Not Found")

    group_name = record.get("group_name", "")

    url = record.get("url", "")

    return {
        "title": str(title).strip(),
        "abstract": str(abstract).strip(),
        "authors": clean_authors(authors),
        "journal_conference_name": str(journal).strip(),
        "publisher": str(publisher).strip(),
        "year": str(year).strip(),
        "doi": str(doi).strip(),
        "group_name": str(group_name).strip(),
        "url": str(url).strip()
    }

def load_data(data_path: Path = None) -> pd.DataFrame:
    if data_path is None:
        data_path = find_data_file()

    with open(data_path, encoding="utf-8") as f:
        articles = json.load(f)

    normalized_records = [normalize_record(rec) for rec in articles]
    df = pd.DataFrame(normalized_records)
    
    invalid_titles = [
        "title not found", "judul tidak ditemukan",
        "judul not found", "", "none"
    ]
    df = df[~df["title"].str.lower().str.strip().isin(invalid_titles)]

    df = df.drop_duplicates(subset=["title"], keep="first")
    df = df.drop_duplicates(subset=["doi"], keep="first")

    print(f"Records after cleaning: {len(df)}")

    df["clean_title"] = df["title"].apply(preprocess_text)
    df["word_count"] = df["clean_title"].apply(lambda x: len(x.split()))

    df = df[df["word_count"] >= 3]
    df = df[df["clean_title"].apply(lambda x: isinstance(x, str) and len(x.strip()) > 0)]

    print(f"Records after preprocessing: {len(df)}")
    return df

def apply_tfidf(df):
    vectorizer = TfidfVectorizer(max_features=500)
    tfidf_matrix = vectorizer.fit_transform(df["article"])
    return pd.DataFrame(tfidf_matrix.toarray(), columns=vectorizer.get_feature_names_out())

def apply_bert(df):
    model = SentenceTransformer("all-MiniLM-L6-v2")
    bert_embeddings = model.encode(df["article"].tolist(), show_progress_bar=True)
    return pd.DataFrame(bert_embeddings)

def clean_data(data_path: Path = None, output_filename: str = "cleaned_articles_combined.json") -> pd.DataFrame:
    df = load_data(data_path)
    cleaned_path = CLEANED_DATA_DIR / output_filename
    tmp_path = cleaned_path.with_suffix(".tmp.json")
    df.to_json(tmp_path, orient="records", force_ascii=False, indent=4)
    os.replace(tmp_path, cleaned_path)
    print(f"Cleaned data saved: {cleaned_path} ({len(df)} records)")
    return df


def clean_and_combine(arxiv_path: Path = None, ieee_path: Path = None, output_filename: str = "cleaned_articles_combined.json") -> pd.DataFrame:
    all_dfs = []

    arxiv_source = arxiv_path or find_data_file()
    if arxiv_source.exists() and arxiv_source.stat().st_size > 0:
        df_arxiv = load_data(arxiv_source)
        df_arxiv["source"] = "arxiv"
        all_dfs.append(df_arxiv)
        print(f"arXiv loaded: {len(df_arxiv)} records")
    else:
        print(f"Warning: arXiv file not found: {arxiv_source}")

    ieee_source = ieee_path or (BASE_DIR / "data" / "cleaned" / "cleaned_articles_ieee.json")
    if ieee_source.exists() and ieee_source.stat().st_size > 0:
        df_ieee = load_data(ieee_source)
        df_ieee["source"] = "ieee"
        all_dfs.append(df_ieee)
        print(f"IEEE loaded: {len(df_ieee)} records")
    else:
        print(f"Warning: IEEE file not found: {ieee_source}")

    if not all_dfs:
        raise FileNotFoundError("No valid data files found.")

    combined = pd.concat(all_dfs, ignore_index=True)
    combined = combined.dropna(subset=["title"])
    combined = combined[combined["title"].str.strip() != ""]
    combined = combined.drop_duplicates(subset=["title"], keep="first")
    combined = combined.reset_index(drop=True)

    print(f"Combined total: {len(combined)} records")
    print(f"Source breakdown: {combined['source'].value_counts().to_dict()}")

    cleaned_path = CLEANED_DATA_DIR / output_filename
    tmp_path = cleaned_path.with_suffix(".tmp.json")
    combined.to_json(tmp_path, orient="records", force_ascii=False, indent=4)
    os.replace(tmp_path, cleaned_path)
    print(f"Saved: {cleaned_path}")

    return combined

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean and preprocess article data.")
    parser.add_argument("--data-path", type=Path, help="Path to the raw data file.")
    args = parser.parse_args()

    data_path = Path(args.data_path) if args.data_path else None

    try:
        df_titles = load_data(data_path)

        if args.save_features:
            feature_dir = RAW_DATA_DIR / "TF_IDF"
            feature_dir.mkdir(parents=True, exist_ok=True)

            print("Extracting TF-IDF features...")
            tfidf = apply_tfidf(df)
            tfidf.to_json(feature_dir / "tfidf_features.json", orient="records", force_ascii=False, indent=4)

            print("Extracting BERT embeddings...")
            bert = apply_bert(df)
            bert.to_json(feature_dir / "bert_features.json", orient="records", force_ascii=False, indent=4)

            print("Features saved")

        print(f"\Done, {len(df)} articles cleaned.")
    
    except Exception as e:
        print(f"Error: {e}")
        raise