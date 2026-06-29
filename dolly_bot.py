import os
import json
import time
from datetime import datetime, timezone, timedelta
from google import genai
from google.genai import types
from firebase_store import init_firebase

# ── Gemini Client ─────────────────────────────────────────────────────────────
# Uses GEMINI_API_KEY if available (AI Studio) to avoid authentication issues.
# Falls back to Vertex AI if key is not set.
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    client = genai.Client(api_key=api_key)
    print("🔑 Using Google AI Studio API Key for Gemini Client.")
else:
    client = genai.Client(
        vertexai=True,
        project=os.getenv("GCP_PROJECT_ID", "fleet-gift-498306-p7"),
        location=os.getenv("GCP_LOCATION", "us-central1")
    )
    print("☁️ Using Vertex AI for Gemini Client.")

IST = timezone(timedelta(hours=5, minutes=30))
COOLDOWN_MINUTES = 20  # Minimum gap between posts in the same room/feed (matches 25-min schedule)

# ── Phase Lock Helpers ────────────────────────────────────────────────────────

def get_phase_lock_key(sport: str, match_id: str, phase: str, room_id: str = None) -> str:
    room_suffix = f"_{room_id}" if room_id else "_global"
    return f"dolly_phase_lock_{sport}_{match_id}_{phase}{room_suffix}"

PRE_MATCH_MAX_POSTS = 2   # 2 rounds of pre-match questions (~50 mins build-up)
POST_MATCH_MAX_POSTS = 2  # 2 rounds of post-match questions (~50 mins wrap-up)

def has_phase_been_posted(db, sport: str, match_id: str, phase: str, room_id: str = None) -> bool:
    """
    Returns True if Dolly should be blocked from posting in this specific room.
    - IN-PLAY: Never blocked here — cooldown check handles spacing.
    - PRE-MATCH: Blocked after PRE_MATCH_MAX_POSTS rounds in this room.
    - POST-MATCH: Blocked after POST_MATCH_MAX_POSTS rounds in this room.
    """
    if phase == "IN-PLAY":
        return False  # Cooldown handles in-play spacing
    key = get_phase_lock_key(sport, match_id, phase, room_id)
    doc = db.collection("dollyPhaseLocks").document(key).get()
    if not doc.exists:
        return False
    data = doc.to_dict()
    posted_at = data.get("postedAt", 0)
    post_count = data.get("count", 1)
    # Lock expires after 24 hours regardless
    elapsed_hours = (time.time() * 1000 - posted_at) / (1000 * 3600)
    if elapsed_hours >= 24:
        return False
    max_posts = PRE_MATCH_MAX_POSTS if phase == "PRE-MATCH" else POST_MATCH_MAX_POSTS
    return post_count >= max_posts

def stamp_phase_lock(db, sport: str, match_id: str, phase: str, room_id: str = None):
    """Stamps/increments this phase's post count in Firestore for this specific room."""
    key = get_phase_lock_key(sport, match_id, phase, room_id)
    doc = db.collection("dollyPhaseLocks").document(key).get()
    existing_count = doc.to_dict().get("count", 0) if doc.exists else 0
    db.collection("dollyPhaseLocks").document(key).set({
        "sport": sport,
        "matchId": match_id,
        "phase": phase,
        "roomId": room_id or "global",
        "postedAt": int(time.time() * 1000),
        "count": existing_count + 1,
    })

def was_recently_posted(db, room_id=None, sport="cricket", cooldown_minutes=COOLDOWN_MINUTES) -> bool:
    """Returns True if Dolly posted in this feed/room within the cooldown window."""
    cutoff_ms = int((time.time() - cooldown_minutes * 60) * 1000)
    try:
        if room_id:
            msgs = db.collection("roarRooms").document(room_id).collection("messages") \
                .where("authorUid", "==", "dolly-dolphin-bot").stream()
            for msg in msgs:
                if msg.to_dict().get("createdAt", 0) > cutoff_ms:
                    return True
        else:
            posts = db.collection("roarPosts") \
                .where("authorUid", "==", "dolly-dolphin-bot") \
                .where("sport", "==", sport).stream()
            for post in posts:
                if post.to_dict().get("createdAt", 0) > cutoff_ms:
                    return True
    except Exception as e:
        print(f"⚠️ Cooldown check error: {e}")
    return False

