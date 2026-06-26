import os
import json
import time
from datetime import datetime, timezone, timedelta
from google import genai
from google.genai import types
from firebase_store import init_firebase

client = genai.Client(
    vertexai=True,
    project=os.getenv("GCP_PROJECT_ID", "fleet-gift-498306-p7"),
    location=os.getenv("GCP_LOCATION", "us-central1")
)

def get_existing_questions(db, room_id=None):
    """
    Fetches text of questions already asked in the last 24 hours to prevent duplicates.
    """
    questions = []
    
    # 1. Fetch from global roarPosts
    global_ref = db.collection("roarPosts").where("sport", "==", "cricket").stream()
    global_posts = [d for d in global_ref]
    global_posts.sort(key=lambda x: x.to_dict().get("createdAt", 0), reverse=True)
    for doc in global_posts[:30]:
        data = doc.to_dict()
        if data.get("text"):
            questions.append(data.get("text"))
            
    # 2. Fetch from room messages if room_id is specified
    if room_id:
        room_ref = db.collection("roarRooms").document(room_id).collection("messages").stream()
        room_posts = [d for d in room_ref]
        room_posts.sort(key=lambda x: x.to_dict().get("createdAt", 0), reverse=True)
        for doc in room_posts[:30]:
            data = doc.to_dict()
            if data.get("text"):
                questions.append(data.get("text"))
                
    return list(set(questions))

def get_match_phase():
    """
    Determines the phase of the India vs Australia match (June 28, 2026) based on current local time.
    """
    # Current India Standard Time (IST)
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(ist_tz)
    
    match_date = datetime(2026, 6, 28, tzinfo=ist_tz)
    
    if now.date() < match_date.date():
        return "PRE-MATCH"
    elif now.date() == match_date.date():
        return "IN-PLAY"
    else:
        return "POST-MATCH"

