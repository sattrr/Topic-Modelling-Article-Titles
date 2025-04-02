import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import time
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.feature_extraction.text import TfidfVectorizer
from bertopic import BERTopic
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent 
DATA_DIR = BASE_DIR / "data" / "raw"
DATA_PATH = DATA_DIR / "JPTIIK_unlabeled.csv"
CLUSTERED_DIR = Path("../../data/raw/clustered")
CLUSTERED_DIR.mkdir(parents=True, exist_ok=True)

df_titles = pd.read_csv(DATA_PATH)
print(df_titles.head())

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
    df_titles[df_titles["cluster"] == cluster].to_csv(CLUSTERED_DIR / f"cluster_{cluster}.csv", index=False)

topic_models = {}
topics_per_cluster = {}

for cluster in range(n_clusters):
    print(f"\n🔍 **Analisis Topik untuk Cluster {cluster}**")
    cluster_data = df_titles[df_titles["cluster"] == cluster]["article"].tolist()
    
    topic_model = BERTopic()
    topics, probs = topic_model.fit_transform(cluster_data)
    
    topic_models[cluster] = topic_model
    topics_per_cluster[cluster] = topics
    
    print(topic_model.get_topic_info())

# Visualisasi Topik
for cluster in range(n_clusters):
    topic_model = topic_models[cluster]
    fig = topic_model.visualize_barchart(top_n_topics=3)
    print(f"Menampilkan Cluster {cluster}")
    fig.show()
    time.sleep(2)