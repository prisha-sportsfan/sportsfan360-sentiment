import os
import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from sentiment_engine import run_sentiment_engine
from firebase_store import save_report, get_latest_report

from fastapi.responses import HTMLResponse

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
def run_now():
    report = run_sentiment_engine()
    if report:
        timestamp = save_report(report, os.getenv("SPORT", "FIFA_WC_2026"))
        return {"status": "success", "saved_as": timestamp}
    return {"status": "failed"}

@app.get("/latest")
def latest():
    report = get_latest_report()
    if report:
        return report
    return {"status": "no reports yet"}

@app.get("/report/{sport}", response_class=HTMLResponse)
def view_report(sport: str):
    filename = "latest_report_fifa.md" if sport.lower() == "fifa" else "latest_report_wt20w.md"
    if not os.path.exists(filename):
        return HTMLResponse("<h1>Report not found yet. Please run the pipeline first.</h1>", status_code=404)
    
    with open(filename, "r") as f:
        markdown_content = f.read()
        
    escaped_md = markdown_content.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SportsFan360 Sentiment Report - {sport.upper()}</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.2.0/github-markdown.min.css">
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <style>
            body {{
                box-sizing: border-box;
                min-width: 200px;
                max-width: 980px;
                margin: 0 auto;
                padding: 45px;
                background-color: #0d1117;
                color: #c9d1d9;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            }}
            @media (max-width: 767px) {{
                body {{
                    padding: 15px;
                }}
            }}
            .markdown-body {{
                background-color: #0d1117 !important;
                color: #c9d1d9 !important;
            }}
        </style>
    </head>
    <body class="markdown-body">
        <div id="content"></div>
        <script>
            document.getElementById('content').innerHTML = marked.parse(`{escaped_md}`);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

def start_scheduler():
    runs_per_day = int(os.getenv("RUNS_PER_DAY", 2))
    interval_hours = 24 / runs_per_day
    scheduler = BlockingScheduler()
    scheduler.add_job(
        lambda: save_report(run_sentiment_engine(), os.getenv("SPORT", "FIFA_WC_2026")),
        'interval',
        hours=interval_hours
    )
    scheduler.start()

# Start scheduler in background when server starts
thread = threading.Thread(target=start_scheduler, daemon=True)
thread.start()