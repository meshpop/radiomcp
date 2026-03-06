#!/usr/bin/env python3
"""Radio blocklist management"""
import json
import sys
import sqlite3
import re
from datetime import datetime

BLOCKLIST_FILE = '/home/dragon/radio_blocklist.json'
UNIFIED_DB = '/home/dragon/radio_unified.db'


def load_blocklist():
    try:
        with open(BLOCKLIST_FILE, 'r') as f:
            return json.load(f)
    except:
        return {'domains': [], 'urls': [], 'station_ids': [], 'patterns': []}


def save_blocklist(bl):
    bl['_updated'] = datetime.now().strftime('%Y-%m-%d')
    with open(BLOCKLIST_FILE, 'w') as f:
        json.dump(bl, f, indent=2, ensure_ascii=False)


def add_domain(domain):
    bl = load_blocklist()
    if domain not in bl['domains']:
        bl['domains'].append(domain)
        save_blocklist(bl)
        print(f'Domain added: {domain}')
        apply_blocklist()
    else:
        print(f'Already exists: {domain}')


def add_station(station_id):
    bl = load_blocklist()
    if station_id not in bl['station_ids']:
        bl['station_ids'].append(station_id)
        save_blocklist(bl)
        print(f'Station added: {station_id}')
        apply_blocklist()
    else:
        print(f'Already exists: {station_id}')


def add_pattern(pattern):
    bl = load_blocklist()
    if pattern not in bl['patterns']:
        bl['patterns'].append(pattern)
        save_blocklist(bl)
        print(f'Pattern added: {pattern}')
        apply_blocklist()
    else:
        print(f'Already exists: {pattern}')


def apply_blocklist():
    """Apply blocklist to DB"""
    bl = load_blocklist()
    conn = sqlite3.connect(UNIFIED_DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Ensure is_blocked column exists
    try:
        c.execute('ALTER TABLE stations ADD COLUMN is_blocked INTEGER DEFAULT 0')
    except:
        pass

    blocked = 0
    stations = c.execute('SELECT id, url, name FROM stations').fetchall()

    for s in stations:
        url = s['url'] or ''
        name = s['name'] or ''
        sid = s['id']

        should_block = False

        if sid in bl.get('station_ids', []):
            should_block = True
        elif url in bl.get('urls', []):
            should_block = True
        else:
            for domain in bl.get('domains', []):
                if domain in url:
                    should_block = True
                    break
            for pattern in bl.get('patterns', []):
                if re.search(pattern, url, re.I) or re.search(pattern, name, re.I):
                    should_block = True
                    break

        if should_block:
            c.execute('UPDATE stations SET is_blocked = 1, is_verified = 0 WHERE id = ?', (sid,))
            blocked += 1

    conn.commit()
    conn.close()
    print(f'Blocked: {blocked} stations')


def list_blocked():
    conn = sqlite3.connect(UNIFIED_DB)
    c = conn.cursor()
    stations = c.execute('SELECT id, name, url FROM stations WHERE is_blocked = 1 LIMIT 50').fetchall()
    print('=== Blocked Stations ===')
    for s in stations:
        print(f'  {s[1]}: {s[2][:50]}...')
    conn.close()


def show_help():
    print('''
Radio Blocklist Management

Usage:
  python3 manage_blocklist.py domain <domain>     # Block domain
  python3 manage_blocklist.py station <id>        # Block station ID
  python3 manage_blocklist.py pattern <regex>     # Block pattern
  python3 manage_blocklist.py apply               # Apply to DB
  python3 manage_blocklist.py list                # List blocked
  python3 manage_blocklist.py show                # Show blocklist.json

Examples:
  python3 manage_blocklist.py domain example.com
  python3 manage_blocklist.py pattern ".*test.*"
''')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        show_help()
    elif sys.argv[1] == 'domain' and len(sys.argv) > 2:
        add_domain(sys.argv[2])
    elif sys.argv[1] == 'station' and len(sys.argv) > 2:
        add_station(sys.argv[2])
    elif sys.argv[1] == 'pattern' and len(sys.argv) > 2:
        add_pattern(sys.argv[2])
    elif sys.argv[1] == 'apply':
        apply_blocklist()
    elif sys.argv[1] == 'list':
        list_blocked()
    elif sys.argv[1] == 'show':
        print(json.dumps(load_blocklist(), indent=2, ensure_ascii=False))
    else:
        show_help()
