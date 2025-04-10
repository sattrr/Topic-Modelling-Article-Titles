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

# Path setup
BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_DATA_DIR = BASE_DIR / "data" / "raw"
CLEANED_DATA_DIR = BASE_DIR / "data" / "cleaned"
DATA_PATH = RAW_DATA_DIR / "scraped_articles.json"

CLUSTERED_DIR = RAW_DATA_DIR / "clustered"
CLUSTERED_DIR.mkdir(parents=True, exist_ok=True)

TOPICMODELLING_DIR = CLEANED_DATA_DIR / "topic-modelling"
TOPICMODELLING_DIR.mkdir(parents=True, exist_ok=True)

# Load JSON data
with open(DATA_PATH, encoding="utf-8") as f:
    articles = json.load(f)

# Pastikan artikelnya dalam list of dicts
df_titles = pd.DataFrame(articles)

df_titles.rename(columns={"Judul": "article"}, inplace=True)

# --- Proses TF-IDF dan PCA ---
vectorizer = TfidfVectorizer(max_features=500)
features_tfidf = vectorizer.fit_transform(df_titles['article'])

pca = PCA(n_components=2)
features_pca = pca.fit_transform(features_tfidf.toarray())

# Visualisasi PCA
plt.figure(figsize=(10, 6))
sns.scatterplot(x=features_pca[:, 0], y=features_pca[:, 1], alpha=0.7)
plt.title('Visualisasi Data Judul Jurnal Setelah PCA')
plt.xlabel('PCA Komponen 1')
plt.ylabel('PCA Komponen 2')
plt.show()

# Clustering
n_clusters = 3 
kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
cluster_labels = kmeans.fit_predict(features_pca)
df_titles["cluster"] = cluster_labels

# Visualisasi Clustering
plt.figure(figsize=(10, 6))
sns.scatterplot(x=features_pca[:, 0], y=features_pca[:, 1], hue=cluster_labels, palette="tab10", alpha=0.7)
centroids = kmeans.cluster_centers_
plt.scatter(centroids[:, 0], centroids[:, 1], c='black', marker='X', s=300, label="Centroids")
plt.title("Visualisasi Cluster dengan KMeans")
plt.xlabel("PCA Component 1")
plt.ylabel("PCA Component 2")
plt.legend()
plt.show()

# Skor Silhouette
silhouette_avg = silhouette_score(features_pca, cluster_labels)
print(f"Silhouette Score: {silhouette_avg}")

# Simpan hasil clustering ke file JSON
for cluster in range(n_clusters):
    cluster_data = df_titles[df_titles["cluster"] == cluster].to_dict(orient="records")
    with open(CLUSTERED_DIR / f"cluster_{cluster}.json", "w", encoding="utf-8") as f:
        json.dump(cluster_data, f, indent=4, ensure_ascii=False)

# BERTopic untuk setiap cluster
topic_models = {}
topics_per_cluster = {}
topics_info = {}

for cluster in range(n_clusters):
    print(f"\n**Analisis Topik untuk Cluster {cluster}**")
    cluster_data = df_titles[df_titles["cluster"] == cluster]["article"].tolist()
    print(f"Jumlah artikel: {len(cluster_data)}")

    umap_model = UMAP(n_neighbors=15, n_components=5, min_dist=0.0, metric='cosine', random_state=42)
    vectorizer_model = CountVectorizer(ngram_range=(1, 2), stop_words="english")

    topic_model = BERTopic(
        vectorizer_model=vectorizer_model,
        umap_model=umap_model,
        min_topic_size=2,
        verbose=True
    )
    
    topics, probs = topic_model.fit_transform(cluster_data)
    
    topic_models[cluster] = topic_model
    topics_per_cluster[cluster] = topics
    topics_info[cluster] = topic_model.get_topic_info()

    # Cetak topik
    print(topics_info[cluster])

    # Simpan info topik ke file
    topic_info_path = CLUSTERED_DIR / f"cluster_{cluster}_topics.json"
    with open(topic_info_path, "w", encoding="utf-8") as f:
        json.dump(topics_info[cluster].to_dict(orient="records"), f, indent=4, ensure_ascii=False)

# Visualisasi Topik
for cluster in range(n_clusters):
    topic_model = topic_models[cluster]
    topics_info_df = topics_info[cluster]

    # Cek apakah ada topik selain -1
    valid_topics = topics_info_df[topics_info_df.Topic != -1]
    
    if valid_topics.shape[0] == 0:
        print(f"Tidak ada topik valid yang ditemukan untuk Cluster {cluster}, visualisasi dilewati.")
        continue

    print(f" Menyimpan visualisasi topik untuk Cluster {cluster} ke file HTML...")
    fig = topic_model.visualize_barchart(top_n_topics=3)
    
    # Simpan ke file HTML
    fig.write_html(TOPICMODELLING_DIR / f"cluster_{cluster}_topics.html")
    print(f" Disimpan di: {TOPICMODELLING_DIR/ f'cluster_{cluster}_topics.html'}")
