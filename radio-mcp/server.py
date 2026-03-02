#!/usr/bin/env python3
"""
Radio MCP Server - 인터넷 라디오 검색 및 재생
"""

import json
import os
import subprocess
import socket
import urllib.request
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


def api_search(endpoint: str, params: dict = None) -> list:
    """Radio Browser API 호출"""
    url = f"{API_BASE}/{endpoint}"
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{query}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RadioMCP/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return []


def format_station(s: dict) -> dict:
    """방송국 정보 포맷"""
    return {
        "id": s.get("stationuuid", ""),
        "name": s.get("name", "Unknown"),
        "url": s.get("url_resolved") or s.get("url", ""),
        "country": s.get("country", ""),
        "tags": s.get("tags", ""),
        "bitrate": s.get("bitrate", 0),
        "votes": s.get("votes", 0),
    }


@mcp.tool()
def search(query: str, limit: int = 20) -> list[dict]:
    """
    라디오 방송국 검색

    Args:
        query: 검색어 (장르, 국가, 이름 등)
        limit: 결과 개수 (기본 20)

    Returns:
        방송국 목록
    """
    # 태그로 검색
    results = api_search("stations/bytag", {
        "tag": query,
        "limit": limit,
        "order": "clickcount",
        "reverse": "true"
    })

    # 결과 없으면 이름으로 검색
    if not results:
        results = api_search("stations/byname", {
            "name": query,
            "limit": limit,
            "order": "clickcount",
            "reverse": "true"
        })

    return [format_station(s) for s in results]


@mcp.tool()
def search_by_country(country_code: str, limit: int = 20) -> list[dict]:
    """
    국가별 라디오 검색

    Args:
        country_code: 국가 코드 (KR, US, JP 등)
        limit: 결과 개수

    Returns:
        방송국 목록
    """
    results = api_search("stations/bycountrycodeexact", {
        "countrycode": country_code.upper(),
        "limit": limit,
        "order": "clickcount",
        "reverse": "true"
    })
    return [format_station(s) for s in results]


@mcp.tool()
def get_popular(limit: int = 20) -> list[dict]:
    """
    인기 라디오 방송국

    Args:
        limit: 결과 개수

    Returns:
        인기 방송국 목록
    """
    results = api_search("stations/topvote", {"limit": limit})
    return [format_station(s) for s in results]


@mcp.tool()
def play(url: str, name: str = "") -> dict:
    """
    라디오 재생

    Args:
        url: 스트림 URL
        name: 방송국 이름 (선택)

    Returns:
        재생 상태
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
    라디오 정지

    Returns:
        정지 상태
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
    현재 재생 중인 곡 정보

    Returns:
        현재 곡 정보 (제목, 아티스트 등)
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
    즐겨찾기 목록

    Returns:
        즐겨찾기 방송국 목록
    """
    return load_json(FAVORITES_FILE)


@mcp.tool()
def add_favorite(station: dict) -> dict:
    """
    즐겨찾기 추가

    Args:
        station: 방송국 정보 (name, url 필수)

    Returns:
        추가 결과
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
    즐겨찾기 삭제

    Args:
        index: 삭제할 인덱스 (0부터 시작)

    Returns:
        삭제 결과
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
    청취 기록

    Args:
        limit: 결과 개수

    Returns:
        최근 청취 기록
    """
    history = load_json(HISTORY_FILE)
    return history[-limit:][::-1]  # 최신순


@mcp.tool()
def recommend(mood: str = "relaxing") -> list[dict]:
    """
    분위기 기반 추천

    Args:
        mood: 분위기 (relaxing, energetic, focus, sleep 등)

    Returns:
        추천 방송국 목록
    """
    mood_tags = {
        "relaxing": ["lounge", "ambient", "classical", "jazz"],
        "energetic": ["dance", "electronic", "pop", "rock"],
        "focus": ["classical", "ambient", "lofi", "instrumental"],
        "sleep": ["ambient", "nature", "classical", "sleep"],
        "morning": ["pop", "jazz", "news"],
        "workout": ["electronic", "dance", "rock", "hiphop"],
        "romantic": ["jazz", "ballad", "classical"],
    }

    tags = mood_tags.get(mood.lower(), [mood])

    all_results = []
    for tag in tags[:2]:  # 상위 2개 태그만
        results = api_search("stations/bytag", {
            "tag": tag,
            "limit": 10,
            "order": "votes",
            "reverse": "true"
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
