import mlflow
import mlflow.sklearn
from bertopic import BERTopic
import pandas as pd
import matplotlib
matplotlib.use("Agg") 
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import json
import joblib
from pathlib import Path
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from src.scrapping.getLink import DATA_PATH
from umap import UMAP

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_DATA_DIR = BASE_DIR / "data" / "raw"
CLEAN_DATA_DIR = BASE_DIR / "data" / "cleaned"
CLUSTERED_DIR = CLEAN_DATA_DIR / "clustered"
TOPICMODELLING_DIR = CLEAN_DATA_DIR / "topic-modelling"
MODEL_DIR = BASE_DIR / "models"
LOG_DIR = BASE_DIR / "logs"

DATA_PATHS = {
    "combined": CLEAN_DATA_DIR / "cleaned_articles_combined.json",
    "arxiv": CLEAN_DATA_DIR / "cleaned_articles.json",
    "ieee": CLEAN_DATA_DIR / "cleaned_articles_ieee.json"
}

CLUSTERED_DIR.mkdir(parents=True, exist_ok=True)
TOPICMODELLING_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

def load_articles(paths: dict = None) -> pd.DataFrame:
    if paths is None:
        paths = DATA_PATHS

    combined_path = CLEAN_DATA_DIR / "cleaned_articles_combined.json"
    if combined_path.exists() and combined_path.stat().st_size > 0:
        print(f"Using combined file: {combined_path}")
        paths = {"combined": combined_path}

    all_dfs = []
    for source, path in paths.items():
        if not path.exists():
            print(f"Warning: File tidak ditemukan: {path}")
            continue
        if path.stat().st_size == 0:
            print(f"Warning: File kosong: {path}")
            continue

        with open(path, encoding="utf-8") as f:
            articles = json.load(f)

        df = pd.DataFrame(articles)

        if "title" in df.columns:
            df["article"] = df["title"]
        elif "clean_title" in df.columns:
            df["article"] = df["clean_title"]
        elif "Judul" in df.columns:
            df["article"] = df["Judul"]
        else:
            print(f"Warning: Tidak ada kolom title di {path}. Skip.")
            continue

        if "source" not in df.columns:
            df["source"] = source

        all_dfs.append(df)
        print(f"Loaded {len(df)} articles from {source} ({path.name})")

    if not all_dfs:
        raise FileNotFoundError("Tidak ada data yang bisa dimuat.")

    combined = pd.concat(all_dfs, ignore_index=True)
    combined = combined.dropna(subset=["article"])
    combined = combined[combined["article"].str.strip() != ""]
    combined = combined.drop_duplicates(subset=["article"], keep="first")
    combined = combined.reset_index(drop=True)

    print(f"Total articles loaded: {len(combined)}")
    print(f"Source breakdown: {combined['source'].value_counts().to_dict()}")
    return combined

def vectorize_and_reduce(df):
    df = df.copy()
    df["article"] = df["article"].astype(str).str.strip()
    df = df[df["article"].str.len() > 0]
    df = df.dropna(subset=["article"])

    vectorizer = TfidfVectorizer(max_features=500)
    features_tfidf = vectorizer.fit_transform(df['article'])

    pca = PCA(n_components=2)
    features_pca = pca.fit_transform(features_tfidf.toarray())
    
    return features_tfidf, features_pca

def perform_clustering(features_pca, n_clusters):
    features_pca = np.array(features_pca, dtype=float)
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(features_pca)
    silhouette = silhouette_score(features_pca, labels)
    return labels, kmeans.cluster_centers_, silhouette

def save_clustered_data(df, clustered_dir):
    for cluster in df["cluster"].unique():
        cluster_data = df[df["cluster"] == cluster].to_dict(orient="records")
        with open(clustered_dir / f"cluster_{cluster}.json", "w", encoding="utf-8") as f:
            json.dump(cluster_data, f, indent=4, ensure_ascii=False)

