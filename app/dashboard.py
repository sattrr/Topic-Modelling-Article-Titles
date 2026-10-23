import streamlit as st
import pandas as pd
import time
import sys
import os
import requests
import mlflow
from pathlib import Path
from mlflow.tracking import MlflowClient

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

API_BASE = os.getenv("API_BASE", "http://localhost:8000")
GRAFANA_URL = "http://localhost:3001"
DASHBOARD_ID = "adf8j6j"

# BASE_DIR = Path(__file__).resolve().parent.parent
# MODELLING_DIR = BASE_DIR / "src" / "modelling"
# SCRAPING_DIR = BASE_DIR / "src" / "scrapping"

st.set_page_config(
    page_title="Topic Modelling Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded", 
)

st.title("Topic Modelling Dashboard")

menu = st.sidebar.radio(
    "Menu",
    ["Scraping", "Modelling", "Analytics"]
)

def get_mlflow_experiments() -> pd.DataFrame:
    client = MlflowClient("http://localhost:5000")
    experiments = client.search_experiments()
    
    runs = []
    for exp in experiments:
        for run in client.search_runs(exp.experiment_id):
            runs.append({
                "run_id":         run.info.run_id[:8],
                "status":         run.info.status,
                "start_time":     pd.to_datetime(run.info.start_time, unit="ms"),
                "n_clusters":     run.data.params.get("n_clusters", "-"),
                "num_articles":   run.data.params.get("num_articles", "-"),
                "silhouette":     run.data.metrics.get("silhouette_score", 0),
                "coherence":      run.data.metrics.get("coherence_score", 0),
                "num_topics":     run.data.metrics.get("num_topics", 0),
            })
    return pd.DataFrame(runs)

if menu == "Scraping":
    st.header("Scraping Article Titles")
    st.write("Enter url link to scrape")

    url = st.text_input("URL", placeholder="https://journal.example.com/...")

    if st.button("Run Scraping", type="primary"):
        with st.spinner("Scraping in progress..."):
            try:
                links_resp = requests.post(
                    f"{API_BASE}/scraping/scrape-links",
                    json={"url": url},
                    timeout=120
                )
                links_resp.raise_for_status()
                links_data = links_resp.json()

                st.success(f"Found {links_data['total']} volume links.")
                titles_resp = requests.post(
                    f"{API_BASE}/scraping/scrape-titles",
                    json={"url": url},
                    timeout=600,
                    stream=True
                )
                titles_resp.raise_for_status()

                log_box = st.empty()
                log_lines = []
                for line in titles_resp.iter_lines():
                    if line:
                        log_lines.append(line.decode("utf-8") if isinstance(line, bytes) else line)
                        log_box.code("\n".join(log_lines[-20:]))

                st.success("Scraping completed")
                st.session_state["scraped_url"] = url

            except requests.exceptions.HTTPError as e:
                detail = e.response.json().get("detail", str(e) if e.response else str(e))
                st.error(f"API error: {detail}")
            except requests.exceptions.ConnectionError:
                st.error(f"Could not connect to API at {API_BASE}. Make sure the backend is running.")
            except requests.exceptions.Timeout:
                st.error("Request timed out. Scraping is taking too long.. check the backend logs.")
        
    if st.session_state.get("scraping_done"):
        st.info(f"Data ready from: {st.session_state.get('scraped_url')}")
        st.caption("Scraping done. Go to the Modelling menu to run topic modelling")

