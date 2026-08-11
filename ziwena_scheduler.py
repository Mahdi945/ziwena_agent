"""
Ziwena — Scheduler module (Phase 4: proactive, not just reactive)

Runs a lightweight background thread that fires a callback on a schedule
(default: once a day) so Ziwena can check in on Mehdi without him opening
the terminal and typing first. This process still has to be running for
triggers to fire (it's a local script, not a server) — but within one
running session, check-ins happen on their own.

Usage:
    from ziwena_scheduler import start_scheduler
    start_scheduler(on_checkin=my_callback, at_time="09:00")
"""

import threading
import time
from datetime import datetime

try:
    import schedule
except ImportError:
    schedule = None


def start_scheduler(on_checkin, at_time: str = "09:00", weekly_summary_day: str = "sunday",
                     on_weekly_summary=None):
    """
    Start a daemon thread that calls on_checkin() once a day at `at_time`
    (24h "HH:MM", local time), and optionally on_weekly_summary() once a
    week on weekly_summary_day.

    Returns the thread (already started), or None if the `schedule`
    package isn't installed.
    """
    if schedule is None:
        print("[Scheduler: 'schedule' package not installed — proactive "
              "check-ins disabled. Run: pip install schedule]")
        return None

    schedule.every().day.at(at_time).do(_safe_call, on_checkin)

    if on_weekly_summary is not None:
        getattr(schedule.every(), weekly_summary_day.lower()).at(at_time).do(
            _safe_call, on_weekly_summary
        )

    def _run():
        while True:
            schedule.run_pending()
            time.sleep(30)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    print(f"[Scheduler: daily check-in armed for {at_time}]")
    return thread


def _safe_call(fn):
    try:
        fn()
    except Exception as e:
        print(f"\n[Scheduled check-in failed: {e}]\n")
