#!/usr/bin/env python3
"""
Radio MCP Server - 인터넷 라디오 검색 및 재생
"""

import json
import os
import subprocess
import socket
import urllib.request
import urllib.parse
from typing import Any

from mcp.server.fastmcp import FastMCP

# MCP 서버 생성
mcp = FastMCP("radio")

# 설정
DATA_DIR = os.path.expanduser("~/.radiocli")
FAVORITES_FILE = os.path.join(DATA_DIR, "favorites.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
MPV_SOCKET = os.path.join(DATA_DIR, "mpv.sock")
API_BASE = "https://de1.api.radio-browser.info/json"

# 전역 상태
current_station = None
player_proc = None


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_json(filepath: str) -> list:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_json(filepath: str, data: list):
    ensure_data_dir()
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def api_get(endpoint: str, params: dict = None) -> list:
    """Radio Browser API GET 호출"""
    url = f"{API_BASE}/{endpoint}"
    if params:
        query = urllib.parse.urlencode(params)
        url = f"{url}?{query}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RadioMCP/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"API error: {e}", flush=True)
        return []


def format_station(s: dict) -> dict:
    """방송국 정보 포맷"""
    return {
        "id": s.get("stationuuid", ""),
        "name": s.get("name", "Unknown"),
        "url": s.get("url_resolved") or s.get("url", ""),
        "country": s.get("country", ""),
        "countrycode": s.get("countrycode", ""),
        "tags": s.get("tags", ""),
        "bitrate": s.get("bitrate", 0),
        "votes": s.get("votes", 0),
    }


@mcp.tool()
def search(query: str, limit: int = 20) -> list[dict]:
    """
    Search radio stations by keyword (genre, name, etc.)

    Args:
        query: Search term (genre like "jazz", "kpop" or station name)
        limit: Number of results (default 20)

    Returns:
        List of radio stations
    """
    # 태그로 검색 (path에 태그 포함)
    encoded_query = urllib.parse.quote(query)
    results = api_get(f"stations/bytag/{encoded_query}", {
        "limit": limit,
        "order": "clickcount",
        "reverse": "true",
        "lastcheckok": 1
    })

    # 결과 없으면 이름으로 검색
    if not results:
        results = api_get(f"stations/byname/{encoded_query}", {
            "limit": limit,
            "order": "clickcount",
            "reverse": "true",
            "lastcheckok": 1
        })

    return [format_station(s) for s in results]


@mcp.tool()
def search_by_country(country_code: str, limit: int = 20) -> list[dict]:
    """
    Search radio stations by country

    Args:
        country_code: Country code (KR, US, JP, DE, FR, etc.)
        limit: Number of results

    Returns:
        List of radio stations
    """
    code = urllib.parse.quote(country_code.upper())
    results = api_get(f"stations/bycountrycodeexact/{code}", {
        "limit": limit,
        "order": "clickcount",
        "reverse": "true",
        "lastcheckok": 1
    })
    return [format_station(s) for s in results]


@mcp.tool()
def get_popular(limit: int = 20) -> list[dict]:
    """
    Get popular radio stations

    Args:
        limit: Number of results

    Returns:
        List of popular stations
    """
    results = api_get(f"stations/topclick/{limit}")
    return [format_station(s) for s in results]


@mcp.tool()
def play(url: str, name: str = "") -> dict:
    """
    Play a radio station

    Args:
        url: Stream URL
        name: Station name (optional)

    Returns:
        Playback status
    """
    global current_station, player_proc

    # 기존 재생 중지
    stop()

    # mpv로 재생
    try:
        # 기존 소켓 삭제
        if os.path.exists(MPV_SOCKET):
            os.remove(MPV_SOCKET)

        player_proc = subprocess.Popen(
            ["mpv", "--no-video", "--no-terminal",
             f"--input-ipc-server={MPV_SOCKET}", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        current_station = {"name": name, "url": url}
        return {"status": "playing", "name": name, "url": url}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def stop() -> dict:
    """
    Stop radio playback

    Returns:
        Stop status
    """
    global player_proc, current_station

    if player_proc:
        player_proc.terminate()
        player_proc = None

    # mpv IPC로 종료
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(MPV_SOCKET)
        sock.send(b'{"command": ["quit"]}\n')
        sock.close()
    except:
        pass

    current_station = None
    return {"status": "stopped"}


@mcp.tool()
def now_playing() -> dict:
    """
    Get current song info

    Returns:
        Current song info (title, artist)
    """
    if not current_station:
        return {"status": "not_playing"}

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect(MPV_SOCKET)

        # icy-title 가져오기
        sock.send(b'{"command": ["get_property", "media-title"]}\n')
        response = sock.recv(4096).decode()
        sock.close()

        data = json.loads(response)
        title = data.get("data", "")

        # 아티스트 - 제목 파싱
        if " - " in title:
            artist, song = title.split(" - ", 1)
            return {
                "status": "playing",
                "station": current_station.get("name", ""),
                "artist": artist.strip(),
                "title": song.strip(),
                "raw": title
            }

        return {
            "status": "playing",
            "station": current_station.get("name", ""),
            "title": title,
            "raw": title
        }
    except Exception as e:
        return {
            "status": "playing",
            "station": current_station.get("name", ""),
            "error": str(e)
        }


@mcp.tool()
def get_favorites() -> list[dict]:
    """
    Get favorite stations list

    Returns:
        List of favorite stations
    """
    return load_json(FAVORITES_FILE)


@mcp.tool()
def add_favorite(station: dict) -> dict:
    """
    Add station to favorites

    Args:
        station: Station info (name, url required)

    Returns:
        Add result
    """
    favorites = load_json(FAVORITES_FILE)

    # 중복 체크
    for fav in favorites:
        if fav.get("url") == station.get("url"):
            return {"status": "already_exists", "name": station.get("name")}

    favorites.append(station)
    save_json(FAVORITES_FILE, favorites)
    return {"status": "added", "name": station.get("name")}


@mcp.tool()
def remove_favorite(index: int) -> dict:
    """
    Remove station from favorites

    Args:
        index: Index to remove (0-based)

    Returns:
        Remove result
    """
    favorites = load_json(FAVORITES_FILE)

    if 0 <= index < len(favorites):
        removed = favorites.pop(index)
        save_json(FAVORITES_FILE, favorites)
        return {"status": "removed", "name": removed.get("name")}

    return {"status": "error", "message": "Invalid index"}


@mcp.tool()
def get_history(limit: int = 20) -> list[dict]:
    """
    Get listening history

    Args:
        limit: Number of results

    Returns:
        Recent listening history
    """
    history = load_json(HISTORY_FILE)
    return history[-limit:][::-1]  # 최신순


@mcp.tool()
def recommend(mood: str = "relaxing") -> list[dict]:
    """
    Get mood-based recommendations

    Args:
        mood: Mood keyword (relaxing, energetic, focus, sleep, morning, workout, romantic)

    Returns:
        Recommended stations
    """
    mood_tags = {
        "relaxing": ["lounge", "ambient", "classical", "jazz"],
        "energetic": ["dance", "electronic", "pop", "rock"],
        "focus": ["classical", "ambient", "instrumental"],
        "sleep": ["ambient", "classical"],
        "morning": ["pop", "jazz"],
        "workout": ["electronic", "dance", "rock"],
        "romantic": ["jazz", "classical"],
    }

    tags = mood_tags.get(mood.lower(), [mood])

    all_results = []
    for tag in tags[:2]:  # 상위 2개 태그만
        encoded_tag = urllib.parse.quote(tag)
        results = api_get(f"stations/bytag/{encoded_tag}", {
            "limit": 15,
            "order": "votes",
            "reverse": "true",
            "lastcheckok": 1
        })
        all_results.extend(results)

    # 중복 제거 및 정렬
    seen = set()
    unique = []
    for s in all_results:
        if s.get("stationuuid") not in seen:
            seen.add(s.get("stationuuid"))
            unique.append(s)

    unique.sort(key=lambda x: x.get("votes", 0), reverse=True)
    return [format_station(s) for s in unique[:20]]


if __name__ == "__main__":
    mcp.run()
