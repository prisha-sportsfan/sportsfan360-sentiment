import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(
    vertexai=True,
    project=os.getenv("GCP_PROJECT_ID", "fleet-gift-498306-p7"),
    location=os.getenv("GCP_LOCATION", "us-central1")
)

# ── FIFA prompt — EXACT AS GIVEN BY BOSS ──────────────────

FIFA_SYSTEM = """You are SportsFan360, the daily app for loyal fans of FIFA and football sport."""

FIFA_TASK = """Create a dashboard report of the following over the last 24 hours:
1. Link of the 3 most trending FIFA ads
2. Link of the 2 FIFA ads that misfired
3. 5 most trending statements made by major analysts, commentators, or football players
4. Top 5 global searches
5. Top 5 fan emotions
6. Top 5 footballer emotions across the countries participating in this FIFA world cup
7. Top 5 national emotions across the countries participating in this FIFA world cup
8. 3 most trending memes
9. Summarize the top 5 signals.

Context: Football. Soccer. FIFA World Cup 2026. We are doing a sentiment analysis of the FIFA World Cup 2026.
Audience: Football fans. India and global. Urban & semi-urban. Gen Z male. Gen Z female.
Persona: Football fan. Tone is friendly, energetic and sports friendly.
Constraints: Do not make up information that isn't on the internet. Do not repeat information from last report.

Return ONLY a valid JSON object with exactly this structure, no extra text:

{
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
  "footballer_emotions": [
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
}

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
- If real data not found for any item, say "Insufficient data for this period"
- Only use real URLs found via search — never make up links"""

# ── WT20W prompt ───────────────────────────────────────────

WT20W_SYSTEM = """You are SportsFan360, the daily app for loyal fans of cricket and women's sports."""

WT20W_TASK = """Create a dashboard report of the following over the last 24 hours:
1. Link of the 3 most trending ICC Women's T20 World Cup 2026 ads
2. Link of the 2 ICC Women's T20 World Cup 2026 ads that misfired
3. 5 most trending statements made by major analysts, commentators, or women cricketers
4. Top 5 global searches
5. Top 5 fan emotions
6. Top 5 cricketer emotions across the countries participating in this Women's T20 World Cup
7. Top 5 national emotions across the countries participating in this Women's T20 World Cup
8. 3 most trending memes
9. Summarize the top 5 signals.

Context: Cricket. T20. ICC Women's T20 World Cup 2026. Women's cricket. Female athletes.
Audience: Cricket fans. India and global. Urban & semi-urban. Gen Z male. Gen Z female.
Persona: Cricket fan. Tone is friendly, energetic and sports friendly.
Constraints: Do not make up information that isn't on the internet. Do not repeat information from last report. Women's cricket ONLY — no men's cricket players.

Return ONLY a valid JSON object with exactly this structure, no extra text:

{
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
}

Rules:
- trending_ads: exactly 3 items — REAL brand ads only, NOT cricket boards or websites
- misfired_ads: exactly 2 items — REAL brand ads that backfired, NOT player performances
- trending_statements: exactly 5 items — women cricketers ONLY
- player_emotions: exactly 5 items — WOMEN cricketers ONLY, no men's players
- If real data not found, say "Insufficient data for this period" — NEVER invent
- Only use real URLs — never make up links"""


def run_sentiment_engine(sport: str = "FIFA_WC_2026") -> dict:
    print(f"\n🚀 Starting Gemini Sentiment Engine for {sport}...")

    system_prompt = FIFA_SYSTEM if sport == "FIFA_WC_2026" else WT20W_SYSTEM
    task = FIFA_TASK if sport == "FIFA_WC_2026" else WT20W_TASK

    try:
        print(f"🔍 Gemini searching real internet for {sport}...")

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=task,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )

        raw = response.text.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        report = json.loads(raw)
        print(f"✅ Gemini: {sport} report generated from real internet data!")
        return report

    except json.JSONDecodeError as e:
        print(f"❌ JSON parse error: {e}")
        print(f"Raw response: {raw[:500]}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


if __name__ == "__main__":
    fifa = run_sentiment_engine("FIFA_WC_2026")
    if fifa:
        print(json.dumps(fifa, indent=2))

    wt20w = run_sentiment_engine("WT20W_WC_2026")
    if wt20w:
        print(json.dumps(wt20w, indent=2))