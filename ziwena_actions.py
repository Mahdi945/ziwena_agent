"""
Ziwena — Actions module (Phase 3: doing things, not just talking about them)

Two concrete actions:
  1. Calendar: read upcoming events from a local Google Calendar (read-only).
  2. Jobs: use Gemini + Google Search to find real Werkstudent postings and
     save a shortlist to disk, instead of just discussing them in chat.

Per Ziwena's BEHAVIOR RULE, nothing here sends/books/modifies anything
external — calendar access is read-only, and job "saving" only writes to a
local JSON file Mehdi controls. Anything that would take an external action
on Mehdi's behalf still needs his explicit go-ahead in chat first.
"""

import os
import json
from datetime import datetime, timedelta

JOBS_FILE = "ziwena_jobs.json"


# ---------- Calendar (Google Calendar, read-only) ----------
# Requires: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
# First run opens a browser once for OAuth consent; token is cached in
# ziwena_calendar_token.json next to this file so it won't ask again.

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
CALENDAR_TOKEN_FILE = "ziwena_calendar_token.json"
CALENDAR_CREDENTIALS_FILE = "credentials.json"  # downloaded from Google Cloud Console


def get_upcoming_events(days: int = 7):
    """
    Return a list of dicts: {summary, start, end} for events in the next N days.
    Returns None (with a printed reason) if calendar isn't set up yet.
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        print("[Calendar: missing packages. Run: pip install google-api-python-client "
              "google-auth-httplib2 google-auth-oauthlib]")
        return None

    if not os.path.isfile(CALENDAR_CREDENTIALS_FILE):
        print(f"[Calendar: no {CALENDAR_CREDENTIALS_FILE} found. Download OAuth "
              f"'Desktop app' credentials from Google Cloud Console and put them "
              f"next to this script to enable calendar access.]")
        return None

    creds = None
    if os.path.isfile(CALENDAR_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(CALENDAR_TOKEN_FILE, CALENDAR_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CALENDAR_CREDENTIALS_FILE, CALENDAR_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(CALENDAR_TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    try:
        service = build("calendar", "v3", credentials=creds)
        now = datetime.utcnow().isoformat() + "Z"
        end = (datetime.utcnow() + timedelta(days=days)).isoformat() + "Z"
        events_result = service.events().list(
            calendarId="primary", timeMin=now, timeMax=end,
            singleEvents=True, orderBy="startTime",
        ).execute()
        events = events_result.get("items", [])
    except Exception as e:
        print(f"[Calendar: error fetching events: {e}]")
        return None

    out = []
    for e in events:
        start = e["start"].get("dateTime", e["start"].get("date"))
        end_t = e["end"].get("dateTime", e["end"].get("date"))
        out.append({"summary": e.get("summary", "(no title)"), "start": start, "end": end_t})
    return out


def format_events(events) -> str:
    if events is None:
        return "[Couldn't access the calendar — see note above.]"
    if not events:
        return "No upcoming events found."
    lines = []
    for ev in events:
        lines.append(f"- {ev['summary']} ({ev['start']} → {ev['end']})")
    return "\n".join(lines)


# ---------- Jobs (search + shortlist, saved to disk) ----------

def _load_jobs():
    if not os.path.isfile(JOBS_FILE):
        return []
    try:
        with open(JOBS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_jobs(jobs):
    with open(JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)


def search_and_shortlist_jobs(chat, query: str) -> str:
    """
    Ask the (already search-enabled) Gemini chat to find real postings matching
    `query`, get back structured JSON, and persist new ones to JOBS_FILE.
    Returns a human-readable summary of what was found/saved.
    """
    prompt = (
        f"Search for current, real Werkstudent job postings matching: '{query}'. "
        "Use web search. Return ONLY a JSON array (no markdown fences, no prose) "
        "of up to 8 objects, each with exactly these keys: "
        '"title", "company", "location", "link", "source". '
        "Only include postings you actually found via search — never invent one. "
        "If you can't find real postings, return an empty array []."
    )
    try:
        response = chat.send_message(prompt)
        text = response.text.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        found = json.loads(text)
    except Exception as e:
        return f"[Job search failed: {e}]"

    if not isinstance(found, list) or not found:
        return "No matching postings found this time — try a broader query."

    existing = _load_jobs()
    existing_links = {j.get("link") for j in existing}

    new_jobs = []
    for job in found:
        if not isinstance(job, dict) or not job.get("link"):
            continue
        if job["link"] in existing_links:
            continue
        job["saved_at"] = datetime.now().isoformat()
        job["query"] = query
        job["status"] = "shortlisted"
        new_jobs.append(job)
        existing_links.add(job["link"])

    if new_jobs:
        existing.extend(new_jobs)
        _save_jobs(existing)

    lines = [f"Found {len(found)} posting(s), {len(new_jobs)} new — saved to {JOBS_FILE}:"]
    for job in new_jobs:
        lines.append(f"- {job.get('title')} @ {job.get('company')} ({job.get('location')}) — {job.get('link')}")
    if not new_jobs:
        lines.append("(all matches were already in your shortlist)")
    return "\n".join(lines)


def list_saved_jobs(status: str = None) -> str:
    jobs = _load_jobs()
    if status:
        jobs = [j for j in jobs if j.get("status") == status]
    if not jobs:
        return "No saved jobs yet. Use /jobs <search terms> to find and shortlist some."
    lines = []
    for j in jobs:
        lines.append(f"- [{j.get('status')}] {j.get('title')} @ {j.get('company')} — {j.get('link')}")
    return "\n".join(lines)
