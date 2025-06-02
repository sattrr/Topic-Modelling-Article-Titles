import mlflow
import mlflow.sklearn
from bertopic import BERTopic
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import json
import sys
from pathlib import Path
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from umap import UMAP

# Set up paths
if len(sys.argv) > 1:
    input_file = Path(sys.argv[1])
    BASE_DIR = input_file.parent.parent.parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    input_file = BASE_DIR / "data" / "cleaned" / "cleaned_articles.json"

RAW_DATA_DIR = BASE_DIR / "data" / "raw"
CLEAN_DATA_DIR = BASE_DIR / "data" / "cleaned"
CLUSTERED_DIR = CLEAN_DATA_DIR / "clustered"
TOPICMODELLING_DIR = CLEAN_DATA_DIR / "topic-modelling"
LOG_DIR = BASE_DIR / "logs"
DATA_PATH = input_file

# Create directories
CLUSTERED_DIR.mkdir(parents=True, exist_ok=True)
TOPICMODELLING_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

def load_articles(path):
    """Load articles from a JSON file and convert to DataFrame."""
    with open(path, encoding="utf-8") as f:
        articles = json.load(f)
    df = pd.DataFrame(articles)
    
    # Handle different column names
    if 'title' in df.columns:
        df.rename(columns={"title": "article"}, inplace=True)
    elif 'Judul' in df.columns:
        df.rename(columns={"Judul": "article"}, inplace=True)
    
    # Use abstract if available, otherwise use title
    if 'abstract' in df.columns:
        df['article'] = df['abstract'].fillna(df['article'])
    
    # Clean the data
    df = df[df['article'].notna()]
    df = df[df['article'].str.strip() != '']
    df = df[~df['article'].str.lower().str.contains('not found|tidak ditemukan')]
    
    print(f"Loaded {len(df)} articles for processing")
    return df

def vectorize_and_reduce(df):
    """Vectorize the articles and apply PCA for dimensionality reduction."""
    vectorizer = TfidfVectorizer(max_features=500, stop_words='english')
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
        print(f"Saved cluster {cluster} with {len(cluster_data)} articles")

def calculate_cosine_similarity_coherence(topic_terms, vectorizer):
    """Calculate cosine similarity coherence for topics."""
    documents = [' '.join(topic) for topic in topic_terms]
    if not any(doc.strip() for doc in documents):
        print("All documents are empty or contain only stopwords.")
        return 0.0

    try:
        topic_vectors = vectorizer.fit_transform(documents)
        similarity_matrix = cosine_similarity(topic_vectors)

        coherence_scores = []
        for i in range(len(topic_terms)):
            for j in range(i + 1, len(topic_terms)):
                coherence_scores.append(similarity_matrix[i, j])
        
        return np.mean(coherence_scores) if coherence_scores else 0.0
    except Exception as e:
        print(f"Error calculating coherence: {e}")
        return 0.0

def get_topic_coherence_from_bertopic(topic_model, cluster_data):
    """Get coherence score from BERTopic model."""
    try:
        topic_words = []
        valid_topic_ids = topic_model.get_topic_info()
        valid_topic_ids = valid_topic_ids[valid_topic_ids.Topic != -1]["Topic"].tolist()
        
        for topic_id in valid_topic_ids:
            terms = topic_model.get_topic(topic_id)
            if terms:  # Check if terms exist
                words = [word.replace(" ", "_") for word, _ in terms[:10]]  # Top 10 words
                if words:
                    topic_words.append(words)

        if not topic_words:
            print("No valid topics found. Coherence score set to 0.")
            return 0.0

        vectorizer = CountVectorizer(stop_words='english')
        return calculate_cosine_similarity_coherence(topic_words, vectorizer)
    except Exception as e:
        print(f"Error getting coherence from BERTopic: {e}")
        return 0.0

