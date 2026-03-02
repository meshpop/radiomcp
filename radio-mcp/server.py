#!/usr/bin/env python3
"""
Radio MCP Server - 인터넷 라디오 검색 및 재생
SQLite DB 우선, Radio Browser API fallback
"""

import json
import os
import subprocess
import socket
import sqlite3
import urllib.request
import urllib.parse
import time
from typing import Any
from datetime import datetime

from mcp.server.fastmcp import FastMCP

# MCP 서버 생성
mcp = FastMCP("radio")

# 설정
DATA_DIR = os.path.expanduser("~/.radiocli")
FAVORITES_FILE = os.path.join(DATA_DIR, "favorites.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
MPV_SOCKET = os.path.join(DATA_DIR, "mpv.sock")
API_BASE = "https://de1.api.radio-browser.info/json"

# DB 경로 (우선순위: 로컬 > 프로젝트)
DB_PATHS = [
    os.path.join(DATA_DIR, "radio_stations.db"),
    os.path.expanduser("~/RadioCli/radio_stations.db"),
    "/Users/dragon/RadioCli/radio_stations.db",
]

# 전역 상태
current_station = None
player_proc = None
db_conn = None
sleep_timer = None  # 슬립 타이머

# 유사어 매핑 (태그 확장)
TAG_SYNONYMS = {
    "lounge": ["lounge", "chillout", "cafe", "ambient", "easy listening"],
    "jazz": ["jazz", "smooth jazz", "jazz lounge", "bossa nova"],
    "classical": ["classical", "classic", "orchestra", "symphony", "piano"],
    "rock": ["rock", "classic rock", "hard rock", "alternative"],
    "pop": ["pop", "top 40", "hits", "chart"],
    "electronic": ["electronic", "edm", "dance", "house", "techno", "trance"],
    "ambient": ["ambient", "chillout", "relaxing", "meditation", "sleep"],
    "hiphop": ["hiphop", "hip-hop", "rap", "r&b", "rnb"],
    "bossa nova": ["bossa nova", "bossa", "brazilian", "latin jazz"],
    "chillout": ["chillout", "chill", "lounge", "ambient", "downtempo"],
    "cafe": ["cafe", "coffee", "lounge", "acoustic", "bossa nova"],
    "sleep": ["sleep", "ambient", "relaxing", "meditation", "nature"],
    "focus": ["focus", "study", "concentration", "instrumental", "classical"],
    "workout": ["workout", "gym", "exercise", "dance", "electronic", "energetic"],
    "morning": ["morning", "wake up", "breakfast", "pop", "acoustic"],
    "night": ["night", "late night", "jazz", "lounge", "ambient"],
    "rain": ["rain", "nature", "ambient", "relaxing", "piano"],
    "summer": ["summer", "tropical", "beach", "latin", "reggae"],
    "winter": ["winter", "christmas", "cozy", "acoustic", "classical"],
}

# 날씨/계절 → 태그 매핑
WEATHER_TAGS = {
    "rainy": ["jazz", "lounge", "piano", "ambient"],
    "sunny": ["pop", "bossa nova", "tropical", "summer"],
    "cloudy": ["indie", "acoustic", "folk", "ambient"],
    "snowy": ["classical", "christmas", "cozy", "piano"],
    "hot": ["tropical", "latin", "reggae", "summer"],
    "cold": ["jazz", "classical", "lounge", "cozy"],
}

# 시간대 → 태그 매핑
TIME_TAGS = {
    "morning": ["pop", "acoustic", "breakfast", "morning"],      # 6-10
    "daytime": ["pop", "rock", "hits", "energetic"],             # 10-17
    "evening": ["jazz", "lounge", "dinner", "relaxing"],         # 17-21
    "night": ["ambient", "chillout", "sleep", "lounge"],         # 21-6
}


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def get_db():
    """SQLite DB 연결 (싱글톤)"""
    global db_conn
    if db_conn:
        return db_conn

    for path in DB_PATHS:
        if os.path.exists(path):
            db_conn = sqlite3.connect(path, check_same_thread=False)
            db_conn.row_factory = sqlite3.Row
            print(f"DB loaded: {path}", flush=True)
            return db_conn

    print("No DB found, using API only", flush=True)
    return None


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


def format_station(s) -> dict:
    """방송국 정보 포맷 (dict 또는 sqlite Row)"""
    if isinstance(s, sqlite3.Row):
        s = dict(s)
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


def expand_tags(query: str) -> list:
    """쿼리를 여러 태그로 확장 (복합 태그 + 유사어)"""
    # 공백으로 분리
    words = query.lower().strip().split()
    all_tags = set()

    # 원본 쿼리도 포함
    all_tags.add(query.lower().strip())

    # 각 단어별 유사어 확장
    for word in words:
        all_tags.add(word)
        if word in TAG_SYNONYMS:
            all_tags.update(TAG_SYNONYMS[word])

    # 2단어 조합도 체크 (예: "bossa nova")
    if len(words) >= 2:
        for i in range(len(words) - 1):
            combo = f"{words[i]} {words[i+1]}"
            all_tags.add(combo)
            if combo in TAG_SYNONYMS:
                all_tags.update(TAG_SYNONYMS[combo])

    return list(all_tags)


def get_time_of_day() -> str:
    """현재 시간대 반환"""
    hour = datetime.now().hour
    if 6 <= hour < 10:
        return "morning"
    elif 10 <= hour < 17:
        return "daytime"
    elif 17 <= hour < 21:
        return "evening"
    else:
        return "night"


def db_search(query: str, field: str = "tags", limit: int = 20) -> list:
    """DB에서 검색"""
    db = get_db()
    if not db:
        return []

    try:
        cursor = db.cursor()
        sql = f"""
            SELECT * FROM stations
            WHERE {field} LIKE ? AND (is_alive = 1 OR is_alive IS NULL)
            ORDER BY clickcount DESC
            LIMIT ?
        """
        cursor.execute(sql, (f"%{query}%", limit))
        return [format_station(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"DB error: {e}", flush=True)
        return []


def db_search_country(code: str, limit: int = 20) -> list:
    """DB에서 국가별 검색"""
    db = get_db()
    if not db:
        return []

    try:
        cursor = db.cursor()
        sql = """
            SELECT * FROM stations
            WHERE countrycode = ? AND (is_alive = 1 OR is_alive IS NULL)
            ORDER BY clickcount DESC
            LIMIT ?
        """
        cursor.execute(sql, (code.upper(), limit))
        return [format_station(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"DB error: {e}", flush=True)
        return []


def db_get_popular(limit: int = 20) -> list:
    """DB에서 인기 방송국"""
    db = get_db()
    if not db:
        return []

    try:
        cursor = db.cursor()
        sql = """
            SELECT * FROM stations
            WHERE is_alive = 1 OR is_alive IS NULL
            ORDER BY clickcount DESC
            LIMIT ?
        """
        cursor.execute(sql, (limit,))
        return [format_station(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"DB error: {e}", flush=True)
        return []


def mark_station_dead(url: str):
    """방송국을 죽은 것으로 표시"""
    db = get_db()
    if not db:
        return

    try:
        cursor = db.cursor()
        cursor.execute("""
            UPDATE stations
            SET is_alive = 0, fail_count = COALESCE(fail_count, 0) + 1,
                last_checked_at = ?
            WHERE url = ? OR url_resolved = ?
        """, (datetime.now().isoformat(), url, url))
        db.commit()
        print(f"Marked dead: {url}", flush=True)
    except Exception as e:
        print(f"DB update error: {e}", flush=True)


def is_valid_station(station: dict) -> bool:
    """방송국이 DB에 추가해도 되는지 검증"""
    url = station.get("url_resolved") or station.get("url", "")

    # 토큰/세션 파라미터가 있는 URL 제외
    if "?" in url or "&" in url:
        return False

    # 의심스러운 도메인 제외
    blocked_domains = [
        "duckdns.org", "no-ip.org", "ddns.net", "iptime.org",
        "zstream.win", "bsod.kr", "localhost", "127.0.0.1"
    ]
    url_lower = url.lower()
    for domain in blocked_domains:
        if domain in url_lower:
            return False

    # IP 주소 직접 사용 제외 (예: http://211.33.246.4:port)
    import re
    if re.search(r"https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", url_lower):
        return False

    # 최소 품질 기준
    if station.get("votes", 0) < 5:
        return False

    return True


def add_station_to_db(station: dict):
    """새 방송국을 DB에 추가 (검증 통과시에만)"""
    if not is_valid_station(station):
        return

    db = get_db()
    if not db:
        return

    try:
        cursor = db.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO stations
            (stationuuid, name, url, url_resolved, country, countrycode, tags, bitrate, votes, clickcount, is_alive, last_checked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (
            station.get("stationuuid", ""),
            station.get("name", ""),
            station.get("url", ""),
            station.get("url_resolved", ""),
            station.get("country", ""),
            station.get("countrycode", ""),
            station.get("tags", ""),
            station.get("bitrate", 0),
            station.get("votes", 0),
            station.get("clickcount", 0),
            datetime.now().isoformat()
        ))
        db.commit()
        print(f"Added to DB: {station.get('name')}", flush=True)
    except Exception as e:
        print(f"DB insert error: {e}", flush=True)


@mcp.tool()
def search(query: str, limit: int = 20) -> list[dict]:
    """
    Search radio stations by keyword (genre, name, etc.)
    Supports complex queries like "bossa nova lounge" with synonym expansion.

    Args:
        query: Search term (genre like "jazz", "kpop" or station name)
        limit: Number of results (default 20)

    Returns:
        List of radio stations
    """
    all_results = []
    seen_urls = set()

    # 태그 확장 (복합 태그 + 유사어)
    expanded_tags = expand_tags(query)

    # 1. DB에서 검색 (확장된 태그들로)
    for tag in expanded_tags[:5]:  # 상위 5개 태그만
        db_results = db_search(tag, "tags", limit // 2)
        for r in db_results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                r["source"] = "db"
                all_results.append(r)

    # 이름으로도 검색
    if len(all_results) < limit // 2:
        db_results = db_search(query, "name", limit)
        for r in db_results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                r["source"] = "db"
                all_results.append(r)

    # 2. Radio Browser API (확장된 태그들로)
    for tag in expanded_tags[:3]:  # 상위 3개 태그만
        encoded_tag = urllib.parse.quote(tag)
        api_results = api_get(f"stations/bytag/{encoded_tag}", {
            "limit": limit // 2,
            "order": "clickcount",
            "reverse": "true",
            "lastcheckok": 1
        })

        for s in api_results:
            url = s.get("url_resolved") or s.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                station = format_station(s)
                station["source"] = "api"
                all_results.append(station)
                if is_valid_station(s):
                    add_station_to_db(s)

    # votes 기준 정렬
    all_results.sort(key=lambda x: x.get("votes", 0), reverse=True)
    return all_results[:limit]


@mcp.tool()
def search_by_country(country_code: str, limit: int = 20) -> list[dict]:
    """
    Search radio stations by country.
    Merges results from local DB and Radio Browser API.

    Args:
        country_code: Country code (KR, US, JP, DE, FR, etc.)
        limit: Number of results

    Returns:
        List of radio stations
    """
    all_results = []
    seen_urls = set()

    # 1. DB에서 검색 (검증된 방송)
    db_results = db_search_country(country_code, limit)
    for r in db_results:
        if r["url"] not in seen_urls:
            seen_urls.add(r["url"])
            r["source"] = "db"
            all_results.append(r)

    # 2. Radio Browser API (최신 결과)
    code = urllib.parse.quote(country_code.upper())
    api_results = api_get(f"stations/bycountrycodeexact/{code}", {
        "limit": limit,
        "order": "clickcount",
        "reverse": "true",
        "lastcheckok": 1
    })

    # API 결과 병합
    for s in api_results:
        url = s.get("url_resolved") or s.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            station = format_station(s)
            station["source"] = "api"
            all_results.append(station)
            # 정상적인 방송만 DB에 저장
            if is_valid_station(s):
                add_station_to_db(s)

    all_results.sort(key=lambda x: x.get("votes", 0), reverse=True)
    return all_results[:limit]


@mcp.tool()
def get_popular(limit: int = 20) -> list[dict]:
    """
    Get popular radio stations from local DB.

    Args:
        limit: Number of results

    Returns:
        List of popular stations
    """
    # 1. DB에서 가져오기
    results = db_get_popular(limit)

    # 2. API fallback
    if not results:
        api_results = api_get(f"stations/topclick/{limit}")
        results = [format_station(s) for s in api_results]

    return results


@mcp.tool()
def play(url: str, name: str = "") -> dict:
    """
    Play a radio station.

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

        # 잠시 대기 후 프로세스 확인
        time.sleep(1)
        if player_proc.poll() is not None:
            # 재생 실패 - DB에 기록
            mark_station_dead(url)
            return {"status": "error", "message": "Stream failed to start"}

        current_station = {"name": name, "url": url}
        return {"status": "playing", "name": name, "url": url}
    except Exception as e:
        mark_station_dead(url)
        return {"status": "error", "message": str(e)}


@mcp.tool()
def stop() -> dict:
    """
    Stop radio playback.

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
    Get current song info.

    Returns:
        Current song info (title, artist)
    """
    if not current_station:
        return {"status": "not_playing"}

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect(MPV_SOCKET)

        sock.send(b'{"command": ["get_property", "media-title"]}\n')
        response = sock.recv(4096).decode()
        sock.close()

        data = json.loads(response)
        title = data.get("data", "")

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
    """Get favorite stations list."""
    return load_json(FAVORITES_FILE)


@mcp.tool()
def add_favorite(station: dict) -> dict:
    """Add station to favorites."""
    favorites = load_json(FAVORITES_FILE)

    for fav in favorites:
        if fav.get("url") == station.get("url"):
            return {"status": "already_exists", "name": station.get("name")}

    favorites.append(station)
    save_json(FAVORITES_FILE, favorites)
    return {"status": "added", "name": station.get("name")}


@mcp.tool()
def remove_favorite(index: int) -> dict:
    """Remove station from favorites by index (0-based)."""
    favorites = load_json(FAVORITES_FILE)

    if 0 <= index < len(favorites):
        removed = favorites.pop(index)
        save_json(FAVORITES_FILE, favorites)
        return {"status": "removed", "name": removed.get("name")}

    return {"status": "error", "message": "Invalid index"}


@mcp.tool()
def get_history(limit: int = 20) -> list[dict]:
    """Get listening history."""
    history = load_json(HISTORY_FILE)
    return history[-limit:][::-1]


@mcp.tool()
def recommend(mood: str = "relaxing") -> list[dict]:
    """
    Get mood-based recommendations.

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
    seen = set()

    for tag in tags[:2]:
        # DB 검색
        db_results = db_search(tag, "tags", 15)
        for r in db_results:
            if r["url"] not in seen:
                seen.add(r["url"])
                r["source"] = "db"
                all_results.append(r)

        # API 검색
        encoded_tag = urllib.parse.quote(tag)
        api_results = api_get(f"stations/bytag/{encoded_tag}", {
            "limit": 15,
            "order": "votes",
            "reverse": "true",
            "lastcheckok": 1
        })
        for s in api_results:
            url = s.get("url_resolved") or s.get("url", "")
            if url and url not in seen:
                seen.add(url)
                station = format_station(s)
                station["source"] = "api"
                all_results.append(station)

    all_results.sort(key=lambda x: x.get("votes", 0), reverse=True)
    return all_results[:20]


@mcp.tool()
def get_db_stats() -> dict:
    """
    Get database statistics.

    Returns:
        DB stats (total stations, alive, dead, etc.)
    """
    db = get_db()
    if not db:
        return {"status": "no_db"}

    try:
        cursor = db.cursor()

        cursor.execute("SELECT COUNT(*) FROM stations")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM stations WHERE is_alive = 1")
        alive = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM stations WHERE is_alive = 0")
        dead = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT countrycode) FROM stations")
        countries = cursor.fetchone()[0]

        return {
            "total": total,
            "alive": alive,
            "dead": dead,
            "unknown": total - alive - dead,
            "countries": countries,
            "db_path": [p for p in DB_PATHS if os.path.exists(p)][0] if any(os.path.exists(p) for p in DB_PATHS) else None
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def purge_dead() -> dict:
    """
    Delete all dead stations from database.

    Returns:
        Number of deleted stations
    """
    db = get_db()
    if not db:
        return {"status": "no_db"}

    try:
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM stations WHERE is_alive = 0")
        count = cursor.fetchone()[0]

        cursor.execute("DELETE FROM stations WHERE is_alive = 0")
        db.commit()

        return {"status": "success", "deleted": count}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def health_check(limit: int = 100) -> dict:
    """
    Check health of stations by testing URLs.
    Updates is_alive status in database.

    Args:
        limit: Number of stations to check (default 100)

    Returns:
        Health check results
    """
    db = get_db()
    if not db:
        return {"status": "no_db"}

    try:
        cursor = db.cursor()
        # 오래된 검증 또는 미검증 방송 우선
        cursor.execute("""
            SELECT stationuuid, name, url, url_resolved
            FROM stations
            WHERE is_alive = 1 OR is_alive IS NULL
            ORDER BY last_checked_at ASC NULLS FIRST
            LIMIT ?
        """, (limit,))

        stations = cursor.fetchall()
        alive = 0
        dead = 0

        for s in stations:
            url = s[3] or s[2]  # url_resolved or url
            try:
                req = urllib.request.Request(url, method='HEAD',
                    headers={"User-Agent": "RadioMCP/1.0"})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    if resp.status < 400:
                        cursor.execute("""
                            UPDATE stations SET is_alive = 1, fail_count = 0,
                                last_checked_at = ? WHERE stationuuid = ?
                        """, (datetime.now().isoformat(), s[0]))
                        alive += 1
                    else:
                        raise Exception("Bad status")
            except:
                cursor.execute("""
                    UPDATE stations SET is_alive = 0,
                        fail_count = COALESCE(fail_count, 0) + 1,
                        last_checked_at = ? WHERE stationuuid = ?
                """, (datetime.now().isoformat(), s[0]))
                dead += 1

        db.commit()
        return {"checked": len(stations), "alive": alive, "dead": dead}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def sync_with_api(country_code: str = None, tag: str = None, limit: int = 100) -> dict:
    """
    Sync database with Radio Browser API.
    Fetches new/updated stations and compares with local DB.

    Args:
        country_code: Filter by country (optional)
        tag: Filter by tag/genre (optional)
        limit: Max stations to fetch (default 100)

    Returns:
        Sync results (new, updated, unchanged)
    """
    db = get_db()
    if not db:
        return {"status": "no_db"}

    # API에서 가져오기
    if country_code:
        code = urllib.parse.quote(country_code.upper())
        api_results = api_get(f"stations/bycountrycodeexact/{code}", {
            "limit": limit, "order": "clickcount", "reverse": "true", "lastcheckok": 1
        })
    elif tag:
        encoded_tag = urllib.parse.quote(tag)
        api_results = api_get(f"stations/bytag/{encoded_tag}", {
            "limit": limit, "order": "clickcount", "reverse": "true", "lastcheckok": 1
        })
    else:
        api_results = api_get(f"stations/topclick/{limit}")

    if not api_results:
        return {"status": "error", "message": "API returned no results"}

    try:
        cursor = db.cursor()
        new_count = 0
        updated = 0
        skipped = 0

        for s in api_results:
            uuid = s.get("stationuuid", "")
            url = s.get("url_resolved") or s.get("url", "")

            # 유효성 검사
            if not is_valid_station(s):
                skipped += 1
                continue

            # DB에 있는지 확인
            cursor.execute("SELECT stationuuid, url_resolved FROM stations WHERE stationuuid = ?", (uuid,))
            existing = cursor.fetchone()

            if not existing:
                # 신규 추가
                add_station_to_db(s)
                new_count += 1
            elif existing[1] != url:
                # URL 변경됨 - 업데이트
                cursor.execute("""
                    UPDATE stations SET url = ?, url_resolved = ?,
                        is_alive = 1, last_checked_at = ?
                    WHERE stationuuid = ?
                """, (s.get("url"), url, datetime.now().isoformat(), uuid))
                updated += 1

        db.commit()
        return {
            "status": "success",
            "fetched": len(api_results),
            "new": new_count,
            "updated": updated,
            "skipped": skipped
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def set_sleep_timer(minutes: int) -> dict:
    """
    Set sleep timer to stop radio after specified minutes.

    Args:
        minutes: Minutes until auto-stop (0 to cancel)

    Returns:
        Timer status
    """
    global sleep_timer
    import threading

    # 기존 타이머 취소
    if sleep_timer:
        sleep_timer.cancel()
        sleep_timer = None

    if minutes <= 0:
        return {"status": "cancelled"}

    def auto_stop():
        global sleep_timer
        stop()
        sleep_timer = None
        print(f"Sleep timer: stopped after {minutes} minutes", flush=True)

    sleep_timer = threading.Timer(minutes * 60, auto_stop)
    sleep_timer.start()

    return {"status": "set", "minutes": minutes, "stop_at": (datetime.now() + __import__('datetime').timedelta(minutes=minutes)).strftime("%H:%M")}


@mcp.tool()
def set_alarm(hour: int, minute: int = 0, station_query: str = "pop") -> dict:
    """
    Set alarm to start playing radio at specified time.

    Args:
        hour: Hour (0-23)
        minute: Minute (0-59)
        station_query: What to play (default "pop")

    Returns:
        Alarm status
    """
    import threading
    from datetime import timedelta

    now = datetime.now()
    alarm_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # 이미 지난 시간이면 내일로
    if alarm_time <= now:
        alarm_time += timedelta(days=1)

    delay = (alarm_time - now).total_seconds()

    def alarm_play():
        stations = search(station_query, 5)
        if stations:
            s = stations[0]
            play(s["url"], s["name"])
            print(f"Alarm: playing {s['name']}", flush=True)

    timer = threading.Timer(delay, alarm_play)
    timer.start()

    return {
        "status": "set",
        "alarm_time": alarm_time.strftime("%Y-%m-%d %H:%M"),
        "station_query": station_query,
        "delay_minutes": int(delay / 60)
    }


@mcp.tool()
def set_volume(level: int) -> dict:
    """
    Set playback volume.

    Args:
        level: Volume level (0-100)

    Returns:
        Volume status
    """
    level = max(0, min(100, level))

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect(MPV_SOCKET)
        sock.send(f'{{"command": ["set_property", "volume", {level}]}}\n'.encode())
        sock.close()
        return {"status": "success", "volume": level}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def get_volume() -> dict:
    """
    Get current volume level.

    Returns:
        Current volume
    """
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect(MPV_SOCKET)
        sock.send(b'{"command": ["get_property", "volume"]}\n')
        response = sock.recv(4096).decode()
        sock.close()
        data = json.loads(response)
        return {"volume": int(data.get("data", 100))}
    except:
        return {"volume": 100, "error": "Could not get volume"}


@mcp.tool()
def similar_stations(limit: int = 10) -> list[dict]:
    """
    Find similar stations based on currently playing station's tags.

    Args:
        limit: Number of results

    Returns:
        List of similar stations
    """
    if not current_station:
        return []

    # 현재 방송국의 태그 가져오기
    db = get_db()
    if db:
        cursor = db.cursor()
        cursor.execute("SELECT tags FROM stations WHERE url = ? OR url_resolved = ?",
                      (current_station.get("url"), current_station.get("url")))
        row = cursor.fetchone()
        if row and row[0]:
            tags = row[0].split(",")
            if tags:
                # 첫 번째 태그로 검색
                main_tag = tags[0].strip()
                results = search(main_tag, limit + 1)
                # 현재 방송국 제외
                return [r for r in results if r["url"] != current_station.get("url")][:limit]

    return []


@mcp.tool()
def recommend_by_weather(city: str = "Seoul") -> list[dict]:
    """
    Recommend stations based on current weather.

    Args:
        city: City name for weather (default Seoul)

    Returns:
        Weather-based recommendations
    """
    # wttr.in 무료 API
    try:
        url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "RadioMCP/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        current = data.get("current_condition", [{}])[0]
        weather_code = int(current.get("weatherCode", 113))
        temp = int(current.get("temp_C", 20))

        # 날씨 코드 → 분위기
        if weather_code in [176, 263, 266, 293, 296, 299, 302, 305, 308, 311, 314, 317, 320, 353, 356, 359]:
            # 비
            mood = "rainy"
        elif weather_code in [179, 182, 185, 227, 230, 323, 326, 329, 332, 335, 338, 350, 362, 365, 368, 371, 374, 377, 392, 395]:
            # 눈
            mood = "snowy"
        elif weather_code in [113]:
            # 맑음
            mood = "sunny" if temp > 20 else "cold"
        else:
            mood = "cloudy"

        # 온도 기반 조정
        if temp > 28:
            mood = "hot"
        elif temp < 5:
            mood = "cold"

        tags = WEATHER_TAGS.get(mood, ["pop", "jazz"])

        # 검색
        all_results = []
        seen = set()
        for tag in tags[:2]:
            results = search(tag, 10)
            for r in results:
                if r["url"] not in seen:
                    seen.add(r["url"])
                    all_results.append(r)

        return {
            "city": city,
            "weather": mood,
            "temp_c": temp,
            "stations": all_results[:10]
        }
    except Exception as e:
        return {"error": str(e), "stations": []}


@mcp.tool()
def recommend_by_time() -> list[dict]:
    """
    Recommend stations based on current time of day.

    Returns:
        Time-based recommendations
    """
    time_of_day = get_time_of_day()
    tags = TIME_TAGS.get(time_of_day, ["pop"])

    all_results = []
    seen = set()
    for tag in tags[:2]:
        results = search(tag, 10)
        for r in results:
            if r["url"] not in seen:
                seen.add(r["url"])
                all_results.append(r)

    return {
        "time_of_day": time_of_day,
        "hour": datetime.now().hour,
        "stations": all_results[:10]
    }


if __name__ == "__main__":
    mcp.run()
