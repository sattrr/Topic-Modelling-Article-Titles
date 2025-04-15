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
from bertopic import BERTopic
from umap import UMAP

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_DATA_DIR = BASE_DIR / "data" / "cleaned"
CLUSTERED_DIR = RAW_DATA_DIR / "clustered"
TOPICMODELLING_DIR = RAW_DATA_DIR / "topic-modelling"
DATA_PATH = RAW_DATA_DIR / "cleaned_articles.json"

CLUSTERED_DIR.mkdir(parents=True, exist_ok=True)
TOPICMODELLING_DIR.mkdir(parents=True, exist_ok=True)

def load_articles(path):
    with open(path, encoding="utf-8") as f:
        articles = json.load(f)
    df = pd.DataFrame(articles)
    df.rename(columns={"Judul": "article"}, inplace=True)
    return df

def vectorize_and_reduce(df):
    vectorizer = TfidfVectorizer(max_features=500)
    features_tfidf = vectorizer.fit_transform(df['article'])

    pca = PCA(n_components=2)
    features_pca = pca.fit_transform(features_tfidf.toarray())
    
    return features_tfidf, features_pca

def perform_clustering(features_pca, n_clusters):
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
    topic_vectors = vectorizer.fit_transform([' '.join(topic) for topic in topic_terms])
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

    vectorizer = CountVectorizer(stop_words='english')
    return calculate_cosine_similarity_coherence(topic_words, vectorizer)

def analyze_topics_per_cluster(df, n_clusters, save_dir):
    topic_models = {}
    for cluster in range(n_clusters):
        print(f"\nTopic Analyze for Cluster {cluster}")
        cluster_data = df[df["cluster"] == cluster]["article"].tolist()
        
        if len(cluster_data) < 2:
            print(f"Data too small for Cluster {cluster}.")
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
        
        fig = topic_model.visualize_barchart(top_n_topics=3)
        fig.write_html(save_dir / f"cluster_{cluster}_topics.html")
        print(f"Visualization saved at: {save_dir / f'cluster_{cluster}_topics.html'}")

    return topic_models

if __name__ == "__main__":
    df = load_articles(DATA_PATH)

    tfidf_matrix, features_pca = vectorize_and_reduce(df)

    n_clusters = 3
    cluster_labels, centroids, silhouette = perform_clustering(features_pca, n_clusters)
    df["cluster"] = cluster_labels

    print(f"\nSilhouette Score: {silhouette:.4f}")

    save_clustered_data(df, CLUSTERED_DIR)

    plt.figure(figsize=(10, 6))
    sns.scatterplot(x=features_pca[:, 0], y=features_pca[:, 1], hue=cluster_labels, palette="tab10", alpha=0.7)
    plt.scatter(centroids[:, 0], centroids[:, 1], c='black', marker='X', s=300, label="Centroids")
    plt.title("Visualisasi Cluster with KMeans")
    plt.xlabel("PCA Component 1")
    plt.ylabel("PCA Component 2")
    plt.legend()
    plt.show()

    topic_models = analyze_topics_per_cluster(df, n_clusters, TOPICMODELLING_DIR)