def calculate_cosine_similarity_coherence(topic_terms, vectorizer):
    documents = [' '.join(topic) for topic in topic_terms]
    if not any(doc.strip() for doc in documents):
        print("All documents is empty or contain stopwords.")
        return 0.0

    topic_vectors = vectorizer.fit_transform(documents)
    similarity_matrix = cosine_similarity(topic_vectors)

    coherence_scores = [
        similarity_matrix[i, j]
        for i in range(len(topic_terms))
        for j in range(i + 1, len(topic_terms))
    ]
    return np.mean(coherence_scores) if coherence_scores else 0.0

def get_topic_coherence_from_bertopic(topic_model, cluster_data):
    topic_words = []
    valid_topic_ids = topic_model.get_topic_info()
    valid_topic_ids = valid_topic_ids[valid_topic_ids.Topic != -1]["Topic"].tolist()
    
    for topic_id in valid_topic_ids:
        terms = topic_model.get_topic(topic_id)
        words = [word.replace(" ", "_") for word, _ in terms]
        if isinstance(words, list) and all(isinstance(w, str) for w in words):
            topic_words.append(words)

    if not topic_words:
        print("There is no vaalid Topic Modelling. Coherence score set into 0.")
        return 0.0

    vectorizer = CountVectorizer(stop_words='english')
    return calculate_cosine_similarity_coherence(topic_words, vectorizer)

def run_modelling(n_cluster: int = 3, paths: dict = None) -> dict:
    if paths is None:
        paths = DATA_PATHS

    with mlflow.start_run():
        mlflow.log_param("n_clusters", n_cluster)
        mlflow.log_param("data_sources", list(paths.keys()))

        df = load_articles(paths)
        print(f"Total articles loaded: {len(df)}")
        df = df.reset_index(drop=True)

        for source, count in df["source"].value_counts().items():
            mlflow.log_param(f"num_articles_{source}", count)

        _, features_pca = vectorize_and_reduce(df)
        cluster_labels, centroids, silhouette = perform_clustering(features_pca, n_cluster)
        df["cluster"] = cluster_labels

        print(f"Silhouette Score: {silhouette:.4f}")
        mlflow.log_metric("silhouette_score", silhouette)

        save_clustered_data(df, CLUSTERED_DIR)

        viz_path = TOPICMODELLING_DIR / "clustering_visualization.png"
        n_sources = len(df["source"].unique()) if "source" in df.columns else 1

        if n_sources > 1:
            fig, axes = plt.subplots(1, 2, figsize=(16, 6))
            ax_cluster, ax_source = axes[0], axes[1]
        else:
            fig, ax_cluster = plt.subplots(1, 1, figsize=(8, 6))
            ax_source = None

        sns.scatterplot(
            ax=ax_cluster,
            x=features_pca[:, 0], y=features_pca[:, 1],
            hue=cluster_labels, palette="tab10", alpha=0.6
        )
        ax_cluster.scatter(
            centroids[:, 0], centroids[:, 1],
            c="black", marker="X", s=300, label="Centroids"
        )
        ax_cluster.set_title(f"KMeans Clusters (n={n_cluster})")
        ax_cluster.legend()

        if ax_source is not None and "source" in df.columns:
            sns.scatterplot(
                ax=ax_source,
                x=features_pca[:, 0], y=features_pca[:, 1],
                hue=df["source"], palette="Set1", alpha=0.6
            )
            ax_source.set_title("Data Source")

        plt.tight_layout()
        plt.savefig(viz_path)
        plt.close()
        mlflow.log_artifact(str(viz_path))

        print(f"\nRunning global BERTopic on {len(df)} articles...")
        titles = df["article"].tolist()
        n = len(titles)

        min_size = max(30, int(n * 0.0005))

        umap_model = UMAP(
            n_neighbors=15,
            n_components=5,
            min_dist=0.0,
            metric="cosine",
            random_state=42,
            low_memory=True
        )
        vectorizer_model = CountVectorizer(
            ngram_range=(1, 2),
            stop_words="english",
            min_df=10,
            max_df=0.85
        )

        topic_model = BERTopic(
            vectorizer_model=vectorizer_model,
            umap_model=umap_model,
            min_topic_size=min_size,
            nr_topics="auto",
            verbose=True,
            calculate_probabilities=False
        )

        topics, _ = topic_model.fit_transform(titles)
        df["topic"] = topics

        topic_info = topic_model.get_topic_info()
        valid_topics = topic_info[topic_info.Topic != -1]
        num_topics = len(valid_topics)
        outliers = int((pd.Series(topics) == -1).sum())
        coherence = get_topic_coherence_from_bertopic(topic_model, titles)

        print(f"Topics found: {num_topics}")
        print(f"Outliers: {outliers} ({outliers/n*100:.1f}%)")
        print(f"Coherence: {coherence:.4f}")

        mlflow.log_metric("num_topics", num_topics)
        mlflow.log_metric("coherence_score", coherence)
        mlflow.log_metric("outlier_ratio", round(outliers/n, 3))

        try:
            bar_path = TOPICMODELLING_DIR / "topics_barchart.html"
            topic_model.visualize_barchart(
                top_n_topics=min(20, num_topics)
            ).write_html(bar_path)
            mlflow.log_artifact(str(bar_path))
        except Exception as e:
            print(f"Barchart skipped: {e}")

        try:
            map_path = TOPICMODELLING_DIR / "topics_map.html"
            topic_model.visualize_topics().write_html(map_path)
            mlflow.log_artifact(str(map_path))
        except Exception as e:
            print(f"Topics map skipped: {e}")

        model_path = MODEL_DIR / "bertopic.pkl"
        joblib.dump(topic_model, model_path)
        print(f"Model saved: {model_path}")
        mlflow.log_artifact(str(model_path))

        topic_hyperparams = {
            "silhouette_score": round(silhouette, 4),
            "num_topics": num_topics,
            "coherence_score": round(coherence, 4),
            "outliers": outliers,
            "outlier_ratio": round(outliers/n, 3),
            "source_breakdown": df["source"].value_counts().to_dict() if "source" in df.columns else {},
        }

        json_output_path = LOG_DIR / "topic_info.json"
        with open(json_output_path, "w", encoding="utf-8") as f:
            json.dump(topic_hyperparams, f, indent=4, ensure_ascii=False)
        mlflow.log_artifact(str(json_output_path))

        results = {
            **topic_hyperparams,
            "n_clusters": n_cluster,
            "num_articles": n,
            "model_path": str(model_path),
            "clusters": {
                int(i): {
                    "num_articles": int((cluster_labels == i).sum()),
                }
                for i in range(n_cluster)
            },
            "top_topics": valid_topics.head(20).to_dict(orient="records"),
        }

        return results

