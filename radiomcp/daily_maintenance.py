#!/usr/bin/env python3
"""
Radio DB Daily Maintenance Script
Run as cron job: 0 4 * * * /path/to/daily_maintenance.py

Full DB health check on 2-week cycle
"""

import sys
import os

# Import server module from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server

def log(msg):
    from datetime import datetime
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def main():
    log("=== Radio DB Daily Maintenance ===")

    # 1. Check DB status
    stats = server.get_db_stats()
    log(f"Current DB: {stats.get('total', 0)}items (alive: {stats.get('alive', 0)}, dead: {stats.get('dead', 0)})")

    # 2. Sync new stations from major countries
    log("--- Sync new stations ---")
    countries = ["KR", "US", "JP", "GB", "DE", "FR"]
    total_new = 0

    for code in countries:
        result = server.sync_with_api(country_code=code, limit=50)
        new = result.get("new", 0)
        total_new += new
        if new > 0:
            log(f"  {code}: +{new}items")

    # 3. Sync popular genres
    tags = ["jazz", "classical", "pop", "rock", "electronic", "lounge"]
    for tag in tags:
        result = server.sync_with_api(tag=tag, limit=30)
        new = result.get("new", 0)
        total_new += new
        if new > 0:
            log(f"  {tag}: +{new}items")

    log(f"Total {total_new}new stations added")

    # 4. Health check (500 batch - load balanced)
    log("--- Health check (500) ---")
    health = server.health_check(limit=500)
    log(f"  checked: {health.get('checked', 0)}, alive: {health.get('alive', 0)}, dead: {health.get('dead', 0)}")

    # 5. Clean up dead stations
    dead_count = server.get_db_stats().get("dead", 0)
    if dead_count > 0:
        log(f"--- Cleaning dead stations: {dead_count}items ---")
        server.purge_dead()

    # 6. Final status
    final = server.get_db_stats()
    log(f"=== Complete: {final.get('total', 0)}items (alive: {final.get('alive', 0)}) ===")

if __name__ == "__main__":
    main()
