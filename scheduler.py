import os
import time
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from sentiment_engine import run_sentiment_engine
from firebase_store import save_report

load_dotenv()

RUNS_PER_DAY = int(os.getenv("RUNS_PER_DAY", 2))
SPORT = os.getenv("SPORT", "FIFA_WC_2026")

def run_pipeline():
    print(f"\n{'='*50}")
    print(f"🏃 Running sentiment pipeline — {SPORT}")
    print(f"{'='*50}")
    
    report = run_sentiment_engine()
    
    if report:
        timestamp = save_report(report, SPORT)
        print(f"✅ Pipeline complete! Saved as: {timestamp}")
    else:
        print("❌ Pipeline failed — no report generated")

if __name__ == "__main__":
    # Calculate interval in hours
    interval_hours = 24 / RUNS_PER_DAY
    print(f"🕐 Scheduler starting — runs every {interval_hours}h ({RUNS_PER_DAY}x daily)")
    
    # Run once immediately on start
    print("▶️ Running immediately on startup...")
    run_pipeline()
    
    # Then schedule
    scheduler = BlockingScheduler()
    scheduler.add_job(run_pipeline, 'interval', hours=interval_hours)
    
    print(f"✅ Scheduler running — next run in {interval_hours} hours")
    print("Press Ctrl+C to stop")
    
    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\n⏹️ Scheduler stopped")