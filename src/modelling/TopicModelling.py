import mlflow
import mlflow.sklearn
from bertopic import BERTopic
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import json
from pathlib import Path
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from umap import UMAP

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_DATA_DIR = BASE_DIR / "data" / "raw"
CLEAN_DATA_DIR = BASE_DIR / "data" / "cleaned"
CLUSTERED_DIR = CLEAN_DATA_DIR / "clustered"
TOPICMODELLING_DIR = CLEAN_DATA_DIR / "topic-modelling"
<<<<<<< HEAD
LOG_DIR = BASE_DIR / "logs"
=======
>>>>>>> abiyyu-v-crawling
DATA_PATH = CLEAN_DATA_DIR / "cleaned_articles.json"

CLUSTERED_DIR.mkdir(parents=True, exist_ok=True)
TOPICMODELLING_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

def load_articles(path):
    """Load articles from a JSON file and convert to DataFrame."""
    with open(path, encoding="utf-8") as f:
        articles = json.load(f)
    df = pd.DataFrame(articles)
    df.rename(columns={"Judul": "article"}, inplace=True)
    return df

def vectorize_and_reduce(df):
    """Vectorize the articles and apply PCA for dimensionality reduction."""
    vectorizer = TfidfVectorizer(max_features=500)
    features_tfidf = vectorizer.fit_transform(df['article'])

    pca = PCA(n_components=2)
    features_pca = pca.fit_transform(features_tfidf.toarray())
    
    return features_tfidf, features_pca

def perform_clustering(features_pca, n_clusters):
    """Perform KMeans clustering on PCA-reduced features."""
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(features_pca)
    silhouette = silhouette_score(features_pca, labels)
    return labels, kmeans.cluster_centers_, silhouette

def save_clustered_data(df, clustered_dir):
    """Save each cluster's data to individual files."""
    for cluster in df["cluster"].unique():
        cluster_data = df[df["cluster"] == cluster].to_dict(orient="records")
        with open(clustered_dir / f"cluster_{cluster}.json", "w", encoding="utf-8") as f:
            json.dump(cluster_data, f, indent=4, ensure_ascii=False)

def calculate_cosine_similarity_coherence(topic_terms, vectorizer):
    """Calculate cosine similarity coherence for topics."""
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
    """Get coherence score from BERTopic model."""
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

def analyze_topics_per_cluster(df, n_clusters, save_dir):
    """Analyze topics for each cluster and save visualizations."""
    topic_models = {}
    for cluster in range(n_clusters):
        print(f"\nTopic Analyze for Cluster {cluster}")
        cluster_data = df[df["cluster"] == cluster]["article"].tolist()
        
        if len(cluster_data) < 2:
            print(f"Data too small for Cluster {cluster}. Skipping.")
            continue
        
        umap_model = UMAP(n_neighbors=19, n_components=5, min_dist=0.1, metric='cosine', random_state=42)
        vectorizer_model = CountVectorizer(ngram_range=(1, 2), stop_words="english")
        
        topic_model = BERTopic(
            vectorizer_model=vectorizer_model,
            umap_model=umap_model,
            min_topic_size=2,
            verbose=True
        )
        
        topics, probs = topic_model.fit_transform(cluster_data)
        topic_models[cluster] = topic_model
        
        coherence_score = get_topic_coherence_from_bertopic(topic_model, cluster_data)
        print(f"Coherence Score for Cluster {cluster}: {coherence_score:.4f}")
        
        mlflow.log_metric(f"coherence_score_cluster_{cluster}", coherence_score)
        
        fig = topic_model.visualize_barchart(top_n_topics=3)
        fig.write_html(save_dir / f"cluster_{cluster}_topics.html")
        print(f"Visualization saved at: {save_dir / f'cluster_{cluster}_topics.html'}")
        
        mlflow.log_artifact(save_dir / f"cluster_{cluster}_topics.html")

    return topic_models

if __name__ == "__main__":
<<<<<<< HEAD
    with mlflow.start_run():
        mlflow.log_param("n_clusters", 3)
        
        df = load_articles(DATA_PATH)

        tfidf_matrix, features_pca = vectorize_and_reduce(df)

        n_clusters = 3
        cluster_labels, centroids, silhouette = perform_clustering(features_pca, n_clusters)
        df["cluster"] = cluster_labels
