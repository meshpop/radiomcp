#!/usr/bin/env python3
"""HLS (.m3u8) stream validator"""
import requests
import re
from urllib.parse import urljoin

TIMEOUT = 10


def validate_hls(url: str) -> dict:
    """
    Validate HLS stream
    1. Download m3u8 playlist
    2. Extract segment URLs
    3. Test first segment
    """
    result = {
        'url': url,
        'valid': False,
        'is_hls': False,
        'segments': 0,
        'bandwidth': None,
        'bytes_received': 0,
        'error': None
    }

    try:
        # 1. Get playlist
        resp = requests.get(url, timeout=TIMEOUT, headers={
            'User-Agent': 'RadioCli/1.0'
        })

        if resp.status_code != 200:
            result['error'] = f'HTTP {resp.status_code}'
            return result

        content = resp.text

        # Check HLS
        if '#EXTM3U' not in content:
            result['error'] = 'Not a valid M3U8 playlist'
            return result

        result['is_hls'] = True

        # 2. Check if master playlist (multiple qualities)
        if '#EXT-X-STREAM-INF' in content:
            lines = content.strip().split('\n')
            for i, line in enumerate(lines):
                if line.startswith('#EXT-X-STREAM-INF'):
                    # Extract BANDWIDTH
                    bw_match = re.search(r'BANDWIDTH=(\d+)', line)
                    if bw_match:
                        result['bandwidth'] = int(bw_match.group(1))

                    # Next line is URL
                    if i + 1 < len(lines):
                        variant_url = lines[i + 1].strip()
                        if not variant_url.startswith('http'):
                            variant_url = urljoin(url, variant_url)

                        # Get variant playlist
                        resp2 = requests.get(variant_url, timeout=TIMEOUT)
                        content = resp2.text
                        break

        # 3. Extract segment URLs
        lines = content.strip().split('\n')
        segments = []

        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                if not line.startswith('http'):
                    line = urljoin(url, line)
                segments.append(line)

        result['segments'] = len(segments)

        if not segments:
            result['error'] = 'No segments found'
            return result

        # 4. Test first segment
        seg_url = segments[0]
        seg_resp = requests.get(seg_url, timeout=TIMEOUT, stream=True)
        data = seg_resp.raw.read(8192)
        result['bytes_received'] = len(data)

        # Success if >= 1KB received
        if len(data) >= 1024:
            result['valid'] = True
        else:
            result['error'] = f'Segment too small: {len(data)} bytes'

    except requests.Timeout:
        result['error'] = 'Timeout'
    except requests.ConnectionError as e:
        result['error'] = f'Connection error: {str(e)[:50]}'
    except Exception as e:
        result['error'] = f'Error: {str(e)[:50]}'

    return result


def validate_stream(url: str) -> dict:
    """
    Auto-detect stream type and validate
    """
    if '.m3u8' in url.lower() or 'playlist' in url.lower():
        return validate_hls(url)
    else:
        # Regular stream
        try:
            resp = requests.get(url, timeout=TIMEOUT, stream=True)
            data = resp.raw.read(4096)
            return {
                'url': url,
                'valid': len(data) >= 1024,
                'is_hls': False,
                'bytes_received': len(data),
                'error': None if len(data) >= 1024 else 'Too small'
            }
        except Exception as e:
            return {
                'url': url,
                'valid': False,
                'is_hls': False,
                'bytes_received': 0,
                'error': str(e)[:50]
            }


if __name__ == '__main__':
    # Test
    test_urls = [
        'https://m-aac.cbs.co.kr/mweb_cbs939/_definst_/cbs939.stream/playlist.m3u8',
        'https://mgugaklive.nowcdn.co.kr/gugakradio/gugakradio.stream/playlist.m3u8',
        'https://ebsonair.ebs.co.kr/fmradiofamilypc/familypc1m/playlist.m3u8',
        'http://amdlive.ctnd.com.edgesuite.net/arirang_3ch/smil:arirang_3ch.smil/playlist.m3u8',
    ]

    print('=== HLS Validation Test ===')
    for url in test_urls:
        result = validate_hls(url)
        status = '✓' if result['valid'] else '✗'
        name = url.split('/')[-2] if '/' in url else url[:30]
        print(f"{status} {name}: {result.get('segments', 0)} segments, {result['bytes_received']} bytes")
        if result['error']:
            print(f"  └─ {result['error']}")
