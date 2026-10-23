import altair as alt
import streamlit as st
import pandas as pd
import json
import os
import ssl
import httpx
from pathlib import Path
from dotenv import load_dotenv
from supabase import Client, create_client
from supabase.lib.client_options import ClientOptions

BASE_DIR = Path(__file__).resolve().parent.parent
CLEAN_DATA_DIR = BASE_DIR / "data" / "cleaned"
JSON_PATH = CLEAN_DATA_DIR / "cleaned_articles_combined.json"

load_dotenv()

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    ssl.SSLContext.verify_mode = property(
        lambda self: ssl.CERT_NONE, lambda self, newval: None
    )

os.environ["SSL_CERT_FILE"] = ""
os.environ["CURL_CA_BUNDLE"] = ""
# os.environ["HTTPX_TIMEOUT"] = "60.0"

SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["key"]

st.set_page_config(
    page_title="Topic Modelling - Article Titles",
    page_icon="📊",
    layout="wide"
)
st.title("📊 Topic Modelling Article Titles")

@st.cache_resource
def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

@st.cache_data(ttl=3600)
def load_topics():
    supabase = get_supabase()
    resp = supabase.table("topics").select("*").order("num_docs", desc=True).execute()
    return pd.DataFrame(resp.data)

@st.cache_data(ttl=3600)
def load_latest_run():
    supabase = get_supabase()
    resp = (supabase.table("modelling_runs")
            .select("*")
            .order("created_at", desc=True)
            .limit(1)
            .execute())
    return resp.data[0] if resp.data else None

@st.cache_data(ttl=3600)
def get_total_articles_count():
    supabase = get_supabase()
    resp = (
        supabase.table("articles").select("*", count="exact", head=True).execute()
    )
    return resp.count if resp.count is not None else 0

@st.cache_data(ttl=3600)
def load_articles(topic_id=None, source=None, limit=100):
    supabase = get_supabase()
    query = supabase.table("articles").select("*")
    if topic_id is not None:
        query = query.eq("topic_id", topic_id)
    if source:
        query = query.eq("source", source)
    resp = query.limit(limit).execute()
    return pd.DataFrame(resp.data)

menu = st.sidebar.radio(
    "Menu",
    ["Overview", "Topics", "Articles"]
)

if menu == "Overview":
    run = load_latest_run()
    # st.write("Debug Latest Run Data:", run)
    total_articles = (
        get_total_articles_count()
    )

    num_topics = run.get("num_topics", 0) if run else 0
    silhouette_score = run.get("silhouette_score", 0.0) if run else 0.0
    coherence_score = run.get("coherence_score", 0.0) if run else 0.0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Articles", f"{total_articles:,}")
    with col2:
        st.metric("Topics Found", num_topics)
    with col3:
        st.metric("Silhouette Score", f"{silhouette_score:.4f}")
    with col4:
        st.metric("Coherence Score", f"{coherence_score:.4f}")
    
    st.subheader("Source Breakdown")

    if run:
        breakdown = run.get("source_breakdown", {})

        if isinstance(breakdown, str):
            try:
                breakdown = json.loads(breakdown)
            except Exception:
                breakdown = {}

        if breakdown and isinstance(breakdown, dict):
            df = pd.DataFrame(breakdown.items(), columns=["Category", "Articles"])
            chart = (
                alt.Chart(df)
                .mark_bar()
                .encode(
                    x=alt.X("Category", sort="-y"),
                    y="Articles",
                    color=alt.Color(
                        "Category",
                        legend=None,
                        scale=alt.Scale(
                            range=["red", "blue"]
                        ),
                    ),
                )
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("Source breakdown data is empty or invalid.")
    else:
        st.info("No data available yet.")

elif menu == "Topics":
    df_topics = load_topics()
    if not df_topics.empty:
        st.subheader(f"{len(df_topics)} Topics Found")

        st.bar_chart(df_topics.head(20).set_index("topic_id")["num_docs"])

        df_topics["keywords"] = df_topics["topic_words"].apply(
            lambda x: ", ".join(json.loads(x)) if x else ""
        )
        st.dataframe(
            df_topics[["topic_id", "keywords", "num_docs"]],
            use_container_width=True
        )
    else:
        st.info("No topics available.")

elif menu == "Articles":
    df_topics = load_topics()

    col1, col2 = st.columns(2)
    with col1:
        topic_options = ["All"] + [
            str(int(t)) for t in df_topics["topic_id"].dropna().tolist()
        ]
        selected_topic = st.selectbox("Select Topic", options=topic_options)
    with col2:
        selected_source = st.selectbox("Filter by Source", ["All", "arxiv", "ieee"])

    topic_id = None if selected_topic == "All" else int(selected_topic)
    source   = None if selected_source == "All" else selected_source

    df_articles = load_articles(topic_id, source)
    if not df_articles.empty:
        st.dataframe(
            df_articles[["title", "authors", "year", "source", "topic_id"]],
            use_container_width=True
        )
    else:
        st.info("No articles found.")