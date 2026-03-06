#!/usr/bin/env python3
"""
Auto Broadcaster System
- Reads broadcaster_registry.json
- Resolves URLs for each broadcaster type
- Syncs to database
- Daily health checks
"""
import json
import sqlite3
import requests
from datetime import datetime
from typing import Optional, Dict, List

REGISTRY_FILE = '/home/dragon/broadcaster_registry.json'
DB_FILE = '/home/dragon/radio_unified.db'
TIMEOUT = 10
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
HEADERS = {'User-Agent': UA}


def load_registry() -> dict:
    with open(REGISTRY_FILE, 'r') as f:
        return json.load(f)


def resolve_kbs(api_url: str, code: str) -> Optional[str]:
    """KBS CloudFront signed URL"""
    try:
        url = api_url.replace('{code}', code)
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        data = resp.json()
        items = data.get('channel_item', [])
        for item in items:
            if item.get('media_type') == 'radio':
                return item.get('service_url')
        if items:
            return items[0].get('service_url')
    except Exception as e:
        print(f'  KBS error: {e}')
    return None


def resolve_mbc(api_url: str, channel_id: str) -> Optional[str]:
    """MBC direct API"""
    try:
        url = api_url.replace('{id}', channel_id)
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        text = resp.text.strip()
        if text.startswith('http'):
            return text
    except Exception as e:
        print(f'  MBC error: {e}')
    return None


def resolve_static(base_url: str, channel_id: str) -> str:
    """Static URL with channel substitution"""
    return base_url.replace('{channel_id}', channel_id)


def resolve_channel(broadcaster: dict, channel: dict) -> Optional[str]:
    """Resolve URL for a channel based on broadcaster type"""
    api_type = broadcaster.get('api_type')
    
    if api_type == 'static_url':
        # Check if channel has direct URL
        if 'url' in channel:
            return channel['url']
        # Or use base_url template
        base_url = broadcaster.get('base_url', '')
        return resolve_static(base_url, channel['id'])
    
    elif api_type == 'cloudfront_signed':
        return resolve_kbs(broadcaster['api_url'], channel.get('code', ''))
    
    elif api_type == 'direct_api':
        return resolve_mbc(broadcaster['api_url'], channel['id'])
    
    elif api_type == 'geo_restricted':
        return None  # Skip geo-restricted
    
    elif api_type == 'unknown':
        return None  # Skip unknown
    
    return None


def test_stream(url: str) -> bool:
    """Test if stream is working"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
        data = resp.raw.read(4096)
        return len(data) >= 1024
    except:
        return False


def sync_to_db(stations: List[dict]):
    """Sync resolved stations to database"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Ensure columns exist
    try:
        c.execute('ALTER TABLE stations ADD COLUMN broadcaster TEXT')
    except:
        pass
    
    for s in stations:
        station_id = f"{s['broadcaster_id']}-{s['channel_id']}"
        
        existing = c.execute('SELECT id FROM stations WHERE id = ?', (station_id,)).fetchone()
        
        if existing:
            c.execute('''
                UPDATE stations SET 
                    name = ?, url = ?, url_resolved = ?, tags = ?,
                    countrycode = ?, broadcaster = ?,
                    is_verified = ?, verified_at = datetime('now')
                WHERE id = ?
            ''', (
                s['name'], s['url'], s['url'], s['tags'],
                s['country'], s['broadcaster_id'],
                1 if s['verified'] else 0, station_id
            ))
        else:
            c.execute('''
                INSERT OR REPLACE INTO stations 
                (id, name, url, url_resolved, tags, countrycode, country, broadcaster, 
                 is_verified, source, created_at, verified_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'auto_broadcaster', datetime('now'), datetime('now'))
            ''', (
                station_id, s['name'], s['url'], s['url'], s['tags'],
                s['country'], s['country_name'], s['broadcaster_id'],
                1 if s['verified'] else 0
            ))
    
    conn.commit()
    conn.close()


def get_country_name(code: str) -> str:
    """Get country name from code"""
    names = {
        'KR': 'South Korea', 'JP': 'Japan', 'GB': 'United Kingdom',
        'US': 'United States', 'DE': 'Germany', 'FR': 'France'
    }
    return names.get(code, code)


def run_sync(test_streams: bool = True):
    """Main sync function"""
    registry = load_registry()
    broadcasters = registry.get('broadcasters', {})
    
    all_stations = []
    
    print(f'=== Auto Broadcaster Sync ===')
    print(f'Time: {datetime.now()}')
    print()
    
    for bc_id, bc in broadcasters.items():
        print(f'{bc["name"]}:')
        
        if bc.get('status') in ['research_needed', 'japan_only']:
            print(f'  Skipped ({bc.get("status")})')
            continue
        
        for ch in bc.get('channels', []):
            url = resolve_channel(bc, ch)
            
            if not url:
                print(f'  ✗ {ch["name"]}: No URL')
                continue
            
            verified = False
            if test_streams:
                verified = test_stream(url)
            else:
                verified = True
            
            status = '✓' if verified else '✗'
            print(f'  {status} {ch["name"]}')
            
            all_stations.append({
                'broadcaster_id': bc_id,
                'channel_id': ch['id'],
                'name': ch['name'],
                'url': url,
                'tags': ch.get('tags', ''),
                'country': bc['country'],
                'country_name': get_country_name(bc['country']),
                'verified': verified
            })
    
    print()
    print(f'Syncing {len(all_stations)} stations to DB...')
    sync_to_db(all_stations)
    
    verified_count = sum(1 for s in all_stations if s['verified'])
    print(f'Done! Verified: {verified_count}/{len(all_stations)}')


def health_check():
    """Check health of all broadcaster stations"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    stations = c.execute('''
        SELECT id, name, url, broadcaster FROM stations 
        WHERE broadcaster IS NOT NULL
    ''').fetchall()
    
    print(f'=== Broadcaster Health Check ===')
    print(f'Time: {datetime.now()}')
    print(f'Stations: {len(stations)}')
    print()
    
    for s in stations:
        ok = test_stream(s['url'])
        status = '✓' if ok else '✗'
        print(f'{status} [{s["broadcaster"]}] {s["name"]}')
        
        c.execute('''
            UPDATE stations SET is_verified = ?, verified_at = datetime('now')
            WHERE id = ?
        ''', (1 if ok else 0, s['id']))
    
    conn.commit()
    conn.close()


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'health':
        health_check()
    else:
        run_sync(test_streams=True)
