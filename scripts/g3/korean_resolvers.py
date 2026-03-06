#!/usr/bin/env python3
"""
Korean broadcaster URL resolvers
KBS, MBC, SBS, YTN - fetch fresh streaming URLs with tokens
"""
import requests
import re
import json
from typing import Optional

TIMEOUT = 10
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
HEADERS = {'User-Agent': UA}


# === KBS ===
KBS_CHANNELS = {
    'kbs1-radio': {'name': 'KBS 1라디오', 'code': '21'},
    'kbs2-radio': {'name': 'KBS 2라디오 해피FM', 'code': '22'},
    'kbs3-radio': {'name': 'KBS 3라디오', 'code': '23'},
    'kbs-classic': {'name': 'KBS 클래식FM', 'code': '24'},
    'kbs-cool': {'name': 'KBS Cool FM', 'code': '25'},
    'kbs-world': {'name': 'KBS 한민족방송', 'code': '26'},
}


def resolve_kbs(channel_id: str) -> Optional[str]:
    """Get KBS radio stream URL"""
    try:
        ch = KBS_CHANNELS.get(channel_id, {})
        code = ch.get('code')
        if not code:
            return None

        # KBS CloudFront API with signed URL
        api_url = f'https://cfpwwwapi.kbs.co.kr/api/v1/landing/live/channel_code/{code}'
        resp = requests.get(api_url, headers=HEADERS, timeout=TIMEOUT)
        data = resp.json()

        items = data.get('channel_item', [])
        if items:
            # Get first radio stream (not bora)
            for item in items:
                if item.get('media_type') == 'radio':
                    return item.get('service_url')
            # Fallback to first item
            return items[0].get('service_url')

        return None
    except Exception as e:
        print(f'KBS resolve error: {e}')
        return None


# === MBC ===
MBC_CHANNELS = {
    'mbc-fm4u': {'name': 'MBC FM4U', 'id': 'mfm'},
    'mbc-sfm': {'name': 'MBC 표준FM', 'id': 'sfm'},
    'mbc-allthat': {'name': 'MBC 올댓뮤직', 'id': 'chm'},
}


def resolve_mbc(channel_id: str) -> Optional[str]:
    """Get MBC radio stream URL"""
    try:
        ch = MBC_CHANNELS.get(channel_id, {})
        mbc_id = ch.get('id')
        if not mbc_id:
            return None

        # MBC mini player API
        api_url = f'https://sminiplay.imbc.com/aacplay.ashx?channel={mbc_id}&protocol=M3U8&agent=webapp'
        resp = requests.get(api_url, headers=HEADERS, timeout=TIMEOUT)

        text = resp.text.strip()
        if text.startswith('http'):
            return text

        return None
    except Exception as e:
        print(f'MBC resolve error: {e}')
        return None


# === SBS === (TODO: find working API)
SBS_CHANNELS = {
    'sbs-power': {'name': 'SBS 파워FM', 'id': 'powerfm'},
    'sbs-love': {'name': 'SBS 러브FM', 'id': 'lovefm'},
}


def resolve_sbs(channel_id: str) -> Optional[str]:
    """Get SBS radio stream URL - TODO: find working API"""
    # SBS changed their API, needs more research
    # Possible endpoints to investigate:
    # - https://api.gorealra.com/
    # - https://api.play.sbs.co.kr/
    return None


# === YTN ===
YTN_CHANNELS = {
    'ytn-radio': {'name': 'YTN 라디오', 'url': 'https://ytnlive.ytndj.co.kr/live/ytnradio.m3u8'},
    'ytn-science': {'name': 'YTN 사이언스', 'url': 'https://ytnlive.ytndj.co.kr/live/ytnscience.m3u8'},
}


def resolve_ytn(channel_id: str) -> Optional[str]:
    """Get YTN stream URL"""
    ch = YTN_CHANNELS.get(channel_id, {})
    return ch.get('url')


# === Main resolver ===
RESOLVERS = {
    'kbs': resolve_kbs,
    'mbc': resolve_mbc,
    'sbs': resolve_sbs,
    'ytn': resolve_ytn,
}


def resolve_url(resolver_type: str, channel_id: str) -> Optional[str]:
    """Resolve stream URL for Korean broadcasters"""
    resolver = RESOLVERS.get(resolver_type)
    if not resolver:
        return None
    return resolver(channel_id)


# === Korean stations metadata ===
KOREAN_STATIONS = [
    # KBS
    {'id': 'kbs1-radio', 'name': 'KBS 1라디오', 'resolver': 'kbs', 'tags': 'news,talk', 'country': 'KR'},
    {'id': 'kbs2-radio', 'name': 'KBS 2라디오 해피FM', 'resolver': 'kbs', 'tags': 'entertainment,music', 'country': 'KR'},
    {'id': 'kbs3-radio', 'name': 'KBS 3라디오', 'resolver': 'kbs', 'tags': 'education,talk', 'country': 'KR'},
    {'id': 'kbs-classic', 'name': 'KBS 클래식FM', 'resolver': 'kbs', 'tags': 'classical', 'country': 'KR'},
    {'id': 'kbs-cool', 'name': 'KBS Cool FM', 'resolver': 'kbs', 'tags': 'pop,music', 'country': 'KR'},
    {'id': 'kbs-world', 'name': 'KBS 한민족방송', 'resolver': 'kbs', 'tags': 'korean,world', 'country': 'KR'},
    # MBC
    {'id': 'mbc-fm4u', 'name': 'MBC FM4U', 'resolver': 'mbc', 'tags': 'pop,music', 'country': 'KR'},
    {'id': 'mbc-sfm', 'name': 'MBC 표준FM', 'resolver': 'mbc', 'tags': 'news,talk', 'country': 'KR'},
    {'id': 'mbc-allthat', 'name': 'MBC 올댓뮤직', 'resolver': 'mbc', 'tags': 'music', 'country': 'KR'},
    # SBS (TODO: find API)
    {'id': 'sbs-power', 'name': 'SBS 파워FM', 'resolver': 'sbs', 'tags': 'pop,music', 'country': 'KR'},
    {'id': 'sbs-love', 'name': 'SBS 러브FM', 'resolver': 'sbs', 'tags': 'talk,music', 'country': 'KR'},
    # YTN
    {'id': 'ytn-radio', 'name': 'YTN 라디오', 'resolver': 'ytn', 'tags': 'news', 'country': 'KR'},
    {'id': 'ytn-science', 'name': 'YTN 사이언스', 'resolver': 'ytn', 'tags': 'science,education', 'country': 'KR'},
]


def get_all_korean_stations() -> list:
    """Get all Korean stations with resolved URLs"""
    result = []
    for station in KOREAN_STATIONS:
        url = resolve_url(station['resolver'], station['id'])
        if url:
            result.append({
                **station,
                'url': url,
                'url_resolved': url,
            })
    return result


if __name__ == '__main__':
    print('=== Korean Broadcaster URL Resolver Test ===')
    print()

    for station in KOREAN_STATIONS:
        url = resolve_url(station['resolver'], station['id'])
        status = '✓' if url else '✗'
        url_preview = url[:70] + '...' if url and len(url) > 70 else (url or 'Failed')
        print(f"{status} {station['name']:<20} {url_preview}")
