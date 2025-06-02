from fastapi import APIRouter, HTTPException
import subprocess
import sys
import time
import json
from prometheus_client import Summary, Gauge
from pathlib import Path

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
input_path = BASE_DIR / "data" / "cleaned" / "cleaned_articles.json"
logs_dir = BASE_DIR / "logs"

MODELLING_DURATION = Summary("modelling_duration_seconds", "Durasi proses topic modelling")
COHERENCE_SCORE = Gauge("coherence_score", "Coherence Score")
SILHOUETTE_SCORE = Gauge("silhouette_score", "Silhouette Score")
TOTAL_TOPICS = Gauge("total_topics", "Total number of topics generated")
TOTAL_CLUSTERS = Gauge("total_clusters", "Total number of clusters")

@MODELLING_DURATION.time()
def run_topic_modelling(input_path: str):
    try:
        result = subprocess.run(
            [sys.executable, 'src/modelling/TopicModelling.py', str(input_path)], 
            check=True,
            capture_output=True,
            text=True,
            cwd=BASE_DIR
        )
        print(f"Topic modelling output: {result.stdout}")
        if result.stderr:
            print(f"Topic modelling stderr: {result.stderr}")
    except subprocess.CalledProcessError as e:
        print(f"Topic Modelling failed with return code {e.returncode}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        raise HTTPException(status_code=500, detail=f"Topic Modelling failed: {e.stderr}")

    # Update metrics from the generated files
    try:
        topic_info_file = logs_dir / "topic_info.json"
        if topic_info_file.exists():
            with open(topic_info_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Set overall coherence score (this is already calculated in TopicModelling.py)
                if 'coherence_score' in data:
                    COHERENCE_SCORE.set(data['coherence_score'])
                    print(f"Updated coherence score: {data['coherence_score']}")
                
                # Set silhouette score
                if 'silhouette_score' in data:
                    SILHOUETTE_SCORE.set(data['silhouette_score'])
                    print(f"Updated silhouette score: {data['silhouette_score']}")
                
                # Set number of clusters
                if 'n_clusters' in data:
                    TOTAL_CLUSTERS.set(data['n_clusters'])
                    print(f"Updated cluster count: {data['n_clusters']}")
                
                # Calculate total topics from cluster_info
                total_topics_count = 0
                if 'cluster_info' in data:
                    for cluster_id, cluster_info in data['cluster_info'].items():
                        if isinstance(cluster_info, dict) and 'topics_count' in cluster_info:
                            total_topics_count += cluster_info['topics_count']
                
                TOTAL_TOPICS.set(total_topics_count)
                print(f"Updated total topics count: {total_topics_count}")
                
                # Print cluster details for debugging
                if 'cluster_info' in data:
                    for cluster_id, cluster_info in data['cluster_info'].items():
                        print(f"Cluster {cluster_id}: {cluster_info['topics_count']} topics, coherence: {cluster_info['coherence_score']:.4f}")
        
        else:
            print(f"Topic info file not found: {topic_info_file}")
            # Set default values
            COHERENCE_SCORE.set(0.0)
            SILHOUETTE_SCORE.set(0.0)
            TOTAL_TOPICS.set(0)
            TOTAL_CLUSTERS.set(0)
        
    except Exception as e:
        print(f"Error updating metrics: {e}")
        import traceback
        traceback.print_exc()
        # Set default values on error
        COHERENCE_SCORE.set(0.0)
        SILHOUETTE_SCORE.set(0.0)
        TOTAL_TOPICS.set(0)
        TOTAL_CLUSTERS.set(0)

@router.post("/run-topic-modelling/")
async def run_topic_modelling_endpoint():
    if not input_path.exists():
        raise HTTPException(status_code=400, detail=f"Input path does not exist: {input_path}")

    run_topic_modelling(input_path)

    return {"status": "success", "message": "Topic Modelling completed successfully!"}