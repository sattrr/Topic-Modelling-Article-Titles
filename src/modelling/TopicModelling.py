import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import time
import json
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.feature_extraction.text import TfidfVectorizer
from bertopic import BERTopic
from pathlib import Path
from bertopic.vectorizers import ClassTfidfTransformer
from sklearn.feature_extraction.text import CountVectorizer
from umap import UMAP
from sklearn.metrics.pairwise import cosine_similarity

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_DATA_DIR = BASE_DIR / "data" / "cleaned"
CLEANED_DATA_DIR = BASE_DIR / "data" / "cleaned"
DATA_PATH = RAW_DATA_DIR / "cleaned_articles.json"

CLUSTERED_DIR = RAW_DATA_DIR / "clustered"
CLUSTERED_DIR.mkdir(parents=True, exist_ok=True)

TOPICMODELLING_DIR = CLEANED_DATA_DIR / "topic-modelling"
TOPICMODELLING_DIR.mkdir(parents=True, exist_ok=True)

with open(DATA_PATH, encoding="utf-8") as f:
    articles = json.load(f)

df_titles = pd.DataFrame(articles)

df_titles.rename(columns={"Judul": "article"}, inplace=True)

vectorizer = TfidfVectorizer(max_features=500)
features_tfidf = vectorizer.fit_transform(df_titles['article'])

pca = PCA(n_components=2)
features_pca = pca.fit_transform(features_tfidf.toarray())

plt.figure(figsize=(10, 6))
sns.scatterplot(x=features_pca[:, 0], y=features_pca[:, 1], alpha=0.7)
plt.title('Visualisasi Data Judul Jurnal Setelah PCA')
plt.xlabel('PCA Komponen 1')
plt.ylabel('PCA Komponen 2')
plt.show()

n_clusters = 3 
kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
cluster_labels = kmeans.fit_predict(features_pca)
df_titles["cluster"] = cluster_labels

plt.figure(figsize=(10, 6))
sns.scatterplot(x=features_pca[:, 0], y=features_pca[:, 1], hue=cluster_labels, palette="tab10", alpha=0.7)
centroids = kmeans.cluster_centers_
plt.scatter(centroids[:, 0], centroids[:, 1], c='black', marker='X', s=300, label="Centroids")
plt.title("Visualisasi Cluster dengan KMeans")
plt.xlabel("PCA Component 1")
plt.ylabel("PCA Component 2")
plt.legend()
plt.show()

silhouette_avg = silhouette_score(features_pca, cluster_labels)
print(f"Silhouette Score: {silhouette_avg}")

for cluster in range(n_clusters):
    cluster_data = df_titles[df_titles["cluster"] == cluster].to_dict(orient="records")
    with open(CLUSTERED_DIR / f"cluster_{cluster}.json", "w", encoding="utf-8") as f:
        json.dump(cluster_data, f, indent=4, ensure_ascii=False)

topic_models = {}
topics_per_cluster = {}
topics_info = {}

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

def calculate_cosine_similarity_coherence(topic_terms, vectorizer):
    topic_vectors = vectorizer.fit_transform([' '.join(topic) for topic in topic_terms])
    similarity_matrix = cosine_similarity(topic_vectors)
    
    coherence_scores = []
    for i in range(len(topic_terms)):
        for j in range(i + 1, len(topic_terms)):
            coherence_scores.append(similarity_matrix[i, j])
    
    return np.mean(coherence_scores) 

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
    
    coherence_score = calculate_cosine_similarity_coherence(topic_words, vectorizer)
    return coherence_score

for cluster in range(n_clusters):
    print(f"\n**Analisis Topik untuk Cluster {cluster}**")
    cluster_data = df_titles[df_titles["cluster"] == cluster]["article"].tolist()
    
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
    print(f"Coherence Score for Cluster {cluster}: {coherence_score}")
    
    fig = topic_model.visualize_barchart(top_n_topics=3)
    fig.write_html(TOPICMODELLING_DIR / f"cluster_{cluster}_topics.html")
    print(f"Topic Visualization saved at: {TOPICMODELLING_DIR/ f'cluster_{cluster}_topics.html'}")

for cluster in range(n_clusters):
    if cluster in topic_models: 
        topic_model = topic_models[cluster]
        print(f"Saving Topic Visualization for Cluster {cluster} into HTML file...")
        fig = topic_model.visualize_barchart(top_n_topics=3)
        fig.write_html(TOPICMODELLING_DIR / f"cluster_{cluster}_topics.html")
        print(f" Saved at: {TOPICMODELLING_DIR/ f'cluster_{cluster}_topics.html'}")
    else:
        print(f"Model for cluster {cluster} not found.")