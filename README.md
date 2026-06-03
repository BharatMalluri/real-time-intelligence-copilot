# P2 — Real-Time Intelligence Copilot

> \*\*Real-time news intelligence platform\*\* with RAG, AI enrichment, and a chat interface.
> Kafka · dbt · ChromaDB · Ollama · FastAPI · Streamlit

!\[CI](https://github.com/BharatMalluri/p2-realtime-intelligence/actions/workflows/ci.yml/badge.svg)

\---

## Architecture

```

\## Architecture



!\[Architecture](docs/architecture.svg)



```



```
NewsAPI · Reddit · RSS (BBC/Reuters/DW) · Hacker News
        │
        ▼
┌───────────────────────────────────┐
│  Apache Kafka                     │  ← 4 topics: news-raw, reddit-raw, rss-raw, hn-raw
│  Producers → Topics → Consumer    │
└────────────────┬──────────────────┘
                 │
                 ▼
┌───────────────────────────────────┐
│  PostgreSQL (raw schema)          │  ← news\_articles, reddit\_posts, rss\_items, hn\_items
└────────────────┬──────────────────┘
                 │
                 ▼
┌───────────────────────────────────┐
│  AI Enrichment                    │
│  sentence-transformers → ChromaDB │  ← Vector embeddings
│  Ollama (Llama3) → Summaries      │  ← Summary, sentiment, topics, entities
└────────────────┬──────────────────┘
                 │
                 ▼
┌───────────────────────────────────┐
│  dbt: staging → marts             │  ← fct\_articles, agg\_hourly\_trends
└────────────────┬──────────────────┘
                 │
                 ▼
┌──────────────────────┐    ┌─────────────────────────────┐
│  FastAPI             │    │  Streamlit Copilot UI        │
│  /ask  (RAG)         │◄───│  Chat · Trends · Entities   │
│  /trends             │    │  Summaries · Citations      │
│  /entities /summary  │    └─────────────────────────────┘
└──────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│  Airflow DAGs                                   │
│  ingest\_all\_sources (every 2h)                  │
│  enrich\_and\_transform (every 4h)                │
└─────────────────────────────────────────────────┘
```

## Stack

|Layer|Tool|
|-|-|
|Streaming|Apache Kafka (Confluent)|
|Orchestration|Apache Airflow 2.9|
|Storage|PostgreSQL 15|
|Transformation|dbt-postgres 1.8|
|Embeddings|sentence-transformers (all-MiniLM-L6-v2)|
|Vector Store|ChromaDB 0.5|
|LLM|Groq (llama-3.1 (local, free)|
|RAG|LangChain + custom retrieval chain|
|API|FastAPI|
|Dashboard|Streamlit|
|Monitoring|Kafka UI · Airflow UI|

\---

## Quick Start

### Prerequisites

* Docker + Docker Compose
* Python 3.11+
* Groq (llama-3.1 installed locally

### 1\. Clone and configure

```bash
git clone https://github.com/BharatMalluri/p2-realtime-intelligence.git
cd p2-realtime-intelligence
cp .env.example .env
# Add your API keys to .env
```

### 2\. Get free API keys (5 minutes)

* **NewsAPI**: https://newsapi.org/register (free, 100 req/day)
* **Reddit**: https://www.reddit.com/prefs/apps → create app → script type

### 3\. Pull Ollama model

```bash
ollama pull llama3
```

### 4\. Start the stack

```bash
docker compose up -d
```

### 5\. Setup Kafka topics

```bash
pip install -r requirements.txt
python scripts/setup\_topics.py
```

### 6\. Run first ingestion

```bash
python kafka/producers/rss\_hn\_producer.py   # No API key needed
python kafka/consumers/postgres\_consumer.py
```

### 7\. Set up dbt

```bash
cd dbt
cp profiles.yml.example profiles.yml
dbt deps \&\& dbt run
```

### 8\. Run enrichment

```bash
python rag/enrich\_articles.py
```

### 9\. Open the dashboard

|Service|URL|
|-|-|
|Copilot UI|http://localhost:8501|
|API docs|http://localhost:8001/docs|
|Airflow|http://localhost:8080|
|Kafka UI|http://localhost:8090|

\---

## Data Sources

|Source|Topics|Requires API Key|
|-|-|-|
|NewsAPI|Global headlines|✅ Free tier|
|Reddit|r/worldnews, r/technology, r/europe|✅ Free|
|BBC RSS|World + Technology news|❌ No key needed|
|Reuters RSS|World news|❌ No key needed|
|DW RSS|European news|❌ No key needed|
|Hacker News|Tech + startup news|❌ No key needed|

\---

## Skills Demonstrated

* ✅ Real-time streaming with Kafka (producers, consumers, topics)
* ✅ RAG pipeline (embed → store → retrieve → generate)
* ✅ Local LLM inference (Groq (llama-3.1, zero cost)
* ✅ Vector search (ChromaDB)
* ✅ dbt modelling (staging → marts)
* ✅ FastAPI REST backend with Pydantic
* ✅ Streamlit chat UI with citations
* ✅ Airflow orchestration
* ✅ CI/CD with GitHub Actions