def run_dolly_match_bot(room_id=None):
    """
    Dolly bot queries Gemini to generate highly specific predictions/debates.
    Saves to global roarPosts (if room_id is None) or roarRooms/{room_id}/messages (if room_id is provided).
    """
    print(f"🚀 Dolly Dolphin Bot active. (Target Room: {room_id if room_id else 'Global Feed'})")
    db = init_firebase()
    
    # Determine the match phase
    phase = get_match_phase()
    print(f"📅 Current Match Phase: {phase}")
    
    # Fetch existing questions to prevent duplicates
    existing_list = get_existing_questions(db, room_id)
    existing_str = "\n".join([f"- {q}" for q in existing_list]) if existing_list else "None"
    
    prompt = f"""
    You are Dolly, a passionate, highly knowledgeable cricket fan. You speak like a confident, direct, and slightly opinionated cricket analyst asking a friend.
    
    MATCH CONTEXT:
    - Match: Australia Women vs India Women
    - Series: ICC Women's T20 World Cup 2026, Group 1, Lord's Cricket Ground, London. Sunday 28 June 2026.
    - Stakes: Final group stage game. Both teams are fighting for semi-final qualification. Must-win.
    - Key Players (Australia): Georgia Voll, Beth Mooney (batting), Sophie Molineux, Kim Garth (bowling).
    - Key Players (India): Smriti Mandhana, Harmanpreet Kaur, Shafali Verma (batting), Shree Charani, Deepti Sharma (bowling).
    
    CURRENT PHASE: {phase}
    
    DIRECTIONS BASED ON MATCH PHASE:
    - If PRE-MATCH: Focus questions on pre-match build-up, NRR qualification scenarios, Lord's pitch expectations, or history.
    - If IN-PLAY: Search the live scores/match state and focus on the immediate match situation (in-play/outcome questions).
    - If POST-MATCH: Focus on review, key performers, and qualification impact.
    
    YOUR QUESTION STYLE:
    - Short and punchy. Maximum of two sentences per question. One sentence is even better.
    - Feels like a conversation, not a quiz. Write the way a knowledgeable cricket fan would ask a friend — confident, direct, a little opinionated.
    - Makes people want to answer. Every question should create a small moment of "ooh, good point" or "I have a strong take on this."
    - No jargon overload. Anyone who casually follows cricket should instantly understand what's being asked.
    - Read and understood in one pass.
    
    TWO TYPES OF QUESTIONS YOU GENERATE:
    1. Prediction - Ask users to forecast one specific, verifiable outcome from this match.
       * Rules: One outcome only. No compound questions. Must be answerable with a number, a name, or a yes/no after the match. Concrete and match-specific. No vague or opinion-based predictions.
       * Good: "Will Smriti Mandhana be India's top scorer today?"
       * Good: "Will Australia post a total above 160?"
       * Good: "Will Deepti Sharma take two or more wickets in this match?"
       * Bad: "What do you think will happen?"
       * Bad: "Will this be a great match?"
    2. Debate - Present a real point of tension and ask users to pick a side.
       * Rules: Two clearly opposing sides. Both must feel genuinely arguable. Specific to this match. Never ask who is "better overall" — keep it tied to today's game and stakes.
       * Good: "India's spinners vs Australia's power hitters — who wins the key battle at Lord's?"
       * Good: "Harmanpreet Kaur or Beth Mooney — who has the bigger match-defining innings today?"
       * Good: "Australia's tournament experience or India's bowling firepower — which is the bigger advantage in a must-win match?"
       * Bad: "Who is the better team in women's cricket?"
       * Bad: "Do you enjoy watching T20 cricket?"
       
    WHAT TO AVOID:
    - Slang, Gen Z phrases (e.g. do NOT use: 'cooked', 'clutch', 'brrr', 'baby', 'chef', 'snag', 'vibes', 'W', 'L', 'go brrr'), meme language, or overly casual tone.
    - Vague questions with no clear answer or stake.
    - Questions that require knowing obscure stats to engage with.
    - Anything longer than 2 sentences.
    - Verbose option text. Keep option sideA and sideB short, clear, and direct (max 1 to 4 words).
    - No exclamation marks.
    
    Do NOT generate questions that are redundant or similar to any of these already asked questions:
    {existing_str}
    
    Generate exactly 3 fresh, highly engaging predictions/debates.
    
    Return ONLY a valid JSON list of objects:
    [
      {{
        "type": "prediction",
        "text": "Short prediction question?",
        "sideA": "Option A",
        "sideB": "Option B"
      }},
      {{
        "type": "debate",
        "text": "Short debate question?",
        "sideA": "Option A",
        "sideB": "Option B"
      }}
    ]
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction="You are Dolly, a knowledgeable sports analyst. Keep your tone smart, passionate, and professional.",
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.3
            )
        )
        
        raw = response.text.strip()
        
        start_idx = raw.find('[')
        end_idx = raw.rfind(']')
        if start_idx != -1 and end_idx != -1:
            raw = raw[start_idx:end_idx + 1]
            
        polls = json.loads(raw)
        print(f"📊 Gemini generated {len(polls)} unique polls.")
        
        for poll in polls:
            now_ms = int(time.time() * 1000)
            
            if room_id:
                # Posting to a specific ROAR room
                msg_ref = db.collection("roarRooms").document(room_id).collection("messages").document()
                post_data = {
                    "msgId": msg_ref.id,
                    "roomId": room_id,
                    "authorUid": "dolly-dolphin-bot",
                    "authorUsername": "Dolly",
                    "authorBadge": "RISING_FAN",
                    "type": poll.get("type", "prediction"),
                    "text": poll.get("text"),
                    "sideA": poll.get("sideA", "Support"),
                    "sideB": poll.get("sideB", "Counter"),
                    "fireCount": 0,
                    "noChanceCount": 0,
                    "heartCount": 0,
                    "replyCount": 0,
                    "createdAt": now_ms,
                    "updatedAt": now_ms
                }
                msg_ref.set(post_data)
                print(f"🐬 Published to Room [{room_id}]: [{poll.get('type')}] \"{poll.get('text')}\"")
            else:
                # Posting to the Global Feed
                post_ref = db.collection("roarPosts").document()
                post_data = {
                    "postId": post_ref.id,
                    "authorUid": "dolly-dolphin-bot",
                    "authorUsername": "Dolly",
                    "authorBadge": "RISING_FAN",
                    "type": poll.get("type", "prediction"),
                    "sport": "cricket",
                    "text": poll.get("text"),
                    "sideA": poll.get("sideA", "Support"),
                    "sideB": poll.get("sideB", "Counter"),
                    "agreeCount": 0,
                    "disagreeCount": 0,
                    "replyCount": 0,
                    "likeCount": 0,
                    "isLive": True,
                    "status": "active",
                    "audience": "Everyone",
                    "createdAt": now_ms,
                    "updatedAt": now_ms
                }
                post_ref.set(post_data)
                print(f"🐬 Published to Global: [{poll.get('type')}] \"{poll.get('text')}\"")
                
        print("✅ Dolly successfully fired all polls!")
        
    except Exception as e:
        print(f"❌ Error in Dolly Bot execution: {e}")

def dolly_auto_run_all_cricket_rooms():
    """
    Finds all active cricket rooms in the database and runs the Dolly Bot inside them.
    Also runs on the global feed (SF360 Infinity Room).
    """
    db = init_firebase()
    
    # 1. Run on Global Feed (SF360 Infinity Room)
    print("📢 Running Dolly on Global Feed...")
    run_dolly_match_bot(room_id=None)
    
    # 2. Find all rooms with sport == 'cricket' (from roarRooms collection)
    print("🔍 Searching for active cricket rooms...")
    rooms_ref = db.collection("roarRooms").where("sport", "==", "cricket").stream()
    
    for room in rooms_ref:
        room_data = room.to_dict()
        room_id = room.id
        room_name = room_data.get("name", "Unknown Room")
        
        print(f"🏏 Running Dolly inside room: {room_name} ({room_id})")
        run_dolly_match_bot(room_id=room_id)

if __name__ == "__main__":
    # Post to the global feed and all active cricket rooms
    dolly_auto_run_all_cricket_rooms()