def analyze_topics_per_cluster(df, n_clusters, save_dir):
    """Analyze topics for each cluster and save visualizations."""
    topic_models = {}
    cluster_coherence_scores = {}
    
    for cluster in range(n_clusters):
        print(f"\nAnalyzing topics for Cluster {cluster}")
        cluster_data = df[df["cluster"] == cluster]["article"].tolist()
        
        if len(cluster_data) < 2:
            print(f"Data too small for Cluster {cluster}. Skipping.")
            cluster_coherence_scores[cluster] = 0.0
            continue
        
        try:
            # Adjust UMAP parameters based on cluster size
            n_neighbors = min(15, len(cluster_data) - 1)
            if n_neighbors < 2:
                n_neighbors = 2
                
            umap_model = UMAP(n_neighbors=n_neighbors, n_components=5, min_dist=0.1, metric='cosine', random_state=42)
            vectorizer_model = CountVectorizer(ngram_range=(1, 2), stop_words="english", max_features=100)
            
            topic_model = BERTopic(
                vectorizer_model=vectorizer_model,
                umap_model=umap_model,
                min_topic_size=2,
                verbose=True
            )
            
            topics, probs = topic_model.fit_transform(cluster_data)
            topic_models[cluster] = topic_model
            
            coherence_score = get_topic_coherence_from_bertopic(topic_model, cluster_data)
            cluster_coherence_scores[cluster] = coherence_score
            print(f"Coherence Score for Cluster {cluster}: {coherence_score:.4f}")
            
            # Save topic visualization
            try:
                fig = topic_model.visualize_barchart(top_n_topics=min(3, len(topic_model.get_topics())))
                fig.write_html(save_dir / f"cluster_{cluster}_topics.html")
                print(f"Visualization saved: cluster_{cluster}_topics.html")
            except Exception as e:
                print(f"Error saving visualization for cluster {cluster}: {e}")
                
        except Exception as e:
            print(f"Error processing cluster {cluster}: {e}")
            cluster_coherence_scores[cluster] = 0.0

    return topic_models, cluster_coherence_scores

if __name__ == "__main__":
    print(f"Starting topic modeling with input file: {DATA_PATH}")
    
    if not DATA_PATH.exists():
        print(f"Error: Input file does not exist: {DATA_PATH}")
        sys.exit(1)
    
    try:
        # Load data
        df = load_articles(DATA_PATH)
        
        if len(df) < 3:
            print("Not enough data for clustering. Need at least 3 articles.")
            sys.exit(1)

        # Vectorize and reduce dimensions
        tfidf_matrix, features_pca = vectorize_and_reduce(df)

        # Perform clustering
        n_clusters = min(3, len(df))  # Adjust based on data size
        cluster_labels, centroids, silhouette = perform_clustering(features_pca, n_clusters)
        df["cluster"] = cluster_labels

        print(f"\nSilhouette Score: {silhouette:.4f}")

        # Save clustered data
        save_clustered_data(df, CLUSTERED_DIR)

        # Create and save clustering visualization
        plt.figure(figsize=(10, 6))
        sns.scatterplot(x=features_pca[:, 0], y=features_pca[:, 1], hue=cluster_labels, palette="tab10", alpha=0.7)
        plt.scatter(centroids[:, 0], centroids[:, 1], c='black', marker='X', s=300, label="Centroids")
        plt.title("Cluster Visualization with KMeans")
        plt.xlabel("PCA Component 1")
        plt.ylabel("PCA Component 2")
        plt.legend()
        plt.savefig(TOPICMODELLING_DIR / "clustering_visualization.png", dpi=150, bbox_inches='tight')
        plt.close()
        print("Clustering visualization saved")

        # Analyze topics for each cluster
        topic_models, cluster_coherence_scores = analyze_topics_per_cluster(df, n_clusters, TOPICMODELLING_DIR)

        # Prepare results for saving
        results = {
            "silhouette_score": silhouette,
            "n_clusters": n_clusters,
            "total_articles": len(df),
            "cluster_info": {}
        }

        # Calculate overall coherence score
        coherence_scores = [score for score in cluster_coherence_scores.values() if score > 0]
        overall_coherence = np.mean(coherence_scores) if coherence_scores else 0.0
        results["coherence_score"] = overall_coherence

        # Add cluster-specific information
        for cluster_id in range(n_clusters):
            cluster_size = len(df[df["cluster"] == cluster_id])
            coherence = cluster_coherence_scores.get(cluster_id, 0.0)
            
            results["cluster_info"][cluster_id] = {
                "size": cluster_size,
                "coherence_score": coherence,
                "topics_count": len(topic_models[cluster_id].get_topics()) if cluster_id in topic_models else 0
            }

        # Save results
        json_output_path = LOG_DIR / "topic_info.json"
        with open(json_output_path, "w", encoding="utf-8") as json_file:
            json.dump(results, json_file, indent=4, ensure_ascii=False)

        print(f"\nResults saved to: {json_output_path}")
        print(f"Overall Coherence Score: {overall_coherence:.4f}")
        print(f"Silhouette Score: {silhouette:.4f}")
        print(f"Number of Clusters: {n_clusters}")
        print("Topic modeling completed successfully!")

    except Exception as e:
        print(f"Error during topic modeling: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)