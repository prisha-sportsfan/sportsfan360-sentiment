import os
import json
from groq import Groq
from tavily import TavilyClient
from dotenv import load_dotenv

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# ── System prompts ─────────────────────────────────────────

FIFA_SYSTEM = """You are SportsFan360, the daily app for loyal fans of FIFA and football sport.
You are an expert sports sentiment analyst writing for Gen Z football fans globally.
Your tone is friendly, energetic and sports-friendly.
CRITICAL: Only use the real news articles provided to you. Never make up links or information."""

WT20W_SYSTEM = """You are SportsFan360, the daily app for loyal fans of cricket and women's sports.
You are an expert sports sentiment analyst writing for Gen Z cricket fans globally.
Your tone is friendly, energetic and sports-friendly.
CRITICAL: Only use the real news articles provided to you. Never make up links or information."""

# ── Task prompts ───────────────────────────────────────────

FIFA_TASK = """
<task>
Create a dashboard report of the following over the last 24 hours:
1. Link of the 3 most trending FIFA ads
2. Link of the 2 FIFA ads that misfired
3. 5 most trending statements made by major analysts, commentators, or football players
4. Top 5 global searches
5. Top 5 fan emotions
6. Top 5 footballer emotions across the countries participating in this FIFA world cup
7. Top 5 national emotions across the countries participating in this FIFA world cup
8. 3 most trending memes
9. Summarize the top 5 signals.
</task>
<context>Football. Soccer. FIFA World Cup 2026. Sentiment analysis of FIFA World Cup 2026.</context>
<audience>Football fans. India and global. Urban & semi-urban. Gen Z male. Gen Z female.</audience>
<persona>Football fan. Tone is friendly, energetic and sports friendly.</persona>
<constraints>Do not make up information that isn't on the internet. Do not repeat information from last report.</constraints>
"""

WT20W_TASK = """
<task>
Create a dashboard report of the following over the last 24 hours:
1. Link of the 3 most trending ICC Women's T20 World Cup 2026 ads
2. Link of the 2 ICC Women's T20 World Cup 2026 ads that misfired
3. 5 most trending statements made by major analysts, commentators, or women cricketers
4. Top 5 global searches
5. Top 5 fan emotions
6. Top 5 cricketer emotions across the countries participating in this Women's T20 World Cup
7. Top 5 national emotions across the countries participating in this Women's T20 World Cup
8. 3 most trending memes
9. Summarize the top 5 signals.
</task>
<context>Cricket. T20. ICC Women's T20 World Cup 2026. Sentiment analysis of Women's T20 WC 2026. Women's cricket. Female athletes.</context>
<audience>Cricket fans. India and global. Urban & semi-urban. Gen Z male. Gen Z female.</audience>
<persona>Cricket fan. Tone is friendly, energetic and sports friendly.</persona>
<constraints>Do not make up information that isn't on the internet. Do not repeat information from last report.</constraints>
"""

# ── Search queries per sport ───────────────────────────────

FIFA_SEARCHES = [
    "FIFA World Cup 2026 trending ads campaigns today",
    "FIFA World Cup 2026 fan reactions sentiment today",
    "FIFA World Cup 2026 player statements news today",
    "FIFA World Cup 2026 trending memes social media today",
    "FIFA World Cup 2026 trending searches fan emotions today"
]

WT20W_SEARCHES = [
    "ICC Women's T20 World Cup 2026 trending news today",
    "Women's T20 World Cup 2026 fan reactions sentiment today",
    "ICC Women's T20 World Cup 2026 player statements today",
    "Women's T20 World Cup 2026 trending memes social media today",
    "ICC Women's T20 World Cup 2026 fan emotions searches today"
]

# ── JSON structure ─────────────────────────────────────────

