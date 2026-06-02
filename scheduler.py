import os
import time
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from sentiment_engine import run_sentiment_engine
from firebase_store import save_report

load_dotenv()

RUNS_PER_DAY = int(os.getenv("RUNS_PER_DAY", 2))

SPORTS = [
    "FIFA_WC_2026",
    "WT20W_WC_2026"
]

def run_pipeline(sport: str):
    print(f"\n{'='*50}")
    print(f"🏃 Running sentiment pipeline — {sport}")
    print(f"{'='*50}")

    report = run_sentiment_engine(sport)

    if report:
        timestamp = save_report(report, sport)
        print(f"✅ Pipeline complete! Saved as: {timestamp}")
    else:
        print(f"❌ Pipeline failed for {sport}")

def run_all():
    for sport in SPORTS:
        run_pipeline(sport)

if __name__ == "__main__":
    interval_hours = 24 / RUNS_PER_DAY
    print(f"🕐 Scheduler starting — runs every {interval_hours}h ({RUNS_PER_DAY}x daily)")
    print(f"📋 Sports: {', '.join(SPORTS)}")

    # Run once immediately
    print("▶️ Running immediately on startup...")
    run_all()

    # Schedule
    scheduler = BlockingScheduler()
    scheduler.add_job(run_all, 'interval', hours=interval_hours)

    print(f"✅ Scheduler running — next run in {interval_hours} hours")
    print("Press Ctrl+C to stop")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\n⏹️ Scheduler stopped")