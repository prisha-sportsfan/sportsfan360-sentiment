import os
import json
from groq import Groq
from tavily import TavilyClient
from dotenv import load_dotenv

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

SYSTEM_PROMPT = """You are SportsFan360, the daily app for loyal fans of FIFA and football sport.
You are an expert sports sentiment analyst writing for Gen Z football fans globally.
Your tone is friendly, energetic and sports-friendly.
CRITICAL: Only use the real news articles provided to you. Never make up links or information."""

def search_real_news():
    print("🔍 Agent 1: Tavily searching real FIFA news...")
    searches = [
        "FIFA World Cup 2026 trending ads campaigns today",
        "FIFA World Cup 2026 fan reactions sentiment today",
        "FIFA World Cup 2026 player statements news today",
        "FIFA World Cup 2026 trending memes social media today",
        "FIFA World Cup 2026 trending searches fan emotions today"
    ]
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
            print(f"⚠️ Search error for '{query}': {e}")

    print(f"✅ Agent 1: Found {len(all_results)} real articles")
    return all_results

def run_sentiment_engine():
    print("🚀 Starting FIFA Sentiment Engine...")

    # Agent 1: Get real news
    real_news = search_real_news()

    if not real_news:
        print("❌ No real news found, aborting")
        return None

    # Format news for Groq
    news_text = ""
    for i, article in enumerate(real_news[:20]):
        news_text += f"\n[{i+1}] {article['title']}\nURL: {article['url']}\nSummary: {article['content']}\n"

    print("🤖 Agent 2: Groq analyzing real news...")

    prompt = f"""Based ONLY on these real news articles from the last 24 hours, create a FIFA World Cup 2026 sentiment dashboard report.

REAL NEWS ARTICLES:
{news_text}

Return ONLY a valid JSON object with exactly these keys, no extra text:

{{
  "trending_ads": [
    {{"rank": 1, "brand": "", "campaign_name": "", "link": "", "why_trending": "", "sentiment": "", "virality_score": ""}}
  ],
  "misfired_ads": [
    {{"rank": 1, "brand": "", "campaign_name": "", "link": "", "what_went_wrong": "", "fan_reaction": ""}}
  ],
  "trending_statements": [
    {{"rank": 1, "person": "", "role": "", "statement": "", "source": "", "why_trending": ""}}
  ],
  "top_searches": [
    {{"rank": 1, "search_term": "", "why_trending": ""}}
  ],
  "fan_emotions": [
    {{"rank": 1, "emotion": "", "score": "", "trend": "", "driven_by": ""}}
  ],
  "footballer_emotions": [
    {{"rank": 1, "emotion": "", "players": "", "trend": ""}}
  ],
  "national_emotions": [
    {{"rank": 1, "country": "", "dominant_emotion": "", "key_driver": "", "mood_score": ""}}
  ],
  "trending_memes": [
    {{"rank": 1, "title": "", "format": "", "why_trending": "", "virality_score": ""}}
  ],
  "top_signals": [
    {{"rank": 1, "signal_title": "", "summary": "", "sportsfan360_play": ""}}
  ]
}}

Rules:
- trending_ads: exactly 3 items
- misfired_ads: exactly 2 items
- trending_statements: exactly 5 items
- top_searches: exactly 5 items
- fan_emotions: exactly 5 items
- footballer_emotions: exactly 5 items
- national_emotions: exactly 5 items
- trending_memes: exactly 3 items
- top_signals: exactly 5 items
- ONLY use information from the articles above
- For links, only use URLs from the articles above
- If not enough data for a section, say "Insufficient data for this period" """

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
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
        print("✅ Agent 2: Report generated from real data!")
        return report

    except json.JSONDecodeError as e:
        print(f"❌ JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


if __name__ == "__main__":
    report = run_sentiment_engine()
    if report:
        print(json.dumps(report, indent=2))