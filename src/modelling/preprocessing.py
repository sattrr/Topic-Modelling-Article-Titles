import os
import json
import pandas as pd
import re
import nltk
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
DATA_PATH = RAW_DATA_DIR / "scraped_articles.json"
CLEANED_DATA_DIR = BASE_DIR / "data" / "cleaned"
CLEANED_DATA_DIR.mkdir(parents=True, exist_ok=True)

def check_files():
    """Display all files in the raw directory for verification."""
    print(f"Checking directory: {RAW_DATA_DIR}")
    print("Available files:")
    for file in RAW_DATA_DIR.iterdir():
        print("-", file.name)

stop_words = set(stopwords.words("english"))
stop_words.update(["using"])
lemmatizer = WordNetLemmatizer()

def preprocess_text(text):
    text = text.lower()
    text = re.sub(r"[^a-z\s]", "", text)
    tokens = word_tokenize(text)
    cleaned_tokens = [
        lemmatizer.lemmatize(word) for word in tokens if word not in stop_words
    ]
    return " ".join(cleaned_tokens)

def load_data():
    """ Load dataset from JSON and apply preprocessing """
    if not DATA_PATH.exists():
        check_files()
        raise FileNotFoundError(f"File '{DATA_PATH}' tidak ditemukan. Pastikan nama dan lokasi benar.")
    
    with open(DATA_PATH, encoding="utf-8") as f:
        articles = json.load(f)

    df = pd.DataFrame(articles)

    if "Judul" not in df.columns:
        raise KeyError("Kolom 'Judul' tidak ditemukan dalam dataset.")

    df.rename(columns={"Judul": "article"}, inplace=True)
    df["article"] = df["article"].fillna("")

    df["clean_article"] = df["article"].apply(preprocess_text)
    df["word_count"] = df["clean_article"].apply(lambda x: len(x.split()))

    df["article"] = df["clean_article"]
    df.drop(columns=["clean_article"], inplace=True)

    return df

def apply_tfidf(df):
    """Extract features using TF-IDF."""
    vectorizer = TfidfVectorizer(max_features=500)
    tfidf_matrix = vectorizer.fit_transform(df["article"])
    return pd.DataFrame(tfidf_matrix.toarray(), columns=vectorizer.get_feature_names_out())

def apply_bert(df):
    """Get BERT embeddings using SentenceTransformer."""
    model = SentenceTransformer("all-MiniLM-L6-v2")
    bert_embeddings = model.encode(df["article"].tolist(), show_progress_bar=True)
    return pd.DataFrame(bert_embeddings)

if __name__ == "__main__":
    try:
        df_titles = load_data()

        tfidf_features = apply_tfidf(df_titles)

        bert_features = apply_bert(df_titles)

        output_dir = RAW_DATA_DIR / "TF-IDF"
        output_dir.mkdir(parents=True, exist_ok=True)

        cleaned_data_path = CLEANED_DATA_DIR / "cleaned_articles.json"
        df_titles.to_json(cleaned_data_path, orient="records", force_ascii=False, indent=4)
        print(f"Cleaned data saved to: {cleaned_data_path}")

        tfidf_features.to_json(output_dir / "tfidf_features.json", orient="records", force_ascii=False, indent=4)
        bert_features.to_json(output_dir / "bert_features.json", orient="records", force_ascii=False, indent=4)

        print("TF-IDF and BERT features successfully saved.")

    except Exception as e:
        print(f"Error: {e}")

