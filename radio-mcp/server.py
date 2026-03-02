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
import shutil
import atexit
import signal
import threading
from typing import Any
from datetime import datetime

from mcp.server.fastmcp import FastMCP

# MCP 서버 생성
mcp = FastMCP("radio")

# 설정
DATA_DIR = os.path.expanduser("~/.radiocli")
FAVORITES_FILE = os.path.join(DATA_DIR, "favorites.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
RECOGNIZED_FILE = os.path.join(DATA_DIR, "recognized_songs.json")
RECORD_FILE = os.path.join(DATA_DIR, "record.mp3")
MPV_SOCKET = os.path.join(DATA_DIR, "mpv.sock")
API_BASE = "https://de1.api.radio-browser.info/json"
ACOUSTID_API_KEY = os.environ.get("ACOUSTID_API_KEY", "vQEDUkpM7e")

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

LAST_STATION_FILE = os.path.join(DATA_DIR, "last_station.json")

def save_last_station():
    """마지막 재생 방송 저장"""
    if current_station:
        try:
            with open(LAST_STATION_FILE, "w", encoding="utf-8") as f:
                json.dump(current_station, f, ensure_ascii=False)
        except:
            pass

def load_last_station():
    """마지막 재생 방송 로드"""
    if os.path.exists(LAST_STATION_FILE):
        try:
            with open(LAST_STATION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return None

def cleanup():
    """종료 시 플레이어 정리"""
    global player_proc
    # 마지막 방송 저장
    save_last_station()
    if player_proc:
        try:
            player_proc.terminate()
            player_proc.wait(timeout=2)
        except:
            try:
                player_proc.kill()
            except:
                pass
        player_proc = None
    # mpv 소켓 정리
    if os.path.exists(MPV_SOCKET):
        try:
            os.remove(MPV_SOCKET)
        except:
            pass

# 종료 핸들러 등록
atexit.register(cleanup)
signal.signal(signal.SIGTERM, lambda s, f: (cleanup(), exit(0)))
signal.signal(signal.SIGINT, lambda s, f: (cleanup(), exit(0)))

# Watchdog: 부모 프로세스 종료 감지 (SIGKILL 대비)
def start_watchdog():
    """부모 프로세스 종료 시 mpv도 종료"""
    parent_pid = os.getppid()
    def watch():
        while True:
            time.sleep(3)
            # 부모 PID가 변경되면 (보통 1로) 부모가 죽은 것
            if os.getppid() != parent_pid:
                cleanup()
                os._exit(0)
    t = threading.Thread(target=watch, daemon=True)
    t.start()

start_watchdog()

# 유사어 매핑 (태그 확장)
TAG_SYNONYMS = {
    "lounge": ["lounge", "chillout", "cafe", "ambient", "easy listening"],
    "jazz": ["jazz", "smooth jazz", "jazz lounge", "bossa nova", "bebop", "swing", "fusion"],
    "classical": ["classical", "classic", "orchestra", "symphony", "piano", "chamber"],
    "rock": ["rock", "classic rock", "hard rock", "alternative", "indie rock"],
    "pop": ["pop", "top 40", "hits", "chart", "mainstream"],
    "electronic": ["electronic", "edm", "dance", "house", "techno", "trance", "dubstep"],
    "ambient": ["ambient", "chillout", "relaxing", "meditation", "sleep", "drone"],
    "hiphop": ["hiphop", "hip-hop", "hip hop", "rap", "r&b", "rnb", "trap"],
    "bossa nova": ["bossa nova", "bossa", "brazilian", "latin jazz", "mpb"],
    "chillout": ["chillout", "chill", "lounge", "ambient", "downtempo"],
    "cafe": ["cafe", "coffee", "lounge", "acoustic", "bossa nova"],
    "sleep": ["sleep", "ambient", "relaxing", "meditation", "nature", "calm"],
    "focus": ["focus", "study", "concentration", "instrumental", "classical", "lo-fi", "lofi"],
    "workout": ["workout", "gym", "exercise", "dance", "electronic", "energetic"],
    "morning": ["morning", "wake up", "breakfast", "pop", "acoustic"],
    "night": ["night", "late night", "jazz", "lounge", "ambient"],
    "rain": ["rain", "nature", "ambient", "relaxing", "piano"],
    "summer": ["summer", "tropical", "beach", "latin", "reggae"],
    "winter": ["winter", "christmas", "cozy", "acoustic", "classical"],
    "blues": ["blues", "soul", "r&b", "rhythm and blues"],
    "country": ["country", "americana", "folk", "bluegrass"],
    "metal": ["metal", "heavy metal", "death metal", "black metal", "thrash"],
    "reggae": ["reggae", "ska", "dub", "dancehall", "roots"],
    "soul": ["soul", "r&b", "motown", "funk", "neo soul"],
    "folk": ["folk", "acoustic", "singer-songwriter", "americana"],
    "latin": ["latin", "salsa", "merengue", "bachata", "cumbia", "reggaeton"],
    "world": ["world", "world music", "ethnic", "traditional", "folk"],
    "news": ["news", "talk", "information", "current affairs", "spoken"],
    "kpop": ["kpop", "k-pop", "korean pop", "korean"],
    "jpop": ["jpop", "j-pop", "japanese pop", "japanese"],
    "anime": ["anime", "japanese", "soundtrack", "ost"],
}

# ============================================================
# 다국어 검색 매핑 (v2.0)
# ============================================================

# 다국어 → 영어 태그 매핑
LANG_MAP = {
    # 한국어
    "재즈": "jazz", "클래식": "classical", "록": "rock", "팝": "pop",
    "뉴스": "news", "힙합": "hip hop", "발라드": "ballad", "국악": "korean traditional",
    "트로트": "trot", "인디": "indie", "라운지": "lounge", "앰비언트": "ambient",
    "일렉트로닉": "electronic", "보사노바": "bossa nova", "케이팝": "kpop",
    "가요": "kpop", "한국": "korean", "클럽": "club", "댄스": "dance",
    "알앤비": "r&b", "소울": "soul", "블루스": "blues", "컨트리": "country",
    "메탈": "metal", "펑크": "punk", "레게": "reggae", "포크": "folk",
    "어쿠스틱": "acoustic", "피아노": "piano", "수면": "sleep", "명상": "meditation",
    "집중": "focus", "공부": "study", "운동": "workout", "카페": "cafe",
    "아침": "morning", "저녁": "evening", "밤": "night", "크리스마스": "christmas",
    "여름": "summer", "겨울": "winter", "비": "rain", "자연": "nature",
    "클래시컬": "classical", "오케스트라": "orchestra", "교향곡": "symphony",
    "오페라": "opera", "뮤지컬": "musical", "영화음악": "soundtrack",
    "게임음악": "game", "애니메이션": "anime", "동요": "children",
    "종교": "religious", "찬송가": "gospel", "불교": "buddhist",

    # 일본어
    "ジャズ": "jazz", "クラシック": "classical", "ロック": "rock", "ポップ": "pop",
    "ニュース": "news", "ヒップホップ": "hip hop", "演歌": "enka",
    "アニメ": "anime", "Jポップ": "jpop", "邦楽": "japanese",
    "洋楽": "western", "ラウンジ": "lounge", "アンビエント": "ambient",
    "エレクトロニック": "electronic", "ボサノバ": "bossa nova",
    "カフェ": "cafe", "睡眠": "sleep", "瞑想": "meditation", "勉強": "study",
    "朝": "morning", "夜": "night", "夏": "summer", "冬": "winter",
    "ソウル": "soul", "ブルース": "blues", "レゲエ": "reggae",
    "フォーク": "folk", "メタル": "metal", "パンク": "punk",
    "ゲーム": "game", "映画": "soundtrack", "童謡": "children",

    # 중국어 (간체)
    "爵士乐": "jazz", "爵士": "jazz", "古典音乐": "classical", "古典": "classical",
    "摇滚": "rock", "流行": "pop", "新闻": "news", "嘻哈": "hip hop",
    "电子": "electronic", "电子音乐": "electronic", "舞曲": "dance",
    "轻音乐": "easy listening", "休闲": "lounge", "咖啡": "cafe",
    "睡眠": "sleep", "冥想": "meditation", "学习": "study", "工作": "focus",
    "早晨": "morning", "夜晚": "night", "夏天": "summer", "冬天": "winter",
    "灵魂乐": "soul", "蓝调": "blues", "雷鬼": "reggae", "民谣": "folk",
    "金属": "metal", "朋克": "punk", "动漫": "anime", "游戏": "game",
    "华语": "chinese", "粤语": "cantonese", "国语": "mandarin",

    # 중국어 (번체)
    "爵士樂": "jazz", "古典音樂": "classical", "搖滾": "rock", "流行音樂": "pop",
    "電子音樂": "electronic", "輕音樂": "easy listening",

    # 스페인어
    "música clásica": "classical", "música pop": "pop", "música rock": "rock",
    "noticias": "news", "jazz latino": "latin jazz", "salsa": "salsa",
    "reggaeton": "reggaeton", "bachata": "bachata", "merengue": "merengue",
    "cumbia": "cumbia", "flamenco": "flamenco", "latina": "latin",
    "relajante": "relaxing", "dormir": "sleep", "estudiar": "study",

    # 독일어
    "klassische musik": "classical", "nachrichten": "news", "schlager": "schlager",
    "volksmusik": "folk", "deutsche musik": "german",

    # 프랑스어
    "musique classique": "classical", "musique pop": "pop", "actualités": "news",
    "chanson française": "chanson", "musique française": "french",

    # 포르투갈어
    "música brasileira": "brazilian", "samba": "samba", "forró": "forro",
    "sertanejo": "sertanejo", "mpb": "mpb", "axé": "axe",

    # 러시아어
    "джаз": "jazz", "классика": "classical", "рок": "rock", "поп": "pop",
    "новости": "news", "электронная": "electronic", "русская": "russian",

    # 아랍어
    "جاز": "jazz", "كلاسيكي": "classical", "أخبار": "news",
    "موسيقى عربية": "arabic", "عربي": "arabic",

    # 힌디어
    "जैज़": "jazz", "शास्त्रीय": "classical", "समाचार": "news",
    "बॉलीवुड": "bollywood", "हिंदी": "hindi",

    # 베트남어
    "nhạc jazz": "jazz", "nhạc cổ điển": "classical", "tin tức": "news",
    "nhạc việt": "vietnamese", "nhạc trẻ": "vpop",

    # 태국어
    "แจ๊ส": "jazz", "คลาสสิก": "classical", "ข่าว": "news",
    "เพลงไทย": "thai", "ลูกทุ่ง": "luk thung",

    # 인도네시아어
    "berita": "news", "musik indonesia": "indonesian", "dangdut": "dangdut",
}

# 복합 장르 (토큰 병합용)
COMPOUND_GENRES = {
    ("bossa", "nova"): "bossa nova",
    ("hip", "hop"): "hip hop",
    ("smooth", "jazz"): "smooth jazz",
    ("deep", "house"): "deep house",
    ("classic", "rock"): "classic rock",
    ("hard", "rock"): "hard rock",
    ("heavy", "metal"): "heavy metal",
    ("death", "metal"): "death metal",
    ("neo", "soul"): "neo soul",
    ("lo", "fi"): "lo-fi",
    ("easy", "listening"): "easy listening",
    ("world", "music"): "world music",
    ("new", "age"): "new age",
    ("drum", "bass"): "drum and bass",
    ("drum", "n", "bass"): "drum and bass",
    ("r", "b"): "r&b",
    ("rhythm", "blues"): "rhythm and blues",
    ("k", "pop"): "kpop",
    ("j", "pop"): "jpop",
    ("top", "40"): "top 40",
    ("old", "school"): "old school",
    ("latin", "jazz"): "latin jazz",
    ("acid", "jazz"): "acid jazz",
    ("nu", "jazz"): "nu jazz",
}

# 알려진 태그 목록 (퍼지 검색용)
KNOWN_TAGS = [
    "jazz", "classical", "rock", "pop", "electronic", "ambient", "lounge",
    "chillout", "hip hop", "r&b", "soul", "blues", "country", "folk",
    "latin", "reggae", "bossa nova", "indie", "alternative", "metal",
    "punk", "edm", "techno", "house", "trance", "dubstep", "acoustic",
    "piano", "instrumental", "meditation", "sleep", "news", "talk",
    "kpop", "jpop", "anime", "enka", "trot", "world music", "folk",
    "gospel", "christian", "religious", "christmas", "soundtrack",
    "80s", "90s", "70s", "60s", "oldies", "retro", "disco", "funk",
    "smooth jazz", "acid jazz", "nu jazz", "fusion", "bebop", "swing",
    "lo-fi", "lofi", "study", "focus", "workout", "gym", "morning",
    "night", "cafe", "coffee", "dinner", "romantic", "relax", "chill",
    "dance", "club", "party", "summer", "tropical", "beach", "nature",
    "rain", "spa", "yoga", "new age", "deep house", "progressive",
    "drum and bass", "breakbeat", "downtempo", "trip hop", "shoegaze",
    "post rock", "math rock", "grunge", "emo", "hardcore", "ska",
    "dub", "dancehall", "roots", "afrobeat", "highlife", "afropop",
    "flamenco", "fado", "celtic", "irish", "scottish", "french",
    "german", "italian", "spanish", "brazilian", "mexican", "cuban",
    "korean", "japanese", "chinese", "arabic", "indian", "bollywood",
    "turkish", "greek", "russian", "polish", "czech", "hungarian",
]

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


# ============================================================
# 검색 엔진 헬퍼 함수 (v2.0)
# ============================================================

def translate_query(query: str) -> str:
    """다국어 쿼리를 영어 태그로 변환"""
    query_lower = query.lower().strip()

    # 1. 정확한 매핑 체크
    if query in LANG_MAP:
        return LANG_MAP[query]
    if query_lower in LANG_MAP:
        return LANG_MAP[query_lower]

    # 2. 각 단어별 변환
    words = query.split()
    translated = []
    for word in words:
        if word in LANG_MAP:
            translated.append(LANG_MAP[word])
        elif word.lower() in LANG_MAP:
            translated.append(LANG_MAP[word.lower()])
        else:
            translated.append(word)

    return " ".join(translated)


def levenshtein_distance(s1: str, s2: str) -> int:
    """두 문자열 간 편집 거리 계산"""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def fuzzy_match(query: str, threshold: int = 2) -> str:
    """오타 교정 - 가장 가까운 알려진 태그 반환"""
    query_lower = query.lower().strip()

    # 정확히 일치하면 그대로 반환
    if query_lower in KNOWN_TAGS:
        return query_lower

    # 너무 짧은 단어(3자 미만)는 퍼지 매칭 안 함 (fm → edm 방지)
    if len(query_lower) < 3:
        return query_lower

    # 라디오 관련 일반 단어는 퍼지 매칭 제외
    SKIP_WORDS = {"radio", "fm", "am", "hd", "the", "and", "or", "with"}
    if query_lower in SKIP_WORDS:
        return query_lower

    # 가장 가까운 태그 찾기
    best_match = None
    best_distance = threshold + 1

    for tag in KNOWN_TAGS:
        # 너무 짧거나 긴 태그는 스킵
        if abs(len(tag) - len(query_lower)) > threshold:
            continue

        distance = levenshtein_distance(query_lower, tag)
        if distance < best_distance:
            best_distance = distance
            best_match = tag

    return best_match if best_match else query_lower


def merge_compound_tokens(tokens: list) -> list:
    """토큰 리스트에서 복합 장르 병합"""
    if len(tokens) < 2:
        return tokens

    result = []
    i = 0
    while i < len(tokens):
        merged = False

        # 3단어 조합 체크
        if i + 2 < len(tokens):
            key3 = (tokens[i], tokens[i+1], tokens[i+2])
            if key3 in COMPOUND_GENRES:
                result.append(COMPOUND_GENRES[key3])
                i += 3
                merged = True
                continue

        # 2단어 조합 체크
        if i + 1 < len(tokens):
            key2 = (tokens[i], tokens[i+1])
            if key2 in COMPOUND_GENRES:
                result.append(COMPOUND_GENRES[key2])
                i += 2
                merged = True
                continue

        if not merged:
            result.append(tokens[i])
            i += 1

    return result


def parse_search_query(query: str) -> dict:
    """
    검색 쿼리 파싱 (연산자 지원)

    지원 연산자:
    - AND: 기본 (공백)
    - OR: '|' 또는 'OR'
    - NOT: '-' 접두사
    - "exact": 따옴표로 정확한 구문

    Returns:
        {
            "must": [...],      # AND 조건 (모두 포함)
            "should": [...],    # OR 조건 (하나 이상)
            "must_not": [...],  # NOT 조건 (제외)
            "exact": [...],     # 정확한 구문
        }
    """
    result = {
        "must": [],
        "should": [],
        "must_not": [],
        "exact": [],
    }

    # 따옴표로 둘러싸인 정확한 구문 추출
    import re
    exact_matches = re.findall(r'"([^"]+)"', query)
    for match in exact_matches:
        result["exact"].append(match.lower())
    query = re.sub(r'"[^"]+"', '', query)

    # OR로 분리
    if ' OR ' in query or '|' in query:
        query = query.replace(' OR ', '|')
        or_parts = [p.strip() for p in query.split('|') if p.strip()]
        for part in or_parts:
            if part.startswith('-'):
                result["must_not"].append(part[1:].lower())
            else:
                result["should"].append(part.lower())
    else:
        # 공백으로 분리 (AND)
        tokens = query.split()
        for token in tokens:
            token = token.strip()
            if not token:
                continue
            if token.startswith('-'):
                result["must_not"].append(token[1:].lower())
            else:
                result["must"].append(token.lower())

    return result


def score_station(station: dict, query_parts: dict, matched_tags: set) -> float:
    """방송국 점수 계산"""
    score = 0.0

    # 기본 인기도 점수 (로그 스케일)
    import math
    votes = station.get("votes", 0)
    if votes > 0:
        score += math.log10(votes + 1)

    # 비트레이트 보너스
    bitrate = station.get("bitrate", 0)
    if bitrate >= 320:
        score += 3
    elif bitrate >= 256:
        score += 2
    elif bitrate >= 192:
        score += 1

    # 매칭 태그 수 보너스
    station_tags = station.get("tags", "").lower()
    match_count = sum(1 for tag in matched_tags if tag in station_tags)
    score += match_count * 2

    # 정확한 구문 매칭 보너스
    for exact in query_parts.get("exact", []):
        if exact in station_tags or exact in station.get("name", "").lower():
            score += 5

    # must_not 페널티
    for exclude in query_parts.get("must_not", []):
        if exclude in station_tags:
            score -= 100  # 사실상 제외

    return score


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


# ============================================================
# 메모리 인덱스 (초고속 검색)
# ============================================================

# 전역 인덱스
_stations_cache = None      # 전체 방송국 리스트
_tag_index = None           # {tag: [indices...]}
_name_words_index = None    # {word: [indices...]}


def build_memory_index():
    """DB를 메모리에 로드하고 인덱스 구축 (최초 1회)"""
    global _stations_cache, _tag_index, _name_words_index

    if _stations_cache is not None:
        return  # 이미 로드됨

    db = get_db()
    if not db:
        _stations_cache = []
        _tag_index = {}
        _name_words_index = {}
        return

    try:
        cursor = db.cursor()
        cursor.execute("""
            SELECT * FROM stations
            WHERE is_alive = 1 OR is_alive IS NULL
            ORDER BY clickcount DESC
        """)
        rows = cursor.fetchall()

        _stations_cache = format_stations(rows)
        _tag_index = {}
        _name_words_index = {}

        for idx, station in enumerate(_stations_cache):
            # 태그 인덱스
            tags = station.get("tags", "").lower()
            for tag in tags.split(","):
                tag = tag.strip()
                if tag:
                    if tag not in _tag_index:
                        _tag_index[tag] = []
                    _tag_index[tag].append(idx)

            # 이름 단어 인덱스
            name = station.get("name", "").lower()
            for word in name.split():
                word = word.strip()
                if len(word) >= 2:
                    if word not in _name_words_index:
                        _name_words_index[word] = []
                    _name_words_index[word].append(idx)

        print(f"Memory index built: {len(_stations_cache)} stations, {len(_tag_index)} tags", flush=True)
    except Exception as e:
        print(f"Index build error: {e}", flush=True)
        _stations_cache = []
        _tag_index = {}
        _name_words_index = {}


def fast_search_by_name(query: str, limit: int = 20) -> list:
    """이름으로 초고속 검색"""
    build_memory_index()

    if not _stations_cache:
        return []

    query_lower = query.lower()
    query_words = query_lower.split()

    # 1. 정확한 이름 매칭
    exact_matches = []
    partial_matches = []

    for idx, station in enumerate(_stations_cache):
        name_lower = station.get("name", "").lower()

        # 전체 쿼리가 이름에 포함
        if query_lower in name_lower:
            exact_matches.append(idx)
        # 모든 단어가 이름에 포함
        elif all(w in name_lower for w in query_words):
            partial_matches.append(idx)

    result_indices = (exact_matches + partial_matches)[:limit]
    return [_stations_cache[i] for i in result_indices]


def fast_search_by_tag(tags: list, limit: int = 20) -> list:
    """태그로 초고속 검색"""
    build_memory_index()

    if not _stations_cache or not _tag_index:
        return []

    # 각 태그에 매칭되는 인덱스 수집
    all_indices = set()
    for tag in tags:
        tag_lower = tag.lower()
        # 정확 매칭
        if tag_lower in _tag_index:
            all_indices.update(_tag_index[tag_lower])
        # 부분 매칭 (태그에 단어 포함)
        else:
            for idx_tag, indices in _tag_index.items():
                if tag_lower in idx_tag or idx_tag in tag_lower:
                    all_indices.update(indices[:50])  # 부분 매칭은 제한

    # votes 기준 정렬 (이미 정렬된 상태라 인덱스 순으로 가져오면 됨)
    sorted_indices = sorted(all_indices)[:limit]
    return [_stations_cache[i] for i in sorted_indices]


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


def get_fresh_url(name: str) -> str:
    """API에서 방송 이름으로 최신 URL 가져오기 (토큰 만료 대응)"""
    if not name:
        return ""
    encoded = urllib.parse.quote(name)
    results = api_get(f"stations/byname/{encoded}", {
        "limit": 5, "order": "clickcount", "reverse": "true", "lastcheckok": 1
    })
    # 정확히 일치하는 것 먼저
    for s in results:
        if s.get("name", "").lower() == name.lower():
            return s.get("url_resolved") or s.get("url", "")
    # 없으면 첫번째 결과
    if results:
        return results[0].get("url_resolved") or results[0].get("url", "")
    return ""


# 영구 차단 목록
BLOCK_LIST = ["평양", "pyongyang", "north korea", "dprk", "조선중앙"]

def is_blocked(name: str) -> bool:
    """차단 목록 확인"""
    if not name:
        return False
    name_lower = name.lower()
    return any(b.lower() in name_lower for b in BLOCK_LIST)


def format_station(s) -> dict:
    """방송국 정보 포맷 (dict 또는 sqlite Row). 차단이면 None"""
    if isinstance(s, sqlite3.Row):
        s = dict(s)
    name = s.get("name", "Unknown")
    if is_blocked(name):
        return None
    return {
        "id": s.get("stationuuid", ""),
        "name": name,
        "url": s.get("url_resolved") or s.get("url", ""),
        "country": s.get("country", ""),
        "countrycode": s.get("countrycode", ""),
        "tags": s.get("tags", ""),
        "bitrate": s.get("bitrate", 0),
        "votes": s.get("votes", 0),
    }


def format_stations(items) -> list:
    """여러 방송국 포맷 (차단 필터링)"""
    return [s for s in (format_station(x) for x in items) if s]


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
        return format_stations(cursor.fetchall())
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
        return format_stations(cursor.fetchall())
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
        return format_stations(cursor.fetchall())
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


def db_advanced_search(
    tags: list = None,
    country: str = None,
    language: str = None,
    min_bitrate: int = 0,
    codec: str = None,
    limit: int = 50
) -> list:
    """DB에서 복합 필터 검색"""
    db = get_db()
    if not db:
        return []

    try:
        cursor = db.cursor()
        conditions = ["(is_alive = 1 OR is_alive IS NULL)"]
        params = []

        # 태그 필터 (OR)
        if tags:
            tag_conditions = []
            for tag in tags:
                tag_conditions.append("tags LIKE ?")
                params.append(f"%{tag}%")
            conditions.append(f"({' OR '.join(tag_conditions)})")

        # 국가 필터
        if country:
            conditions.append("countrycode = ?")
            params.append(country.upper())

        # 언어 필터
        if language:
            conditions.append("language LIKE ?")
            params.append(f"%{language}%")

        # 비트레이트 필터
        if min_bitrate > 0:
            conditions.append("bitrate >= ?")
            params.append(min_bitrate)

        # 코덱 필터
        if codec:
            conditions.append("codec LIKE ?")
            params.append(f"%{codec}%")

        sql = f"""
            SELECT * FROM stations
            WHERE {' AND '.join(conditions)}
            ORDER BY clickcount DESC
            LIMIT ?
        """
        params.append(limit)
        cursor.execute(sql, params)
        return format_stations(cursor.fetchall())
    except Exception as e:
        print(f"DB advanced search error: {e}", flush=True)
        return []


@mcp.tool()
def search(query: str, limit: int = 20) -> list[dict]:
    """
    Search radio stations by keyword (genre, name, etc.)
    Supports multilingual queries (Korean, Japanese, Chinese, etc.)
    and complex queries like "bossa nova lounge".

    Uses in-memory index for instant results.

    Args:
        query: Search term - can be in any language (재즈, ジャズ, jazz)
        limit: Number of results (default 20)

    Returns:
        List of radio stations
    """
    name_results = []
    tag_results = []
    seen_urls = set()

    # 1. 먼저 이름으로 검색 (가장 정확, 최우선)
    for r in fast_search_by_name(query, limit):
        if r["url"] not in seen_urls:
            seen_urls.add(r["url"])
            r["source"] = "db"
            r["match_type"] = "name"
            name_results.append(r)

    # 이름 매칭이 충분하면 바로 반환 (태그 검색 생략)
    if len(name_results) >= limit:
        return name_results[:limit]

    # 2. 다국어 번역 + 태그 검색 (이름 매칭 부족시)
    translated = translate_query(query)
    words = translated.lower().split()
    corrected_words = [fuzzy_match(w) for w in words]
    merged = merge_compound_tokens(corrected_words)

    # 유사어 확장 (장르 쿼리만)
    # 일반 단어(fm, radio, beach 등)는 태그 확장 안 함
    SKIP_TAG_EXPAND = {"fm", "am", "radio", "beach", "music", "the", "and", "or"}
    all_tags = []
    for word in merged:
        if word.lower() not in SKIP_TAG_EXPAND:
            all_tags.append(word)
            if word in TAG_SYNONYMS:
                all_tags.extend(TAG_SYNONYMS[word][:2])

    # 태그가 있을 때만 검색
    if all_tags:
        for r in fast_search_by_tag(all_tags, limit):
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                r["source"] = "db"
                r["match_type"] = "tag"
                tag_results.append(r)

    # 이름 매칭 우선 + 태그 매칭으로 채움
    all_results = name_results + tag_results

    # 3. API 검색 (이름 매칭이 없고 결과 부족시에만)
    # 이름으로 찾았으면 API 호출 생략 (속도 향상)
    has_name_match = any(r.get("match_type") == "name" for r in all_results)
    if not has_name_match and len(all_results) < limit // 2:
        for tag in all_tags[:2]:
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

    # 정렬: 이름 매칭 우선, 그 안에서 votes 정렬
    # 이름 매칭이 있으면 그게 먼저 오고, 나머지는 votes로
    if name_results:
        # 이름 매칭은 그대로 두고, 태그 매칭만 votes로 정렬
        tag_results.sort(key=lambda x: x.get("votes", 0), reverse=True)
        return (name_results + tag_results)[:limit]
    else:
        all_results.sort(key=lambda x: x.get("votes", 0), reverse=True)
        return all_results[:limit]


@mcp.tool()
def advanced_search(
    query: str = None,
    country: str = None,
    language: str = None,
    tags: str = None,
    min_bitrate: int = 0,
    codec: str = None,
    sort_by: str = "votes",
    limit: int = 20
) -> list[dict]:
    """
    Advanced search with multiple filters combined.

    Supports:
    - Multilingual queries (Korean, Japanese, Chinese, etc.)
    - Search operators: "exact phrase", -exclude, term1 OR term2
    - Fuzzy matching for typos
    - Combined filters (country + genre + bitrate)

    Args:
        query: Search keywords (supports operators like "smooth jazz" -vocal)
        country: Country code filter (KR, US, JP, etc.)
        language: Language filter (korean, english, japanese, etc.)
        tags: Comma-separated tags (jazz,lounge,chill)
        min_bitrate: Minimum bitrate in kbps (128, 192, 256, 320)
        codec: Audio codec filter (MP3, AAC, OGG, FLAC)
        sort_by: Sort by: votes, bitrate, name (default: votes)
        limit: Number of results

    Returns:
        List of matching radio stations

    Examples:
        - advanced_search(query="재즈")  # Korean → jazz
        - advanced_search(query="lounge -vocal", min_bitrate=256)
        - advanced_search(country="KR", tags="pop,kpop")
        - advanced_search(query='"smooth jazz"', sort_by="bitrate")
    """
    all_results = []
    seen_urls = set()
    search_tags = []

    # 1. 쿼리 처리
    if query:
        # 다국어 번역
        translated = translate_query(query)

        # 검색 연산자 파싱
        parsed = parse_search_query(translated)

        # 퍼지 매칭 + 복합어 병합
        must_tags = []
        for term in parsed["must"]:
            corrected = fuzzy_match(term)
            must_tags.append(corrected)

        # 복합어 병합
        merged = merge_compound_tokens(must_tags)

        # 유사어 확장
        for tag in merged:
            search_tags.append(tag)
            if tag in TAG_SYNONYMS:
                search_tags.extend(TAG_SYNONYMS[tag][:3])

        # should (OR) 조건
        for term in parsed["should"]:
            corrected = fuzzy_match(term)
            search_tags.append(corrected)

        # exact 조건 (나중에 필터링)
        exact_phrases = parsed["exact"]

        # must_not 조건 (나중에 필터링)
        exclude_terms = parsed["must_not"]
    else:
        exact_phrases = []
        exclude_terms = []

    # 2. 태그 파라미터 처리
    if tags:
        for tag in tags.split(","):
            tag = tag.strip().lower()
            if tag:
                search_tags.append(tag)

    # 3. DB 검색
    db_results = db_advanced_search(
        tags=search_tags if search_tags else None,
        country=country,
        language=language,
        min_bitrate=min_bitrate,
        codec=codec,
        limit=limit * 2
    )

    for r in db_results:
        if r["url"] not in seen_urls:
            # exact phrase 필터
            if exact_phrases:
                station_text = f"{r.get('name', '')} {r.get('tags', '')}".lower()
                if not all(phrase in station_text for phrase in exact_phrases):
                    continue

            # exclude 필터
            if exclude_terms:
                station_tags = r.get("tags", "").lower()
                if any(term in station_tags for term in exclude_terms):
                    continue

            seen_urls.add(r["url"])
            r["source"] = "db"
            all_results.append(r)

    # 4. API 검색 (결과 부족시)
    if len(all_results) < limit and search_tags:
        for tag in search_tags[:3]:
            params = {
                "limit": limit,
                "order": "clickcount",
                "reverse": "true",
                "lastcheckok": 1
            }
            if country:
                params["countrycode"] = country.upper()
            if min_bitrate > 0:
                params["bitrateMin"] = min_bitrate

            encoded_tag = urllib.parse.quote(tag)
            api_results = api_get(f"stations/bytag/{encoded_tag}", params)

            for s in api_results:
                url = s.get("url_resolved") or s.get("url", "")
                if url and url not in seen_urls:
                    station = format_station(s)

                    # exact/exclude 필터
                    station_text = f"{station.get('name', '')} {station.get('tags', '')}".lower()
                    if exact_phrases and not all(p in station_text for p in exact_phrases):
                        continue
                    if exclude_terms and any(t in station.get("tags", "").lower() for t in exclude_terms):
                        continue

                    seen_urls.add(url)
                    station["source"] = "api"
                    all_results.append(station)

                    if is_valid_station(s):
                        add_station_to_db(s)

    # 5. 정렬
    if sort_by == "bitrate":
        all_results.sort(key=lambda x: x.get("bitrate", 0), reverse=True)
    elif sort_by == "name":
        all_results.sort(key=lambda x: x.get("name", "").lower())
    else:  # votes (default)
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
def search_by_language(language: str, limit: int = 20) -> list[dict]:
    """
    Search radio stations by language.

    Args:
        language: Language name or code (korean, english, japanese, ko, en, ja)
        limit: Number of results

    Returns:
        List of radio stations
    """
    # 언어 코드 → 전체 이름 매핑
    LANG_CODES = {
        "ko": "korean", "en": "english", "ja": "japanese", "de": "german",
        "fr": "french", "es": "spanish", "pt": "portuguese", "it": "italian",
        "ru": "russian", "zh": "chinese", "ar": "arabic", "hi": "hindi",
        "nl": "dutch", "pl": "polish", "tr": "turkish", "vi": "vietnamese",
        "th": "thai", "id": "indonesian", "ms": "malay", "sv": "swedish",
    }

    lang = language.lower().strip()
    if lang in LANG_CODES:
        lang = LANG_CODES[lang]

    all_results = []
    seen_urls = set()

    # DB 검색
    db = get_db()
    if db:
        try:
            cursor = db.cursor()
            cursor.execute("""
                SELECT * FROM stations
                WHERE language LIKE ? AND (is_alive = 1 OR is_alive IS NULL)
                ORDER BY clickcount DESC
                LIMIT ?
            """, (f"%{lang}%", limit))
            for row in cursor.fetchall():
                r = format_station(row)
                if r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    r["source"] = "db"
                    all_results.append(r)
        except Exception as e:
            print(f"DB error: {e}", flush=True)

    # API 검색 (결과 부족시)
    if len(all_results) < limit:
        encoded = urllib.parse.quote(lang)
        api_results = api_get(f"stations/bylanguage/{encoded}", {
            "limit": limit,
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
        results = format_stations(api_results)

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

    # API에서 최신 URL 가져오기 (토큰 만료 대응)
    play_url = url
    url_refreshed = False
    if name:
        fresh_url = get_fresh_url(name)
        if fresh_url:
            play_url = fresh_url
            url_refreshed = (fresh_url != url)

    # mpv로 재생
    try:
        # 기존 소켓 삭제
        if os.path.exists(MPV_SOCKET):
            os.remove(MPV_SOCKET)

        player_proc = subprocess.Popen(
            ["mpv", "--no-video", "--no-terminal",
             f"--input-ipc-server={MPV_SOCKET}", play_url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # 잠시 대기 후 프로세스 확인
        time.sleep(1)
        if player_proc.poll() is not None:
            # 재생 실패 - DB에 기록
            mark_station_dead(url)
            return {"status": "error", "message": "Stream failed to start"}

        current_station = {"name": name, "url": play_url}
        result = {"status": "playing", "name": name, "url": play_url}
        if url_refreshed:
            result["url_refreshed"] = True
        return result
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
def resume() -> dict:
    """
    Resume last playing station.

    Returns:
        Playback status or error if no last station
    """
    last = load_last_station()
    if not last:
        return {"status": "error", "message": "No last station found"}

    url = last.get("url", "")
    name = last.get("name", "")
    if not url:
        return {"status": "error", "message": "No URL in last station"}

    return play(url, name)


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


def record_stream(url: str, duration: int = 12) -> bool:
    """스트림에서 오디오 녹음 (ffmpeg 사용)"""
    if not shutil.which("ffmpeg"):
        return False

    try:
        if os.path.exists(RECORD_FILE):
            os.remove(RECORD_FILE)

        subprocess.run(
            ["ffmpeg", "-y", "-t", str(duration), "-i", url,
             "-ac", "1", "-ar", "16000", "-acodec", "libmp3lame",
             "-loglevel", "quiet", RECORD_FILE],
            timeout=duration + 10
        )
        return os.path.exists(RECORD_FILE)
    except:
        return False


def recognize_with_acoustid(audio_file: str) -> dict:
    """AcoustID + Chromaprint로 곡 인식"""
    if not shutil.which("fpcalc"):
        return None

    try:
        # 오디오 핑거프린트 생성
        result = subprocess.run(
            ["fpcalc", "-json", audio_file],
            capture_output=True, text=True, timeout=30
        )
        fp_data = json.loads(result.stdout)
        fingerprint = fp_data.get("fingerprint", "")
        duration = int(fp_data.get("duration", 0))

        if not fingerprint:
            return None

        # AcoustID API 조회
        params = urllib.parse.urlencode({
            "client": ACOUSTID_API_KEY,
            "fingerprint": fingerprint,
            "duration": duration,
            "meta": "recordings+releasegroups+compress"
        })

        req = urllib.request.Request(f"https://api.acoustid.org/v2/lookup?{params}")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())

        if data.get("results"):
            for r in data["results"]:
                if r.get("recordings"):
                    rec = r["recordings"][0]
                    artists = rec.get("artists", [])
                    artist_name = artists[0].get("name", "") if artists else ""

                    album = ""
                    if rec.get("releasegroups"):
                        album = rec["releasegroups"][0].get("title", "")

                    return {
                        "title": rec.get("title", ""),
                        "artist": artist_name,
                        "album": album,
                        "acoustid": r.get("id", ""),
                        "score": r.get("score", 0)
                    }
    except:
        pass
    return None


def recognize_with_whisper(audio_file: str) -> dict:
    """Whisper로 음성 인식"""
    try:
        # mlx-whisper 시도 (Apple Silicon)
        result = subprocess.run(
            ["mlx_whisper", audio_file, "--language", "auto", "--output-format", "json"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0 and result.stdout.strip():
            return {"transcription": result.stdout.strip(), "method": "mlx-whisper"}
    except:
        pass

    try:
        # openai-whisper 시도
        result = subprocess.run(
            ["whisper", audio_file, "--language", "auto", "--output_format", "txt"],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            txt_file = audio_file.rsplit(".", 1)[0] + ".txt"
            if os.path.exists(txt_file):
                with open(txt_file, "r") as f:
                    text = f.read().strip()
                os.remove(txt_file)
                return {"transcription": text, "method": "whisper"}
    except:
        pass

    return None


@mcp.tool()
def recognize_song(duration: int = 12) -> dict:
    """
    Recognize current playing song using multiple methods.

    Methods tried in order:
    1. ICY metadata (instant, from stream)
    2. AcoustID (audio fingerprinting, like Shazam)
    3. Whisper (speech-to-text for DJ mentions)

    Args:
        duration: Recording duration in seconds (default 12)

    Returns:
        Recognized song info (title, artist, method)

    Requirements:
        - ffmpeg: brew install ffmpeg
        - fpcalc: brew install chromaprint (for AcoustID)
        - whisper: pip install openai-whisper (optional)
    """
    if not current_station:
        return {"status": "not_playing"}

    url = current_station.get("url_resolved") or current_station.get("url")
    if not url:
        return {"error": "no_stream_url"}

    # 1. 먼저 메타데이터 확인 (가장 빠름)
    metadata = now_playing()
    if metadata.get("title") and metadata.get("status") == "playing":
        result = {
            "status": "recognized",
            "method": "metadata",
            "title": metadata.get("title", ""),
            "artist": metadata.get("artist", ""),
            "station": current_station.get("name", "")
        }
        save_recognized(result)
        return result

    # 2. 오디오 녹음
    if not shutil.which("ffmpeg"):
        return {"error": "ffmpeg_not_installed", "hint": "brew install ffmpeg"}

    if not record_stream(url, duration):
        return {"error": "recording_failed"}

    # 3. AcoustID 시도
    if shutil.which("fpcalc"):
        acoustid_result = recognize_with_acoustid(RECORD_FILE)
        if acoustid_result:
            result = {
                "status": "recognized",
                "method": "acoustid",
                "title": acoustid_result.get("title", ""),
                "artist": acoustid_result.get("artist", ""),
                "album": acoustid_result.get("album", ""),
                "score": acoustid_result.get("score", 0),
                "station": current_station.get("name", "")
            }
            save_recognized(result)
            return result

    # 4. Whisper 시도
    if shutil.which("whisper") or shutil.which("mlx_whisper"):
        whisper_result = recognize_with_whisper(RECORD_FILE)
        if whisper_result and whisper_result.get("transcription"):
            result = {
                "status": "transcribed",
                "method": whisper_result.get("method", "whisper"),
                "transcription": whisper_result.get("transcription", ""),
                "station": current_station.get("name", "")
            }
            save_recognized(result)
            return result

    return {"status": "not_recognized", "hint": "Install fpcalc (brew install chromaprint) for better recognition"}


def save_recognized(result: dict):
    """인식 결과 저장"""
    songs = load_json(RECOGNIZED_FILE)
    result["recognized_at"] = datetime.now().isoformat()
    songs.append(result)
    save_json(RECOGNIZED_FILE, songs[-100:])  # 최근 100개 유지


@mcp.tool()
def get_recognized_songs(limit: int = 20) -> list[dict]:
    """
    Get history of recognized songs.

    Returns list of previously recognized songs with:
    - title, artist (if available)
    - method (metadata, acoustid, whisper)
    - station name
    - timestamp

    Args:
        limit: Number of recent songs to return

    Returns:
        List of recognized songs (newest first)
    """
    songs = load_json(RECOGNIZED_FILE)
    return list(reversed(songs[-limit:]))


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
def get_user_profile() -> dict:
    """
    Analyze listening history to build user preference profile.

    Returns:
        User profile with top tags, time preferences, day preferences
    """
    history = load_json(HISTORY_FILE)
    if not history:
        return {"status": "no_history", "message": "Listen to some radio first"}

    # 태그 가중치 (duration 기반)
    tag_weights = {}

    # 시간대별 선호
    time_prefs = {
        "morning": {},    # 6-10
        "daytime": {},    # 10-17
        "evening": {},    # 17-21
        "night": {},      # 21-6
    }

    # 요일별 선호
    day_prefs = {i: {} for i in range(7)}  # 0=월요일

    total_duration = 0
    total_listens = len(history)

    for entry in history:
        tags_str = entry.get("tags", "")
        duration = entry.get("duration", 60)  # 기본 1분
        timestamp = entry.get("timestamp", "")

        total_duration += duration

        # 태그 파싱
        tags = [t.strip().lower() for t in tags_str.split(",") if t.strip()]
        if not tags:
            continue

        # duration 가중치 (분 단위, 최대 10점)
        weight = min(duration / 60, 10)

        # 시간 파싱
        try:
            dt = datetime.fromisoformat(timestamp)
            hour = dt.hour
            weekday = dt.weekday()

            # 시간대 결정
            if 6 <= hour < 10:
                time_slot = "morning"
            elif 10 <= hour < 17:
                time_slot = "daytime"
            elif 17 <= hour < 21:
                time_slot = "evening"
            else:
                time_slot = "night"
        except:
            time_slot = "daytime"
            weekday = 0

        for tag in tags:
            # 전체 가중치
            tag_weights[tag] = tag_weights.get(tag, 0) + weight

            # 시간대별
            time_prefs[time_slot][tag] = time_prefs[time_slot].get(tag, 0) + weight

            # 요일별
            day_prefs[weekday][tag] = day_prefs[weekday].get(tag, 0) + weight

    # 정렬
    top_tags = sorted(tag_weights.items(), key=lambda x: -x[1])[:10]

    # 시간대별 상위 태그
    time_top = {}
    for slot, tags in time_prefs.items():
        if tags:
            time_top[slot] = sorted(tags.items(), key=lambda x: -x[1])[:5]

    # 요일별 상위 태그
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    day_top = {}
    for day, tags in day_prefs.items():
        if tags:
            day_top[day_names[day]] = sorted(tags.items(), key=lambda x: -x[1])[:3]

    return {
        "total_listens": total_listens,
        "total_minutes": round(total_duration / 60, 1),
        "top_tags": top_tags,
        "time_preferences": time_top,
        "day_preferences": day_top,
    }


@mcp.tool()
def personalized_recommend(limit: int = 10) -> list[dict]:
    """
    Recommend stations based on user's listening patterns.
    Considers time of day, day of week, and overall preferences.

    Args:
        limit: Number of results

    Returns:
        Personalized recommendations
    """
    profile = get_user_profile()
    if profile.get("status") == "no_history":
        # 기록 없으면 시간대 기반 추천
        return recommend_by_time()

    # 현재 컨텍스트
    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    # 시간대
    if 6 <= hour < 10:
        time_slot = "morning"
    elif 10 <= hour < 17:
        time_slot = "daytime"
    elif 17 <= hour < 21:
        time_slot = "evening"
    else:
        time_slot = "night"

    # 태그 수집 (우선순위: 시간대+요일 > 시간대 > 전체)
    recommended_tags = []

    # 1. 해당 요일 선호 태그
    day_prefs = profile.get("day_preferences", {}).get(day_names[weekday], [])
    for tag, _ in day_prefs[:2]:
        recommended_tags.append(tag)

    # 2. 해당 시간대 선호 태그
    time_prefs = profile.get("time_preferences", {}).get(time_slot, [])
    for tag, _ in time_prefs[:3]:
        if tag not in recommended_tags:
            recommended_tags.append(tag)

    # 3. 전체 선호 태그
    for tag, _ in profile.get("top_tags", [])[:5]:
        if tag not in recommended_tags:
            recommended_tags.append(tag)

    # 검색
    all_results = []
    seen = set()

    for tag in recommended_tags[:4]:
        results = search(tag, limit // 2)
        for r in results:
            if r["url"] not in seen:
                seen.add(r["url"])
                r["matched_tag"] = tag
                all_results.append(r)

    all_results.sort(key=lambda x: x.get("votes", 0), reverse=True)

    return {
        "context": {
            "time_slot": time_slot,
            "day": day_names[weekday],
            "recommended_tags": recommended_tags[:5],
        },
        "stations": all_results[:limit]
    }


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
