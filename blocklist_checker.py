#!/usr/bin/env python3
"""
Blocklist checker for RadioCli/RadioMCP
Checks GitHub-hosted blocklist on startup to filter blocked stations
"""
import json
import os
import urllib.request
import time

# GitHub raw URL for blocklist
BLOCKLIST_URL = "https://raw.githubusercontent.com/anthropics/radiocli/main/blocklist.json"
# Local cache
CACHE_DIR = os.path.expanduser("~/.radiocli")
BLOCKLIST_CACHE = os.path.join(CACHE_DIR, "blocklist_cache.json")
CACHE_TTL = 3600  # 1 hour

_blocklist = None

def fetch_blocklist():
    """Fetch blocklist from GitHub"""
    try:
        req = urllib.request.Request(BLOCKLIST_URL, headers={'User-Agent': 'RadioCli/1.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            # Cache locally
            os.makedirs(CACHE_DIR, exist_ok=True)
            data['_cached_at'] = time.time()
            with open(BLOCKLIST_CACHE, 'w') as f:
                json.dump(data, f)
            return data
    except Exception as e:
        print(f"[blocklist] Failed to fetch: {e}")
        return None

def load_blocklist():
    """Load blocklist from cache or fetch from GitHub"""
    global _blocklist
    
    # Check cache first
    if os.path.exists(BLOCKLIST_CACHE):
        try:
            with open(BLOCKLIST_CACHE, 'r') as f:
                cached = json.load(f)
                cached_at = cached.get('_cached_at', 0)
                if time.time() - cached_at < CACHE_TTL:
                    _blocklist = cached
                    return _blocklist
        except:
            pass
    
    # Fetch from GitHub
    fetched = fetch_blocklist()
    if fetched:
        _blocklist = fetched
        return _blocklist
    
    # Use expired cache if fetch failed
    if os.path.exists(BLOCKLIST_CACHE):
        try:
            with open(BLOCKLIST_CACHE, 'r') as f:
                _blocklist = json.load(f)
                return _blocklist
        except:
            pass
    
    # Empty blocklist as fallback
    _blocklist = {'station_ids': [], 'urls': [], 'domains': [], 'patterns': []}
    return _blocklist

def is_blocked(station):
    """Check if a station is blocked"""
    global _blocklist
    if _blocklist is None:
        load_blocklist()
    
    if not _blocklist:
        return False
    
    # Get station info
    station_id = station.get('stationuuid') or station.get('id') or ''
    url = station.get('url') or station.get('url_resolved') or ''
    name = station.get('name') or ''
    
    # Check station ID
    if station_id in _blocklist.get('station_ids', []):
        return True
    
    # Check URL
    if url in _blocklist.get('urls', []):
        return True
    
    # Check domains
    for domain in _blocklist.get('domains', []):
        if domain in url:
            return True
    
    # Check patterns (regex)
    import re
    for pattern in _blocklist.get('patterns', []):
        try:
            if re.search(pattern, url, re.I) or re.search(pattern, name, re.I):
                return True
        except:
            pass
    
    return False

def filter_blocked(stations):
    """Filter out blocked stations from a list"""
    return [s for s in stations if not is_blocked(s)]

# Auto-load on import
load_blocklist()

if __name__ == '__main__':
    # Test
    bl = load_blocklist()
    print(f"Blocklist loaded: {len(bl.get('station_ids', []))} stations, {len(bl.get('domains', []))} domains")