def get_available_models() -> list[int]:
    model_path = MODEL_DIR / "bertopic.pkl"
    return [0] if model_path.exists() else []

def load_model() -> BERTopic:
    model_path = MODEL_DIR / "bertopic.pkl"
    if not model_path.exists():
        raise FileNotFoundError(f"Model tidak ditemukan: {model_path}")
    return joblib.load(model_path)

def predict_topics(texts: list[str], cluster_id: int = 0) -> list[dict]:
    model = load_model()
    topics, probs = model.transform(texts)
    return [
        {
            "text": text,
            "topic": int(topic),
            "probability": float(prob.max()) if hasattr(prob, "max") else float(prob)
        }
        for text, topic, prob in zip(texts, topics, probs)
    ]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-clusters", type=int, default=3)
    parser.add_argument("--data-path", type=str, default=str(DATA_PATH))
    args = parser.parse_args()

    results = run_modelling(
        n_clusters=args.n_clusters,
        data_path=Path(args.data_path)
    )
    print(f"Finished modelling with results: {results['num_articles']} articles, {results['n_clusters']} clusters, silhouette score: {results['silhouette_score']:.4f}")
    for cid, info in results["clusters"].items():
        print(f"Cluster {cid}: {info['num_topics']} topics, coherence score: {info['coherence_score']:.4f}")