def get_existing_questions(db, room_id=None, sport="cricket"):
    """Fetches last 30 question texts in this specific room or feed to prevent duplicate posts."""
    questions = []
    try:
        if room_id:
            room_ref = db.collection("roarRooms").document(room_id).collection("messages") \
                .where("authorUid", "==", "dolly-dolphin-bot").stream()
            room_posts = sorted([d for d in room_ref],
                                 key=lambda x: x.to_dict().get("createdAt", 0), reverse=True)
            for doc in room_posts[:30]:
                text = doc.to_dict().get("text")
                if text:
                    questions.append(text)
        else:
            global_ref = db.collection("roarPosts").where("authorUid", "==", "dolly-dolphin-bot") \
                .where("sport", "==", sport).stream()
            global_posts = sorted([d for d in global_ref],
                                   key=lambda x: x.to_dict().get("createdAt", 0), reverse=True)
            for doc in global_posts[:30]:
                text = doc.to_dict().get("text")
                if text:
                    questions.append(text)
    except Exception as e:
        print(f"⚠️ Error fetching existing questions: {e}")
    return list(set(questions))

# ── Dynamic Match Detection via Gemini ───────────────────────────────────────

def detect_current_match(sport: str) -> dict | None:
    """
    Uses Gemini + Google Search to dynamically find the current or next upcoming match.
    Returns a dict with match details, or None if no credible match found.
    """
    now_ist = datetime.now(IST).strftime("%A, %d %B %Y %I:%M %p IST")

    if sport == "cricket":
        search_query = f"""
        Search Google right now for: "cricket match today live OR upcoming {now_ist}".
        Find the most relevant cricket match currently live OR starting within the next 24 hours.
        Include both Men's and Women's international cricket (ICC events, bilateral series, etc.).
        
        If you find a credible match, return ONLY this JSON (no extra text):
        {{
          "found": true,
          "matchId": "short-unique-id-no-spaces",
          "teams": "Team A vs Team B",
          "tournament": "Tournament Name",
          "venue": "Venue, City",
          "matchDate": "YYYY-MM-DD",
          "phase": "PRE-MATCH or IN-PLAY or POST-MATCH",
          "liveScore": "Score if live, else null",
          "keyPlayers": "Comma-separated key player names",
          "format": "T20 or ODI or Test"
        }}
        
        If you cannot find a credible, confirmed cricket match today or tomorrow, return ONLY:
        {{"found": false}}
        
        STRICT RULES:
        - Only return a match if you found it in a real search result (cricket board, ESPN, Cricbuzz, BBC Sport, etc.)
        - Do NOT make up or guess any match, score, or player names.
        - Do NOT return a match that finished more than 6 hours ago.
        """
    else:  # football / FIFA
        search_query = f"""
        Search Google right now for: "FIFA World Cup 2026 match today live OR upcoming {now_ist}".
        Find the most relevant FIFA World Cup 2026 match currently live OR starting within the next 24 hours.
        
        If you find a credible match, return ONLY this JSON (no extra text):
        {{
          "found": true,
          "matchId": "short-unique-id-no-spaces",
          "teams": "Team A vs Team B",
          "tournament": "FIFA World Cup 2026",
          "venue": "Venue, City",
          "matchDate": "YYYY-MM-DD",
          "phase": "PRE-MATCH or IN-PLAY or POST-MATCH",
          "liveScore": "Score if live, else null",
          "keyPlayers": "Comma-separated key player names",
          "format": "90 mins"
        }}
        
        If you cannot find a credible, confirmed FIFA match today or tomorrow, return ONLY:
        {{"found": false}}
        
        STRICT RULES:
        - Only return a match if you found it in a real search result (FIFA.com, ESPN, BBC Sport, etc.)
        - Do NOT make up or guess any match, score, or player names.
        - Do NOT return a match that finished more than 6 hours ago.
        """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=search_query,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.1
            )
        )
        raw = response.text.strip()
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            print(f"⚠️ Gemini returned no JSON for match detection ({sport}).")
            return None
        data = json.loads(raw[start:end])
        if not data.get("found"):
            print(f"ℹ️ No active or upcoming {sport} match found by Gemini.")
            return None
        print(f"✅ Match detected: {data.get('teams')} — Phase: {data.get('phase')}")
        return data
    except Exception as e:
        print(f"❌ Match detection error ({sport}): {e}")
        return None