elif menu == "Modelling":
    st.header("Topic Modelling with BERTopic")

    def check_scraping_files() -> dict:
        try:
            resp = requests.get(f"{API_BASE}/scraping/scrape-status/", timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except:
            pass

        return {}

    try:
        files_resp = requests.get(f"{API_BASE}/modelling/data-status/", timeout=5)
        files_resp.raise_for_status()
        data_status = files_resp.json()
    except:
        data_status = {
            "scraped_arxiv": False,
            "scraped_ieee": False,
            "cleaned_combined": False,
        }

    st.subheader("Data Status")
    col1, col2, col3 = st.columns(3)
    with col1:
        if data_status.get("scraped_arxiv"):
            st.success("arXiv scraped")
        else:
            st.warning("arXiv not scraped")
    with col2:
        if data_status.get("scraped_ieee"):
            st.success("IEEE scraped")
        else:
            st.warning("IEEE not scraped")
    with col3:
        if data_status.get("cleaned_combined"):
            st.success("Combined data ready")
        else:
            st.info("Not preprocessed yet")

    st.divider()
    st.subheader("Upload Data (Optional)")
    st.caption("Upload json file if you don't want to scrape again.")

    col_up1, col_up2 = st.columns(2)

    with col_up1:
        uploaded_arxiv = st.file_uploader(
            "Upload arXiv JSON",
            type=["json"],
            key="upload_arxiv",
            help="File JSON hasil scraping arXiv"
        )
        if uploaded_arxiv:
            if st.button("Save arXiv File"):
                try:
                    resp = requests.post(
                        f"{API_BASE}/modelling/upload-data/",
                        files={"file": (uploaded_arxiv.name, uploaded_arxiv, "application/json")},
                        data={"source": "arxiv"},
                        timeout=60
                    )
                    resp.raise_for_status()
                    st.success(f"arXiv file uploaded: {resp.json().get('message')}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Upload failed: {e}")

    with col_up2:
        uploaded_ieee = st.file_uploader(
            "Upload IEEE JSON",
            type=["json"],
            key="upload_ieee",
            help="File JSON hasil scraping IEEE"
        )
        if uploaded_ieee:
            if st.button("Save IEEE File"):
                try:
                    resp = requests.post(
                        f"{API_BASE}/modelling/upload-data/",
                        files={"file": (uploaded_ieee.name, uploaded_ieee, "application/json")},
                        data={"source": "ieee"},
                        timeout=60
                    )
                    resp.raise_for_status()
                    st.success(f"IEEE file uploaded: {resp.json().get('message')}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Upload failed: {e}")

    st.divider()
    st.subheader("Run Topic Modelling")

    has_data = (
        data_status.get("scraped_arxiv") or
        data_status.get("scraped_ieee") or
        uploaded_arxiv is not None or
        uploaded_ieee is not None
    )

    if not has_data:
        st.error(
            "No data available. "
            "Perform scraping in the **Scraping** menu first, "
            "or upload a JSON file above."
        )

    col1, col2 = st.columns(2)
    with col1:
        use_arxiv = st.checkbox("arXiv", value=data_status.get("scraped_arxiv", False))
    with col2:
        use_ieee = st.checkbox("IEEE", value=data_status.get("scraped_ieee", False))

    n_clusters = st.slider("Number of clusters", min_value=2, max_value=20, value=3)

    if st.button(
        "Run Modelling",
        type="primary",
        disabled=not has_data
    ):
        try:
            resp = requests.post(
                f"{API_BASE}/modelling/run-topic-modelling/",
                json={
                    "n_clusters": n_clusters,
                    "use_arxiv": use_arxiv,
                    "use_ieee": use_ieee
                },
                timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            st.session_state["modelling_job_id"] = data["job_id"]
            st.success(f"Job started: `{data['job_id']}`")
        except Exception as e:
            st.error(f"Error: {e}")

    if st.session_state.get("modelling_job_id"):
        job_id = st.session_state["modelling_job_id"]

        if st.button("Refresh Status"):
            try:
                resp = requests.get(
                    f"{API_BASE}/modelling/run-topic-modelling/status/{job_id}",
                    timeout=10
                )
                job = resp.json()

                steps = {"preprocessing": 1, "modelling": 2, "done": 2}
                current = steps.get(job.get("step", ""), 0)
                st.progress(current / 2, text=f"Step {current}/2")

                if job["status"] == "done":
                    st.success(f"{job['message']}")
                    st.session_state["modelling_result"] = job["result"]
                    st.session_state["scraping_done"] = True
                elif job["status"] == "failed":
                    st.error(f"{job['message']}")
                else:
                    st.info(f"{job['message']}")

            except Exception as e:
                st.error(f"Error: {e}")

    if st.session_state.get("modelling_result"):
        result = st.session_state["modelling_result"]

        tab1, tab2 = st.tabs(["Visualisation", "Topic Table"])

        with tab1:
            st.subheader("Cluster Visualization")
            viz_path = Path("data/cleaned/topic-modelling/clustering_visualization.png")
            if viz_path.exists():
                st.image(str(viz_path))
            else:
                st.info("Cluster visualization not available.")

            st.subheader("Topic Bar Chart")
            bar_path = Path("data/cleaned/topic-modelling/topics_barchart.html")
            if bar_path.exists():
                with open(bar_path, "r", encoding="utf-8") as f:
                    st.components.v1.html(f.read(), height=500, scrolling=True)
            else:
                st.info("Topic bar chart not available.")

            st.subheader("Topic Map")
            map_path = Path("data/cleaned/topic-modelling/topics_map.html")
            if map_path.exists():
                with open(map_path, "r", encoding="utf-8") as f:
                    st.components.v1.html(f.read(), height=500, scrolling=True)
            else:
                st.info("Topic map not available.")

        with tab2:
            st.subheader("Topic Info")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Articles", result.get("num_articles", 0))
            with col2:
                st.metric("Topics Found", result.get("num_topics", 0))
            with col3:
                st.metric("Coherence Score", f"{result.get('coherence_score', 0):.4f}")

            st.divider()

            top_topics = result.get("top_topics", [])
            if top_topics:
                df_topics = pd.DataFrame(top_topics)
                st.dataframe(df_topics, use_container_width=True)

                st.download_button(
                    "Download Topic Info CSV",
                    df_topics.to_csv(index=False).encode("utf-8"),
                    "topic_info.csv",
                    "text/csv"
                )
            else:
                st.info("No topic info available.")

            st.divider()
            st.subheader("KMeans Cluster Breakdown")
            clusters = result.get("clusters", {})
            if clusters:
                df_clusters = pd.DataFrame([
                    {"cluster_id": k, "num_articles": v.get("num_articles", 0)}
                    for k, v in clusters.items()
                ])
                st.dataframe(df_clusters, use_container_width=True)

elif menu == "Analytics":
    st.header("Analytics")
    tab1, tab2 = st.tabs(["MLflow", "Grafana"])

    with tab1:
        st.subheader("Experiment History")
        try:
            df_runs = get_mlflow_experiments()
            if df_runs.empty:
                st.info("No experiments found in MLflow. Run topic modelling first.")
            else:
                st.dataframe(df_runs, use_container_width=True)
                if "silhouette" in df_runs.columns and "coherence" in df_runs.columns:
                    st.line_chart(
                        df_runs.set_index("start_time")[["silhouette", "coherence"]]
                    )

                finished_runs = df_runs[df_runs["status"] == "FINISHED"]

                if not finished_runs.empty:
                    best = finished_runs.loc[finished_runs["silhouette"].idxmax()]
                    
                    try:
                        sil_val = float(best['silhouette'])
                        coh_val = float(best['coherence'])
                    except (ValueError, TypeError):
                        sil_val, coh_val = 0.0, 0.0

                    st.success(
                        f"Best run: `{best['run_id']}` — "
                        f"silhouette: {sil_val:.4f}, "
                        f"coherence: {coh_val:.4f}, "
                        f"topics: {best['num_topics']}"
                    )
                else:
                    st.warning("No finished runs found in MLflow. Run topic modelling first.")
                    
        except Exception as e:
            st.error(f"Can't access MLflow: {e}")
            st.caption("Make sure the MLflow server is running: `mlflow ui --port 5000`")

    with tab2:
        st.subheader("System Metrics")

        def get_metric(query: str) -> str:
            try:
                resp = requests.get(
                    "http://localhost:9090/api/v1/query",
                    params={"query": query},
                    timeout=5
                )
                data = resp.json()

                if data.get("status") != "success":
                    return "N/A"

                result = data.get("data", {}).get("result", [])
                
                if not result:
                    return "N/A"
                    
                value = result[0].get("value", [])
                if len(value) < 2:
                    return "N/A"
                    
                return str(value[1])

            except Exception:
                return "N/A"

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Links Scraped", get_metric("scraped_links_total"))
        with col2:
            val = get_metric("silhouette_score")
            st.metric("Silhouette Score", f"{float(val):.4f}" if val != "N/A" else "N/A")
        with col3:
            val = get_metric("coherence_score")
            st.metric("Coherence Score", f"{float(val):.4f}" if val != "N/A" else "N/A")

        st.divider()

        st.subheader("Metrics History")
        try:
            import time

            end_time = int(time.time())
            start_time = end_time - 3600

            resp = requests.get(
                "http://localhost:9090/api/v1/query_range",
                params={
                    "query": "scraped_links_total",
                    "start": str(start_time),
                    "end": str(end_time),
                    "step": "60"
                },
                timeout=5
            )
            
            response_json = resp.json()
            
            if response_json.get("status") == "success":
                result_list = response_json.get("data", {}).get("result", [])
                 
                if result_list and "values" in result_list[0]:
                    values = result_list[0]["values"]
                    df_metrics = pd.DataFrame(values, columns=["timestamp", "value"])
                    df_metrics["timestamp"] = pd.to_datetime(df_metrics["timestamp"], unit="s")
                    df_metrics["value"] = df_metrics["value"].astype(float)
                    st.line_chart(df_metrics.set_index("timestamp")["value"])
                else:
                    st.info("No metrics data found in Prometheus. Make sure the FastAPI backend is running and scraping data.")
            else:
                error_reason = response_json.get("error", "Unknown error from Prometheus API")
                st.error(f"Prometheus API Error: {error_reason}")
                
        except Exception as e:
            st.warning(f"Can't fetch data from Prometheus: {e}")


        st.divider()

        st.subheader("Grafana Dashboard")
        st.components.v1.iframe(
            "http://192.168.1.240:3001/d/adf8j6j/topic-modelling-monitor"
            "?orgId=1&refresh=30s&kiosk",
            height=1000,
            scrolling=False
        )