REPORT_STRUCTURE = """{
  "trending_ads": [
    {"rank": 1, "brand": "", "campaign_name": "", "link": "", "why_trending": "", "sentiment": "", "virality_score": ""}
  ],
  "misfired_ads": [
    {"rank": 1, "brand": "", "campaign_name": "", "link": "", "what_went_wrong": "", "fan_reaction": ""}
  ],
  "trending_statements": [
    {"rank": 1, "person": "", "role": "", "statement": "", "source": "", "why_trending": ""}
  ],
  "top_searches": [
    {"rank": 1, "search_term": "", "why_trending": ""}
  ],
  "fan_emotions": [
    {"rank": 1, "emotion": "", "score": "", "trend": "", "driven_by": ""}
  ],
  "player_emotions": [
    {"rank": 1, "emotion": "", "players": "", "trend": ""}
  ],
  "national_emotions": [
    {"rank": 1, "country": "", "dominant_emotion": "", "key_driver": "", "mood_score": ""}
  ],
  "trending_memes": [
    {"rank": 1, "title": "", "format": "", "why_trending": "", "virality_score": ""}
  ],
  "top_signals": [
    {"rank": 1, "signal_title": "", "summary": "", "sportsfan360_play": ""}
  ]
}"""


def search_real_news(sport: str) -> list:
    """Agent 1 — Tavily searches real internet"""
    searches = FIFA_SEARCHES if sport == "FIFA_WC_2026" else WT20W_SEARCHES
    print(f"🔍 Agent 1: Tavily searching real {sport} news...")
    all_results = []
    for query in searches:
        try:
            results = tavily_client.search(
                query=query,
                search_depth="advanced",
                max_results=5
            )
            for r in results.get("results", []):
                all_results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", "")[:500]
                })
        except Exception as e:
            print(f"⚠️ Search error: {e}")

    print(f"✅ Agent 1: Found {len(all_results)} real articles")
    return all_results


def run_sentiment_engine(sport: str = "FIFA_WC_2026") -> dict:
    """Full pipeline — Agent 1 searches, Agent 2 writes report"""
    print(f"\n🚀 Starting Sentiment Engine for {sport}...")

    # Agent 1: Get real news
    real_news = search_real_news(sport)
    if not real_news:
        print("❌ No real news found")
        return None

    # Format articles for Groq
    news_text = ""
    for i, article in enumerate(real_news[:20]):
        news_text += f"\n[{i+1}] {article['title']}\nURL: {article['url']}\nSummary: {article['content']}\n"

    # Pick system prompt and task
    system_prompt = FIFA_SYSTEM if sport == "FIFA_WC_2026" else WT20W_SYSTEM
    task_prompt = FIFA_TASK if sport == "FIFA_WC_2026" else WT20W_TASK

    print(f"🤖 Agent 2: Groq analyzing real {sport} news...")

    full_prompt = f"""Based ONLY on these real news articles from the last 24 hours:

REAL NEWS ARTICLES:
{news_text}

{task_prompt}

Return ONLY a valid JSON object with exactly this structure, no extra text:
{REPORT_STRUCTURE}

Rules:
- trending_ads: exactly 3 items
- misfired_ads: exactly 2 items
- trending_statements: exactly 5 items
- top_searches: exactly 5 items
- fan_emotions: exactly 5 items
- player_emotions: exactly 5 items
- national_emotions: exactly 5 items
- trending_memes: exactly 3 items
- top_signals: exactly 5 items
- ONLY use information from the articles above
- For links, only use URLs from the articles above
- If not enough data, say "Insufficient data for this period"
"""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_prompt}
            ],
            max_tokens=4000,
            temperature=0.1
        )

        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        report = json.loads(raw)
        print(f"✅ Agent 2: {sport} report generated from real data!")
        return report

    except json.JSONDecodeError as e:
        print(f"❌ JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


if __name__ == "__main__":
    # Test both
    fifa_report = run_sentiment_engine("FIFA_WC_2026")
    if fifa_report:
        print(json.dumps(fifa_report, indent=2))

    wt20w_report = run_sentiment_engine("WT20W_WC_2026")
    if wt20w_report:
        print(json.dumps(wt20w_report, indent=2))