#!/usr/bin/env python3
"""
Sync radiomcp DB from g3 unified DB
Run weekly: 0 3 * * 0 /path/to/sync_from_unified.py
"""

import subprocess
import sqlite3
import os
from datetime import datetime

LOCAL_DB = os.path.join(os.path.dirname(__file__), '..', 'radio_stations.db')
REMOTE_HOST = os.environ.get('RADIO_REMOTE_HOST', 'g3')  # Override via env var
# Remote DB path on the source server. Override via env var RADIO_REMOTE_DB
REMOTE_DB = os.environ.get('RADIO_REMOTE_DB', '/home/user/radio_unified.db')

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def sync():
    log("=== Sync from unified DB ===")

    # 1. Extract quality stations from g3 (votes >= 1)
    query = '''
    SELECT
        id, name, url, url_resolved, favicon,
        country, countrycode, tags, codec, bitrate,
        votes, clickcount, is_verified,
        verified_at as last_checked_at, fail_count,
        bytes_received, content_type
    FROM stations
    WHERE votes >= 1 AND is_verified = 1
    '''

    log("Fetching from g3...")
    cmd = f'ssh {REMOTE_HOST} "sqlite3 -json {REMOTE_DB} \\"{query}\\""'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode != 0:
        log(f"Error: {result.stderr}")
        return

    import json
    stations = json.loads(result.stdout) if result.stdout.strip() else []
    log(f"Fetched {len(stations)} stations")

    if not stations:
        log("No stations fetched, aborting")
        return

    # 2. Update local DB
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()

    # Backup existing data (preserve is_alive state)
    c.execute('CREATE TABLE IF NOT EXISTS stations_backup AS SELECT * FROM stations')

    updated = 0
    new = 0

    for s in stations:
        c.execute('SELECT 1 FROM stations WHERE stationuuid = ?', (s['id'],))
        exists = c.fetchone()

        if exists:
            c.execute('''
                UPDATE stations SET
                    name = ?, url = ?, url_resolved = ?, favicon = ?,
                    country = ?, countrycode = ?, tags = ?, codec = ?,
                    bitrate = ?, votes = ?, clickcount = ?,
                    is_verified = ?, last_checked_at = ?
                WHERE stationuuid = ?
            ''', (
                s['name'], s['url'], s.get('url_resolved'), s.get('favicon'),
                s.get('country'), s.get('countrycode'), s.get('tags'), s.get('codec'),
                s.get('bitrate'), s.get('votes'), s.get('clickcount'),
                s.get('is_verified', 1), s.get('last_checked_at'),
                s['id']
            ))
            updated += 1
        else:
            c.execute('''
                INSERT INTO stations (
                    stationuuid, name, url, url_resolved, favicon,
                    country, countrycode, tags, codec, bitrate,
                    votes, clickcount, is_alive, is_verified, last_checked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            ''', (
                s['id'], s['name'], s['url'], s.get('url_resolved'), s.get('favicon'),
                s.get('country'), s.get('countrycode'), s.get('tags'), s.get('codec'),
                s.get('bitrate'), s.get('votes'), s.get('clickcount'),
                s.get('is_verified', 1), s.get('last_checked_at')
            ))
            new += 1

    conn.commit()
    c.execute('DROP TABLE IF EXISTS stations_backup')
    conn.commit()
    conn.close()

    log(f"Updated: {updated}, New: {new}")
    log("=== Done ===")

if __name__ == "__main__":
    sync()
