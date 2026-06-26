import os
import threading
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from sentiment_engine import run_sentiment_engine
from firebase_store import save_report, get_latest_report, list_reports, get_report
from dolly_bot import dolly_auto_run_all_cricket_rooms

load_dotenv()

app = FastAPI(title="SportsFan360 Sentiment Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok", "service": "SportsFan360 Sentiment Engine"}

@app.post("/run-now")
def run_now(sport: str = "FIFA_WC_2026"):
    report = run_sentiment_engine(sport)
    if report:
        timestamp = save_report(report, sport)
        return {"status": "success", "saved_as": timestamp, "sport": sport}
    return {"status": "failed"}

@app.post("/run-dolly")
def run_dolly(background_tasks: BackgroundTasks):
    background_tasks.add_task(dolly_auto_run_all_cricket_rooms)
    return {"status": "triggered", "message": "Dolly match bot execution started in the background."}

@app.get("/latest")
def latest(sport: str = "FIFA_WC_2026"):
    report = get_latest_report(sport)
    if report:
        return report
    return {"status": "no reports yet"}

@app.get("/list-reports")
def api_list_reports(sport: str = "FIFA_WC_2026", limit: int = 50):
    return {"reports": list_reports(sport, limit)}

@app.get("/get-report")
def api_get_report(sport: str = "FIFA_WC_2026", timestamp: str = None):
    report = get_report(sport, timestamp)
    if report:
        return report
    return {"status": "error", "message": f"Report not found for timestamp: {timestamp}"}

def start_scheduler():
    runs_per_day = int(os.getenv("RUNS_PER_DAY", 2))
    interval_hours = 24 / runs_per_day
    scheduler = BlockingScheduler()
    
    def run_all_sports():
        print("⏰ Starting scheduled background run for all sports...")
        for sport in ["FIFA_WC_2026", "WT20W_WC_2026"]:
            try:
                report = run_sentiment_engine(sport)
                if report:
                    save_report(report, sport)
            except Exception as e:
                print(f"❌ Scheduled run error for {sport}: {e}")
                
    scheduler.add_job(
        run_all_sports,
        'interval',
        hours=interval_hours
    )
    scheduler.start()

# Start scheduler in background when server starts
thread = threading.Thread(target=start_scheduler, daemon=True)
thread.start()