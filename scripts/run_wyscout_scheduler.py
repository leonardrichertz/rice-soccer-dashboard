"""Local Python scheduler for the Wyscout incremental sync -- runs
run_incremental_sync() on a recurring interval.

This is the ONE throwaway piece of the whole pipeline: once AWS EventBridge
exists, this script goes away and EventBridge invokes
wyscout_incremental.run_incremental_sync() directly as a Lambda handler
instead. Nothing in wyscout_incremental.py or wyscout_backfill.py needs to
change for that migration -- both were written as plain functions with no
CLI-specific logic for exactly this reason.

Runs in the foreground; leave it running in a terminal (or wrap it in a
Windows Task Scheduler entry / service that keeps a process alive) for it
to actually fire on schedule.

Usage:
    python scripts/run_wyscout_scheduler.py [--interval-hours 6] [--run-once]
"""
import argparse
import time

import schedule

import wyscout_incremental


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval-hours", type=float, default=6,
                         help="How often to run the incremental sync, in hours (default: 6).")
    parser.add_argument("--run-once", action="store_true",
                         help="Run a single sync immediately and exit, instead of looping.")
    args = parser.parse_args()

    if args.run_once:
        wyscout_incremental.run_incremental_sync()
        return

    schedule.every(args.interval_hours).hours.do(wyscout_incremental.run_incremental_sync)
    print(f"Scheduler started -- syncing every {args.interval_hours} hour(s). Press Ctrl+C to stop.")

    # Run once immediately on startup rather than waiting a full interval
    # for the first sync.
    wyscout_incremental.run_incremental_sync()

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
