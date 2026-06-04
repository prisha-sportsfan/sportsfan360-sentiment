import os
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate({
            "type": "service_account",
            "project_id": os.getenv("FIREBASE_PROJECT_ID"),
            "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace("\\n", "\n"),
            "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
            "token_uri": "https://oauth2.googleapis.com/token"
        })
        firebase_admin.initialize_app(cred)
    return firestore.client()

def save_plain_text_report(report: dict, sport: str):
    filename = "latest_report_fifa.md" if sport == "FIFA_WC_2026" else "latest_report_wt20w.md"
    try:
        content = []
        content.append(f"# SportsFan360 Sentiment Report - {sport}")
        content.append(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        content.append("## 🔥 Top Trending Ads")
        for ad in report.get("trending_ads", []):
            content.append(f"- **{ad.get('brand')} - {ad.get('campaign_name')}** (Rank {ad.get('rank')})")
            content.append(f"  * Why Trending: {ad.get('why_trending')}")
            content.append(f"  * Link: {ad.get('link')}")
            content.append(f"  * Sentiment: {ad.get('sentiment')} | Virality: {ad.get('virality_score')}")
        content.append("")
        
        content.append("## ❌ Misfired Ads")
        for ad in report.get("misfired_ads", []):
            content.append(f"- **{ad.get('brand')} - {ad.get('campaign_name')}** (Rank {ad.get('rank')})")
            content.append(f"  * What Went Wrong: {ad.get('what_went_wrong')}")
            content.append(f"  * Fan Reaction: {ad.get('fan_reaction')}")
            content.append(f"  * Link: {ad.get('link')}")
        content.append("")
        
        content.append("## 🗣️ Top Trending Statements")
        for stmt in report.get("trending_statements", []):
            content.append(f"- **{stmt.get('person')} ({stmt.get('role')})** (Rank {stmt.get('rank')})")
            content.append(f"  * Statement: \"{stmt.get('statement')}\"")
            content.append(f"  * Source: {stmt.get('source')} | Why Trending: {stmt.get('why_trending')}")
        content.append("")
        
        content.append("## 📊 Top Global Searches")
        for search in report.get("top_searches", []):
            content.append(f"- **{search.get('search_term')}** (Rank {search.get('rank')}): {search.get('why_trending')}")
        content.append("")
        
        content.append("## ❤️ Top Fan Emotions")
        for emotion in report.get("fan_emotions", []):
            content.append(f"- **{emotion.get('emotion')}** (Score: {emotion.get('score')} | Trend: {emotion.get('trend')}): {emotion.get('driven_by')}")
        content.append("")

        content.append("## 🏃‍♂️ Top Player Emotions")
        player_key = "footballer_emotions" if "footballer_emotions" in report else "player_emotions"
        for p_emotion in report.get(player_key, []):
            content.append(f"- **{p_emotion.get('emotion')}** (Rank {p_emotion.get('rank')} | Trend: {p_emotion.get('trend')}): {p_emotion.get('players')}")
        content.append("")

        content.append("## 🌍 Top National Emotions")
        for nat in report.get("national_emotions", []):
            content.append(f"- **{nat.get('country')}** ({nat.get('dominant_emotion')} | Mood: {nat.get('mood_score')}): {nat.get('key_driver')}")
        content.append("")

        content.append("## 🎭 Trending Memes")
        for meme in report.get("trending_memes", []):
            content.append(f"- **{meme.get('title')}** (Rank {meme.get('rank')} | Format: {meme.get('format')}): {meme.get('why_trending')} (Virality: {meme.get('virality_score')})")
        content.append("")

        content.append("## 🧠 Top Intelligence Signals")
        for sig in report.get("top_signals", []):
            content.append(f"- **{sig.get('signal_title')}** (Rank {sig.get('rank')})")
            content.append(f"  * Summary: {sig.get('summary')}")
            content.append(f"  * SportsFan360 Play: {sig.get('sportsfan360_play')}")
        content.append("")

        with open(filename, "w") as f:
            f.write("\n".join(content))
        print(f"📝 Plain English report generated: {filename}")
    except Exception as e:
        print(f"⚠️ Error generating plain English report: {e}")

def save_report(report: dict, sport: str = "FIFA_WC_2026"):
    if not report:
        print("⚠️ Failed to save report to Firebase: Report is empty or None.")
        return None
    db = init_firebase()
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    doc_data = {
        "timestamp": timestamp,
        "sport": sport,
        "generated_at": firestore.SERVER_TIMESTAMP,
        "disclaimer": "Answers are AI-generated. SportsFan360 does not claim accuracy of this content.",
        "report": report
    }
    
    collection_name = "fifaSentiments" if sport == "FIFA_WC_2026" else "wt20wSentiments"
    db.collection(collection_name).document(timestamp).set(doc_data)
    print(f"✅ Report saved to Firebase: {collection_name}/{timestamp}")
    
    # Save the human-readable plain text file
    save_plain_text_report(report, sport)
    return timestamp

def get_latest_report(sport: str = "FIFA_WC_2026"):
    db = init_firebase()
    
    # Bug 2 fixed: use correct collection based on sport
    collection_name = "fifaSentiments" if sport == "FIFA_WC_2026" else "wt20wSentiments"
    docs = db.collection(collection_name)\
              .order_by("generated_at", direction=firestore.Query.DESCENDING)\
              .limit(1)\
              .stream()
    
    for doc in docs:
        return doc.to_dict()
    return None

if __name__ == "__main__":
    print("Testing Firebase connection...")
    db = init_firebase()
    print("✅ Firebase connected successfully!")