=======
    df = load_articles(DATA_PATH)

    tfidf_matrix, features_pca = vectorize_and_reduce(df)

    n_clusters = 3
    cluster_labels, centroids, silhouette = perform_clustering(features_pca, n_clusters)
    df["cluster"] = cluster_labels
>>>>>>> abiyyu-v-crawling

        print(f"\nSilhouette Score: {silhouette:.4f}")
        mlflow.log_metric("silhouette_score", silhouette)

<<<<<<< HEAD
        save_clustered_data(df, CLUSTERED_DIR)

        plt.figure(figsize=(10, 6))
        sns.scatterplot(x=features_pca[:, 0], y=features_pca[:, 1], hue=cluster_labels, palette="tab10", alpha=0.7)
        plt.scatter(centroids[:, 0], centroids[:, 1], c='black', marker='X', s=300, label="Centroids")
        plt.title("Visualisasi Cluster with KMeans")
        plt.xlabel("PCA Component 1")
        plt.ylabel("PCA Component 2")
        plt.legend()
        plt.savefig(TOPICMODELLING_DIR / "clustering_visualization.png")
        plt.close()

        mlflow.log_artifact(TOPICMODELLING_DIR / "clustering_visualization.png")

        topic_models = analyze_topics_per_cluster(df, n_clusters, TOPICMODELLING_DIR)

        topic_hyperparams = {}
        for cluster_id, model in topic_models.items():
            coherence_score = get_topic_coherence_from_bertopic(model, df[df["cluster"] == cluster_id]["article"].tolist())
            num_topics = len(model.get_topics())

            mlflow.log_metric(f"num_topics_cluster_{cluster_id}", num_topics)
            mlflow.log_metric(f"coherence_score_cluster_{cluster_id}", coherence_score)
            mlflow.log_param(f"cluster_{cluster_id}_min_topic_size", model.min_topic_size)
            mlflow.log_param(f"cluster_{cluster_id}_vectorizer_model", str(model.vectorizer_model))
            mlflow.log_param(f"cluster_{cluster_id}_umap_n_neighbors", model.umap_model.n_neighbors)
            mlflow.log_param(f"cluster_{cluster_id}_umap_n_components", model.umap_model.n_components)
            mlflow.log_param(f"cluster_{cluster_id}_umap_min_dist", model.umap_model.min_dist)
            mlflow.log_param(f"cluster_{cluster_id}_umap_metric", model.umap_model.metric)

            topic_hyperparams[cluster_id] = {
                "min_topic_size": model.min_topic_size,
                "vectorizer_model": str(model.vectorizer_model),
                "umap_model": {
                    "n_neighbors": model.umap_model.n_neighbors,
                    "n_components": model.umap_model.n_components,
                    "min_dist": model.umap_model.min_dist,
                    "metric": model.umap_model.metric
                },
                "coherence_score": coherence_score
            }

        json_output_path = LOG_DIR / "topic_info.json"
        with open(json_output_path, "w", encoding="utf-8") as json_file:
            json.dump(topic_hyperparams, json_file, indent=4, ensure_ascii=False)

        mlflow.log_artifact(json_output_path)
        print(f"Hyperparameter dan coherence BERTopic berhasil disimpan ke: {json_output_path}")
=======
    save_clustered_data(df, CLUSTERED_DIR)

    plt.figure(figsize=(10, 6))
    sns.scatterplot(x=features_pca[:, 0], y=features_pca[:, 1], hue=cluster_labels, palette="tab10", alpha=0.7)
    plt.scatter(centroids[:, 0], centroids[:, 1], c='black', marker='X', s=300, label="Centroids")
    plt.title("Visualisasi Cluster with KMeans")
    plt.xlabel("PCA Component 1")
    plt.ylabel("PCA Component 2")
    plt.legend()
    plt.savefig(TOPICMODELLING_DIR / "clustering_visualization.png")
    plt.close()

    topic_models = analyze_topics_per_cluster(df, n_clusters, TOPICMODELLING_DIR)
>>>>>>> abiyyu-v-crawling