# ── Question Generator ────────────────────────────────────────────────────────

def generate_questions(match: dict, sport: str, existing_str: str) -> list:
    """
    Uses Gemini + Google Search to generate 2 unique, non-hallucinatory questions
    (1 prediction + 1 debate) based on the detected match and phase.
    """
    phase = match.get("phase", "PRE-MATCH")
    teams = match.get("teams", "Unknown Teams")
    tournament = match.get("tournament", "")
    venue = match.get("venue", "")
    live_score = match.get("liveScore") or "Not available"
    key_players = match.get("keyPlayers", "")
    format_ = match.get("format", "")

    if sport == "cricket":
        sport_label = "cricket"
        phase_instruction = {
            "PRE-MATCH": "Focus on pre-match build-up: toss predictions, key player battles, pitch conditions, and team strategy.",
            "IN-PLAY": f"The match is LIVE. Current score: {live_score}. Focus on what is happening RIGHT NOW in the match based on this live context.",
            "POST-MATCH": "The match has ended. Focus on match review: key performances, impact of the result, and what it means for the tournament."
        }.get(phase, "")
    else:
        sport_label = "football"
        phase_instruction = {
            "PRE-MATCH": "Focus on pre-match build-up: formation predictions, key player battles, and which team has the tactical advantage.",
            "IN-PLAY": f"The match is LIVE. Current score: {live_score}. Focus on what is happening RIGHT NOW based on this live context.",
            "POST-MATCH": "The match has ended. Focus on match review: goal scorers, key moments, and what this result means for the tournament."
        }.get(phase, "")

    prompt = f"""
    You are Dolly, a passionate and highly knowledgeable {sport_label} fan and analyst.
    
    MATCH DETAILS (verified from live Google Search):
    - Match: {teams}
    - Tournament: {tournament}
    - Venue: {venue}
    - Format: {format_}
    - Current Phase: {phase}
    - Live Score: {live_score}
    - Key Players: {key_players}
    
    PHASE INSTRUCTION: {phase_instruction}
    
    YOUR QUESTION STYLE:
    - Short and punchy. Maximum 2 sentences. 1 sentence is even better.
    - Confident, direct, slightly opinionated — like a knowledgeable fan asking a friend.
    - No jargon overload. Any casual fan should instantly understand.
    - Makes people want to pick a side or answer immediately.
    
    TWO TYPES OF QUESTIONS:
    1. PREDICTION — One specific, verifiable outcome. Answerable with a name, number, or yes/no.
       Good: "Will Smriti Mandhana be India's top scorer today?"
       Good: "Will this match see a penalty shootout?"
       Bad: "What do you think will happen?"
    
    2. DEBATE — Two genuinely opposing sides specific to this match and moment.
       Good: "India's spinners vs Australia's power hitters — who wins the key battle?"
       Good: "Mbappe or Vinicius Jr — who has the bigger game today?"
       Bad: "Who is the better team overall?"
    
    STRICT RULES TO PREVENT HALLUCINATION:
    - ONLY ask questions about things you found in the live search results above.
    - Do NOT invent stats, scores, or player names. Only use what is confirmed.
    - If you are not certain about something, do not include it in a question.
    - If the match details are insufficient to ask good questions, return an empty list [].
    - No Gen-Z slang, no emojis in the questions, no exclamation marks.
    - Options (sideA, sideB) must be 1 to 4 words only.
    
    Do NOT generate questions similar to any of these already posted:
    {existing_str if existing_str else "None"}
    
    Generate exactly 1 prediction and 1 debate.
    
    Return ONLY a valid JSON list of exactly 2 objects:
    [
      {{
        "type": "prediction",
        "text": "Short prediction question?",
        "sideA": "Yes",
        "sideB": "No"
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
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.3
            )
        )
        raw = response.text.strip()
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start == -1 or end == 0:
            print("⚠️ Gemini returned no JSON for question generation.")
            return []
        polls = json.loads(raw[start:end])
        print(f"📊 Gemini generated {len(polls)} questions for phase [{phase}].")
        return polls
    except Exception as e:
        print(f"❌ Question generation error: {e}")
        return []

# ── Post to Firestore ─────────────────────────────────────────────────────────

def publish_questions(db, polls: list, sport: str, room_id=None):
    """Writes generated questions to Firestore (room or global feed)."""
    for poll in polls:
        now_ms = int(time.time() * 1000)
        text = poll.get("text", "").strip()
        if not text:
            continue

        if room_id:
            msg_ref = db.collection("roarRooms").document(room_id).collection("messages").document()
            msg_ref.set({
                "msgId": msg_ref.id,
                "roomId": room_id,
                "authorUid": "dolly-dolphin-bot",
                "authorUsername": "Dolly",
                "authorBadge": "RISING_FAN",
                "type": poll.get("type", "prediction"),
                "text": text,
                "sideA": poll.get("sideA", "Yes"),
                "sideB": poll.get("sideB", "No"),
                "fireCount": 0,
                "noChanceCount": 0,
                "heartCount": 0,
                "replyCount": 0,
                "sport": sport,
                "createdAt": now_ms,
                "updatedAt": now_ms
            })
            print(f"🐬 Room [{room_id}]: [{poll.get('type')}] \"{text}\"")
        else:
            post_ref = db.collection("roarPosts").document()
            post_ref.set({
                "postId": post_ref.id,
                "authorUid": "dolly-dolphin-bot",
                "authorUsername": "Dolly",
                "authorBadge": "RISING_FAN",
                "type": poll.get("type", "prediction"),
                "sport": sport,
                "text": text,
                "sideA": poll.get("sideA", "Yes"),
                "sideB": poll.get("sideB", "No"),
                "agreeCount": 0,
                "disagreeCount": 0,
                "replyCount": 0,
                "likeCount": 0,
                "isLive": True,
                "status": "active",
                "audience": "Everyone",
                "createdAt": now_ms,
                "updatedAt": now_ms
            })
            print(f"🐬 Global [{sport}]: [{poll.get('type')}] \"{text}\"")

# ── Core Runner ───────────────────────────────────────────────────────────────

def run_dolly_for_sport(sport: str, room_id=None):
    """
    Full pipeline for one sport:
    1. Detect current match via Gemini + Google Search
    2. Check phase lock (no double-posting for same phase)
    3. Check cooldown (no posting if last post was < 15 mins ago)
    4. Generate questions
    5. Publish to Firestore
    6. Stamp the phase lock
    """
    db = init_firebase()
    target = f"Room [{room_id}]" if room_id else "Global Feed"
    print(f"\n🐬 Dolly running for sport={sport}, target={target}")

    # Step 1: Detect match
    match = detect_current_match(sport)
    if not match:
        print(f"⏭️ No match found for {sport}. Dolly will stay silent.")
        return

    match_id = match.get("matchId", "unknown")
    phase = match.get("phase", "PRE-MATCH")

    # Step 2: Phase lock check
    if has_phase_been_posted(db, sport, match_id, phase, room_id):
        print(f"🔒 Phase lock active: Already posted [{phase}] for match [{match_id}] in target [{target}]. Skipping.")
        return

    # Step 3: Cooldown check
    if was_recently_posted(db, room_id=room_id, sport=sport):
        print(f"⏳ Cooldown active: A post was made less than {COOLDOWN_MINUTES} mins ago in target [{target}]. Skipping.")
        return

    # Step 4: Generate questions
    existing = get_existing_questions(db, room_id=room_id, sport=sport)
    existing_str = "\n".join([f"- {q}" for q in existing]) if existing else "None"
    polls = generate_questions(match, sport, existing_str)

    if not polls:
        print(f"⚠️ No questions generated for {sport} [{phase}] in target [{target}]. Staying silent.")
        return

    # Step 5: Publish
    publish_questions(db, polls, sport, room_id=room_id)

    # Step 6: Stamp phase lock
    stamp_phase_lock(db, sport, match_id, phase, room_id)
    print(f"✅ Dolly done for sport={sport}, phase={phase}, target={target}")


# ── Automated Full Run ────────────────────────────────────────────────────────

def find_infinity_room_id(db) -> str | None:
    """
    Dynamically finds the SF360 Infinity Room by querying Firestore.
    Returns the room ID if found, else None.
    No hardcoding — works even if the room is renamed or recreated.
    """
    try:
        rooms = db.collection("roarRooms").stream()
        for room in rooms:
            data = room.to_dict()
            name = (data.get("name") or "").lower()
            if "infinity" in name:
                print(f"🌐 Infinity Room found: {room.id} ('{data.get('name')}')")
                return room.id
    except Exception as e:
        print(f"⚠️ Could not find Infinity Room: {e}")
    return None


def dolly_auto_run_all_rooms():
    """
    Master runner — runs automatically every 25 minutes via APScheduler on Render.

    Logic:
    - SF360 Infinity Room (common room): always gets BOTH cricket and football posts.
    - Cricket rooms: get cricket posts only (based on most upcoming cricket match).
    - Football rooms: get football posts only (based on most upcoming football match).
    - Global feed: gets both cricket and football posts.
    - No hardcoding of match details — Gemini + Google Search detects live/upcoming matches.
    - Anti-spam: 20-min cooldown between posts in any room.
    - Anti-hallucination: silent if no match found.
    - Pre-match: 2 rounds max. In-play: every 25 mins. Post-match: 2 rounds max.
    """
    db = init_firebase()
    posted_room_ids = set()  # Prevents double-posting to same room

    # ── Step 1: SF360 Infinity Room (common room — cricket + football) ────────
    print("\n🌐 ── Dolly: SF360 Infinity Room ──")
    infinity_room_id = find_infinity_room_id(db)
    if infinity_room_id:
        run_dolly_for_sport("cricket", room_id=infinity_room_id)
        run_dolly_for_sport("football", room_id=infinity_room_id)
        posted_room_ids.add(infinity_room_id)
    else:
        print("⚠️ Infinity Room not found. Skipping.")

    # ── Step 2: Global feed (cricket + football) ──────────────────────────────
    print("\n🌍 ── Dolly: Global Feed ──")
    run_dolly_for_sport("cricket", room_id=None)
    run_dolly_for_sport("football", room_id=None)

    # ── Step 3: All cricket rooms (cricket posts only) ────────────────────────
    print("\n🏏 ── Dolly: Cricket Rooms ──")
    cricket_rooms = db.collection("roarRooms").where("sport", "==", "cricket").stream()
    for room in cricket_rooms:
        if room.id not in posted_room_ids:
            run_dolly_for_sport("cricket", room_id=room.id)
            posted_room_ids.add(room.id)

    # ── Step 4: All football rooms (football posts only) ─────────────────────
    print("\n⚽ ── Dolly: Football Rooms ──")
    football_rooms = db.collection("roarRooms").where("sport", "==", "football").stream()
    for room in football_rooms:
        if room.id not in posted_room_ids:
            run_dolly_for_sport("football", room_id=room.id)
            posted_room_ids.add(room.id)

    print("\n🐬 Dolly full run complete.")


# ── Legacy alias for backward compatibility ───────────────────────────────────
def dolly_auto_run_all_cricket_rooms():
    dolly_auto_run_all_rooms()


if __name__ == "__main__":
    dolly_auto_run_all_rooms()
