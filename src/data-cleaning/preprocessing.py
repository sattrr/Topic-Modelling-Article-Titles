import os
from pathlib import Path
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sentence_transformers import SentenceTransformer

BASE_DIR = Path(__file__).resolve().parent.parent.parent 
DATA_DIR = BASE_DIR / "data" / "raw"
DATA_PATH = DATA_DIR / "JPTIIK_unlabeled.csv"

def check_files():
    """Menampilkan semua file dalam direktori raw untuk verifikasi."""
    print(f"Direktori yang dicek: {DATA_DIR}")
    print("File yang tersedia:")
    for file in DATA_DIR.iterdir():
        print("-", file.name)

def load_data():
    """ Load dataset dan tambahkan kolom jumlah kata. """
    if not DATA_PATH.exists():
        check_files()
        raise FileNotFoundError(f"File '{DATA_PATH}' tidak ditemukan. Pastikan nama dan lokasi benar.")
    
    df = pd.read_csv(DATA_PATH)

    if "article" not in df.columns:
        raise KeyError("Kolom 'article' tidak ditemukan dalam dataset. Pastikan nama kolom benar.")

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
        output_dir.mkdir(parents=True, exist_ok=True)  # Buat folder jika belum ada

        tfidf_features.to_csv(output_dir / "tfidf_features.csv", index=False)
        bert_features.to_csv(output_dir / "bert_features.csv", index=False)

        print("TF-IDF dan BERT embedding berhasil disimpan.")

    except Exception as e:
        print(f"Terjadi kesalahan: {e}")
