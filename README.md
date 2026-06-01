# SportsFan360 — Sentiment Engine

AI-powered fan sentiment automation for FIFA World Cup 2026 (and WT20 WC coming soon).

---

## What It Does

Runs automatically on a configurable schedule, browses the real internet for the latest FIFA fan sentiment, and stores structured reports in Firebase Firestore — ready to feed into FanZone and AskAI.

**Flow:**
```
Scheduler (2x daily, configurable)
    ↓
Agent 1: Tavily — browses real internet for FIFA news
    ↓
Agent 2: Groq (llama-3.3-70b) — writes structured sentiment report
    ↓
Firebase Firestore — stores as /fifaSentiments/{timestamp}
    ↓
FanZone + AskAI read from Firebase
```

---

## Report Structure (9 Sections)

Each run generates a JSON report with:

1. **trending_ads** — Top 3 trending FIFA ads with links
2. **misfired_ads** — Top 2 FIFA ads that backfired
3. **trending_statements** — Top 5 quotes from analysts, players, commentators
4. **top_searches** — Top 5 global searches
5. **fan_emotions** — Top 5 fan emotions with scores
6. **footballer_emotions** — Top 5 footballer emotions across WC countries
7. **national_emotions** — Top 5 national emotions across participating countries
8. **trending_memes** — Top 3 trending memes
9. **top_signals** — Top 5 intelligence signals with SportsFan360 plays

Every report includes:
- `timestamp` — doc ID (e.g. `2026-06-01_14-32-02`) — never overwrites
- `disclaimer` — "Answers are AI-generated. SportsFan360 does not claim accuracy of this content."

---

## Files

| File | Purpose |
|---|---|
| `sentiment_engine.py` | Core logic — Tavily web search + Groq report generation |
| `firebase_store.py` | Saves reports to Firestore with timestamp |
| `scheduler.py` | Runs pipeline on configurable schedule |
| `main.py` | FastAPI wrapper — `/health`, `/run-now`, `/latest` |
| `requirements.txt` | Dependencies |
| `.env` | API keys (never commit — see below) |

---

## Setup

### 1. Install dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Create `.env` file
```
GROQ_API_KEY=your_groq_key
TAVILY_API_KEY=your_tavily_key
FIREBASE_PROJECT_ID=sportsfan360-new
FIREBASE_CLIENT_EMAIL=firebase-adminsdk-xxx@sportsfan360-new.iam.gserviceaccount.com
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
RUNS_PER_DAY=2
SPORT=FIFA_WC_2026
```

### 3. Run scheduler
```bash
python scheduler.py
```

### 4. Run as API server
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Health check |
| `/run-now` | POST | Trigger one run manually |
| `/latest` | GET | Get latest report from Firebase |

---

## Configuration

Change `RUNS_PER_DAY` in `.env` to run more or less frequently:

```
RUNS_PER_DAY=2    # runs every 12 hours
RUNS_PER_DAY=4    # runs every 6 hours
RUNS_PER_DAY=10   # runs every 2.4 hours
```

---

## Firebase Structure

```
fifaSentiments/
  {YYYY-MM-DD_HH-MM-SS}/
    timestamp: "2026-06-01_14-32-02"
    sport: "FIFA_WC_2026"
    generated_at: Timestamp
    disclaimer: "Answers are AI-generated..."
    report: { ...all 9 sections... }
```

---

## Prompt

**System:** You are SportsFan360, the daily app for loyal fans of FIFA and football sport.

**Task:** Creates a dashboard report covering last 24 hours — trending ads, misfired ads, analyst statements, global searches, fan emotions, footballer emotions, national emotions, trending memes, top signals.

**Context:** FIFA World Cup 2026 — sentiment analysis for football fans, India and global, Gen Z.

**Constraints:** No made-up information. No repeats from last report.

> **Note:** Currently configured for FIFA WC 2026. WT20 WC support coming — same engine, different prompt via `SPORT` env variable.

---

## Deployment

Deploy to Render or Railway — connect this GitHub repo, set env vars, set start command:

```
uvicorn main:app --host 0.0.0.0 --port $PORT
```

---

## Tech Stack

- **Groq** — LLM (llama-3.3-70b-versatile)
- **Tavily** — Real-time web search
- **Firebase Firestore** — Storage
- **FastAPI** — API wrapper
- **APScheduler** — Scheduling