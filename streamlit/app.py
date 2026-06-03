"""
app.py — Real-Time Intelligence Copilot UI
Chat interface + live trends + cited answers
"""
import os

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(
    page_title="Intelligence Copilot",
    page_icon="🧠",
    layout="wide",
)

API_URL = os.getenv("API_URL", "http://localhost:8001")

# ── Helpers ───────────────────────────────────────────────────────────────────
def api_get(path, params=None):
    try:
        r = requests.get(f"{API_URL}{path}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return None
def api_post(path, payload):
    try:
        r = requests.post(f"{API_URL}{path}", json=payload, timeout=60)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"answer": f"API error: {e}", "sources": [], "query": ""}

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🧠 Real-Time Intelligence Copilot")
st.caption("Powered by Kafka · dbt · RAG · ChromaDB · Ollama · FastAPI")

# ── Stats bar ─────────────────────────────────────────────────────────────────
stats = api_get("/stats")
if stats:
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("News Articles",  stats.get("news_articles", 0))
    col2.metric("Reddit Posts",   stats.get("reddit_posts", 0))
    col3.metric("RSS Items",      stats.get("rss_items", 0))
    col4.metric("HN Items",       stats.get("hn_items", 0))
    col5.metric("Embedded",       stats.get("embedded", 0))
    col6.metric("Summarized",     stats.get("summarized", 0))
else:
    st.warning("API not available — start the FastAPI service.")

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["💬 Ask", "📈 Trends", "🏷️ Entities", "📋 Summaries"])

# ── Tab 1: RAG Chat ───────────────────────────────────────────────────────────
with tab1:
    st.subheader("Ask a question about the news")
    st.caption("Powered by RAG — answers are grounded in real articles with citations")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                with st.expander(f"📎 {len(msg['sources'])} sources"):
                    for s in msg["sources"]:
                        st.markdown(f"- **[{s['source']}]** [{s['title']}]({s['url']})")

    question = st.chat_input("Ask anything about current news...")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Searching articles and generating answer..."):
                result = api_post("/ask", {"question": question, "n_results": 5})
            answer  = result.get("answer", "No answer returned.")
            sources = result.get("sources", [])
            st.markdown(answer)
            if sources:
                with st.expander(f"📎 {len(sources)} sources"):
                    for s in sources:
                        st.markdown(f"- **[{s['source']}]** [{s['title']}]({s.get('url','')})")

        st.session_state.messages.append({
            "role": "assistant",
            "content": answer,
            "sources": sources,
        })

# ── Tab 2: Trends ─────────────────────────────────────────────────────────────
with tab2:
    st.subheader("📈 Trending Topics")
    hours = st.slider("Time window (hours)", 1, 168, 24)
    trends = api_get("/trends", {"hours": hours})

    if trends:
        df = pd.DataFrame(trends)
        col_left, col_right = st.columns(2)

        with col_left:
            fig = px.bar(
                df.head(15), x="count", y="topic", orientation="h",
                color="sentiment",
                color_discrete_map={"positive": "#16a34a", "negative": "#dc2626", "neutral": "#6b7280"},
                title="Top 15 Topics by Frequency",
            )
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True)

        with col_right:
            sentiment_counts = df.groupby("sentiment")["count"].sum().reset_index()
            fig2 = px.pie(
                sentiment_counts, names="sentiment", values="count",
                color="sentiment",
                color_discrete_map={"positive": "#16a34a", "negative": "#dc2626", "neutral": "#6b7280"},
                title="Sentiment Distribution",
            )
            st.plotly_chart(fig2, use_container_width=True)

        st.dataframe(df, use_container_width=True)
    else:
        st.info("No trend data yet — run the enrichment pipeline first.")

# ── Tab 3: Entities ───────────────────────────────────────────────────────────
with tab3:
    st.subheader("🏷️ Top Entities Mentioned")
    hours_e = st.slider("Time window (hours)", 1, 168, 24, key="entities_hours")
    entities = api_get("/entities", {"hours": hours_e})

    if entities:
        df_e = pd.DataFrame(entities)
        fig3 = px.treemap(
            df_e.head(30), path=["entity"], values="count",
            title="Entity Frequency Treemap",
        )
        st.plotly_chart(fig3, use_container_width=True)
        st.dataframe(df_e, use_container_width=True)
    else:
        st.info("No entity data yet — run the enrichment pipeline first.")

# ── Tab 4: Summaries ──────────────────────────────────────────────────────────
with tab4:
    st.subheader("📋 Recent Article Summaries")
    source_filter = st.selectbox(
        "Filter by source", ["All", "newsapi", "reddit", "rss", "hackernews"]
    )
    summaries = api_get(
        "/summary",
        {"hours": 24, "source": None if source_filter == "All" else source_filter}
    )

    if summaries:
        for s in summaries[:20]:
            with st.expander(f"[{s['source']}] {s.get('summary', '')[:80]}..."):
                st.write(f"**Sentiment:** {s.get('sentiment', 'unknown')}")
                st.write(f"**Topics:** {', '.join(s.get('topics', []))}")
                st.write(f"**Summary:** {s.get('summary', '')}")
                st.write(f"**Time:** {s.get('summarized_at', '')}")
    else:
        st.info("No summaries yet — run the enrichment pipeline first.")
