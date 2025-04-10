import os
import json
from pathlib import Path
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sentence_transformers import SentenceTransformer

BASE_DIR = Path(__file__).resolve().parent.parent.parent 
DATA_DIR = BASE_DIR / "data" / "raw"
DATA_PATH = DATA_DIR / "scraped_articles.json"

def check_files():
    """Menampilkan semua file dalam direktori raw untuk verifikasi."""
    print(f"Direktori yang dicek: {DATA_DIR}")
    print("File yang tersedia:")
    for file in DATA_DIR.iterdir():
        print("-", file.name)

def load_data():
    """ Load dataset dari JSON dan tambahkan kolom jumlah kata. """
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
    df["word_count"] = df["article"].apply(lambda x: len(x.split()))

    return df

def apply_tfidf(df):
    """ Menggunakan TF-IDF untuk ekstraksi fitur dari teks. """
    vectorizer = TfidfVectorizer(max_features=500)
    tfidf_matrix = vectorizer.fit_transform(df["article"])
    return pd.DataFrame(tfidf_matrix.toarray(), columns=vectorizer.get_feature_names_out())

def apply_bert(df):
    """ Menggunakan SentenceTransformer untuk mendapatkan embedding BERT dari teks. """
    model = SentenceTransformer("all-MiniLM-L6-v2")
    bert_embeddings = model.encode(df["article"].tolist())
    return pd.DataFrame(bert_embeddings)

if __name__ == "__main__":
    try:
        df_titles = load_data()

        tfidf_features = apply_tfidf(df_titles)

        bert_features = apply_bert(df_titles)

        output_dir = DATA_DIR / "TF-IDF"
        output_dir.mkdir(parents=True, exist_ok=True)

        tfidf_features.to_json(output_dir / "tfidf_features.json", orient="records", force_ascii=False, indent=4)
        bert_features.to_json(output_dir / "bert_features.json", orient="records", force_ascii=False, indent=4)

        print("TF-IDF dan BERT embedding berhasil disimpan.")

    except Exception as e:
        print(f"Terjadi kesalahan: {e}")
