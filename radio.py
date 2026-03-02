#!/usr/bin/env python3
"""
RadioCli - 인터넷 라디오 검색 및 재생
"""

import subprocess
import sys
import json
import urllib.request
import urllib.parse
import shutil
import signal
import os
import time
import sqlite3
import threading
from datetime import datetime
from collections import Counter

# 데이터 파일 경로
DATA_DIR = os.path.expanduser("~/.radiocli")
FAVORITES_FILE = os.path.join(DATA_DIR, "favorites.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
SONGS_FILE = os.path.join(DATA_DIR, "songs.json")  # 곡 기록
PREFERENCES_FILE = os.path.join(DATA_DIR, "preferences.json")

# SQLite DB
DB_PATH = os.path.expanduser("~/RadioCli/radio_stations.db")

# API 모드: True=DB+API, False=DB만 (빠름)
USE_API = False  # 기본값: DB만 (0.1초)

# 데이터 디렉토리 생성
os.makedirs(DATA_DIR, exist_ok=True)

# === UI 언어 설정 ===
UI_LANG = os.environ.get("RADIOCLI_LANG", "ko")

# languages.json에서 다국어 로드 (70+ 언어 지원)
def load_languages():
    """languages.json에서 UI 문자열 로드"""
    script_dir = os.path.dirname(os.path.realpath(__file__))  # symlink 해결
    lang_file = os.path.join(script_dir, "languages.json")

    if os.path.exists(lang_file):
        try:
            with open(lang_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass

    # 파일 없으면 기본 한국어/영어만
    return {
        "ko": {"name": "한국어", "title": "RadioCli 라디오", "search_hint": "검색", "search_examples": "재즈", "ai_recommend": "AI 추천", "my_taste": "내 취향", "mood_now": "분위기", "song_recognize": "곡 인식", "popular": "인기", "hq": "고음질", "genre": "장르", "country": "국가", "favorites": "즐겨찾기", "playlist": "플레이리스트", "premium": "프리미엄", "dj_mode": "DJ모드", "stop": "정지", "quit": "종료", "playing": "재생", "added_fav": "추가됨", "removed_fav": "제거됨", "already_fav": "이미 있음", "no_fav": "없음", "searching": "검색 중", "loading": "로딩 중", "no_results": "결과 없음", "invalid_num": "잘못된 번호", "help_after_play": "+ 즐겨찾기 | s 정지 | m 메뉴", "ad_playing": "광고", "history": "기록", "llm": "LLM"},
        "en": {"name": "English", "title": "RadioCli Radio", "search_hint": "Search", "search_examples": "jazz", "ai_recommend": "AI Recommend", "my_taste": "My Taste", "mood_now": "Mood", "song_recognize": "Recognize", "popular": "Popular", "hq": "Hi-Quality", "genre": "Genre", "country": "Country", "favorites": "Favorites", "playlist": "Playlist", "premium": "Premium", "dj_mode": "DJ Mode", "stop": "Stop", "quit": "Quit", "playing": "Playing", "added_fav": "Added", "removed_fav": "Removed", "already_fav": "Already exists", "no_fav": "None", "searching": "Searching", "loading": "Loading", "no_results": "No results", "invalid_num": "Invalid", "help_after_play": "+ fav | s stop | m menu", "ad_playing": "Ad", "history": "History", "llm": "LLM"}
    }

UI_STRINGS = load_languages()

# LANG_NAMES 자동 생성
LANG_NAMES = {code: data.get("name", code) for code, data in UI_STRINGS.items()}

# 전체 국가 → UI 언어 매핑 (100+ 국가)
COUNTRY_TO_UI_LANG = {
    # 한국어
    "KR": "ko", "KP": "ko",
    # 영어
    "US": "en", "GB": "en", "AU": "en", "CA": "en", "NZ": "en", "IE": "en", "ZA": "en", "PH": "en", "SG": "en", "IN": "en", "PK": "en", "NG": "en", "KE": "en", "GH": "en",
    # 일본어
    "JP": "ja",
    # 중국어
    "CN": "zh", "HK": "zh-tw", "TW": "zh-tw", "MO": "zh-tw",
    # 스페인어
    "ES": "es", "MX": "es", "AR": "es", "CO": "es", "PE": "es", "VE": "es", "CL": "es", "EC": "es", "GT": "es", "CU": "es", "BO": "es", "DO": "es", "HN": "es", "PY": "es", "SV": "es", "NI": "es", "CR": "es", "PA": "es", "UY": "es", "PR": "es",
    # 프랑스어
    "FR": "fr", "BE": "fr", "CH": "fr", "LU": "fr", "MC": "fr", "SN": "fr", "CI": "fr", "CM": "fr", "MG": "fr", "ML": "fr",
    # 독일어
    "DE": "de", "AT": "de", "LI": "de",
    # 이탈리아어
    "IT": "it", "SM": "it", "VA": "it",
    # 포르투갈어
    "PT": "pt", "BR": "pt", "AO": "pt", "MZ": "pt",
    # 러시아어
    "RU": "ru", "BY": "ru", "KZ": "ru", "KG": "ru",
    # 아랍어
    "SA": "ar", "AE": "ar", "EG": "ar", "IQ": "ar", "MA": "ar", "DZ": "ar", "SD": "ar", "SY": "ar", "TN": "ar", "YE": "ar", "JO": "ar", "LB": "ar", "LY": "ar", "KW": "ar", "OM": "ar", "QA": "ar", "BH": "ar",
    # 힌디어
    "IN": "hi",
    # 벵골어
    "BD": "bn",
    # 인도네시아어
    "ID": "id",
    # 말레이어
    "MY": "ms", "BN": "ms",
    # 태국어
    "TH": "th",
    # 베트남어
    "VN": "vi",
    # 필리핀어
    "PH": "tl",
    # 터키어
    "TR": "tr", "CY": "tr",
    # 폴란드어
    "PL": "pl",
    # 네덜란드어
    "NL": "nl",
    # 스웨덴어
    "SE": "sv",
    # 노르웨이어
    "NO": "no",
    # 덴마크어
    "DK": "da",
    # 핀란드어
    "FI": "fi",
    # 체코어
    "CZ": "cs",
    # 슬로바키아어
    "SK": "sk",
    # 헝가리어
    "HU": "hu",
    # 루마니아어
    "RO": "ro", "MD": "ro",
    # 불가리아어
    "BG": "bg",
    # 우크라이나어
    "UA": "uk",
    # 크로아티아어
    "HR": "hr",
    # 세르비아어
    "RS": "sr", "ME": "sr",
    # 슬로베니아어
    "SI": "sl",
    # 에스토니아어
    "EE": "et",
    # 라트비아어
    "LV": "lv",
    # 리투아니아어
    "LT": "lt",
    # 그리스어
    "GR": "el",
    # 히브리어
    "IL": "he",
    # 페르시아어
    "IR": "fa", "AF": "fa",
    # 우르두어
    "PK": "ur",
    # 스와힐리어
    "TZ": "sw", "KE": "sw",
    # 아프리칸스어
    "ZA": "af",
    # 암하라어
    "ET": "am",
    # 카탈루냐어
    "AD": "ca",
    # 아이슬란드어
    "IS": "is",
    # 알바니아어
    "AL": "sq", "XK": "sq",
    # 마케도니아어
    "MK": "mk",
    # 벨라루스어
    "BY": "be",
    # 카자흐어
    "KZ": "kk",
    # 우즈베크어
    "UZ": "uz",
    # 몽골어
    "MN": "mn",
    # 네팔어
    "NP": "ne",
    # 싱할라어
    "LK": "si",
    # 미얀마어
    "MM": "my",
    # 크메르어
    "KH": "km",
    # 라오어
    "LA": "lo",
    # 조지아어
    "GE": "ka",
    # 아르메니아어
    "AM": "hy",
    # 아제르바이잔어
    "AZ": "az",
}

def t(key):
    """UI 문자열 번역"""
    strings = UI_STRINGS.get(UI_LANG, UI_STRINGS.get("en", {}))
    return strings.get(key, UI_STRINGS.get("en", {}).get(key, key))

def show_languages(page=1):
    """언어 선택 표시 (페이지당 20개)"""
    per_page = 20
    langs = list(LANG_NAMES.items())
    total = len(langs)
    total_pages = (total + per_page - 1) // per_page
    page = max(1, min(page, total_pages))

    start = (page - 1) * per_page
    end = min(start + per_page, total)

    print(f"\n  Language ({page}/{total_pages}) - {total}:")
    for code, name in langs[start:end]:
        marker = "●" if code == UI_LANG else "○"
        print(f"    {marker} {code}: {name}")
    if total_pages > 1:
        print(f"  [lang 2] {t('next_page')} / [lang code] {t('select_lang')}")
    print()

def change_language(code):
    """언어 변경"""
    global UI_LANG
    code = code.lower().strip()
    if code in UI_STRINGS:
        UI_LANG = code
        print(f"  ✓ {LANG_NAMES.get(code, code)}\n")
        return True
    else:
        # 페이지 번호인 경우
        if code.isdigit():
            show_languages(int(code))
            return False
        print(f"  ? {t('supported_langs')}: {len(UI_STRINGS)} (lang)\n")
        return False

def detect_language_by_ip():
    """IP 기반 언어 자동 감지"""
    global UI_LANG
    try:
        req = urllib.request.Request(
            "http://ip-api.com/json/?fields=countryCode",
            headers={"User-Agent": "RadioCli/1.0"}
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            country = data.get("countryCode", "")
            if country in COUNTRY_TO_UI_LANG:
                UI_LANG = COUNTRY_TO_UI_LANG[country]
                return UI_LANG
    except:
        pass
    return None

def init_language():
    """언어 초기화 (환경변수 > IP 감지 > 기본값)"""
    global UI_LANG
    # 환경변수 설정 있으면 그거 사용
    env_lang = os.environ.get("RADIOCLI_LANG", "")
    if env_lang and env_lang in UI_STRINGS:
        UI_LANG = env_lang
        return

    # IP로 자동 감지
    detected = detect_language_by_ip()
    if detected:
        return

    # 기본값
    UI_LANG = "ko"

# 곡 인식 설정
AUDD_API_KEY = os.environ.get("AUDD_API_KEY", "")  # 백업용
SHAZAM_API_KEY = os.environ.get("SHAZAM_API_KEY", "")  # 백업용
ACOUSTID_API_KEY = os.environ.get("ACOUSTID_API_KEY", "vQEDUkpM7e")  # AcoustID 무료 (하루 3000회)
RECOGNIZED_SONGS_FILE = os.path.join(DATA_DIR, "recognized_songs.json")
RECORD_FILE = os.path.join(DATA_DIR, "record_sample.mp3")
RECORD_WAV_FILE = os.path.join(DATA_DIR, "record_sample.wav")

# === LLM 설정 ===
# RADIOCLI_LLM: auto(기본), ollama, claude, openai, none
LLM_PROVIDER = os.environ.get("RADIOCLI_LLM", "auto")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gpt-oss:20b")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

API_BASE = "https://de1.api.radio-browser.info/json"
PLAYER = None
PLAYER_PROC = None
CURRENT_SONG_FILE = os.path.join(DATA_DIR, "current_song.txt")
MPV_SOCKET = os.path.join(DATA_DIR, "mpv.sock")

# === SQLite DB 검색 (빠름) ===
_db_cache = None

def db_search(query=None, country=None, tag=None, limit=30):
    """DB에서 검색 (메모리 캐시 사용)"""
    global _db_cache

    if not os.path.exists(DB_PATH):
        return []

    # 캐시 로드 (최초 1회)
    if _db_cache is None:
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM stations
                WHERE is_alive = 1 OR is_alive IS NULL
                ORDER BY clickcount DESC
            """)
            _db_cache = [dict(row) for row in cursor.fetchall()]
            conn.close()
        except:
            _db_cache = []

    results = []
    for s in _db_cache:
        # 국가 필터
        if country and s.get("countrycode", "").upper() != country.upper():
            continue
        # 태그 필터
        if tag and tag.lower() not in s.get("tags", "").lower():
            continue
        # 이름 검색
        if query and query.lower() not in s.get("name", "").lower():
            continue

        results.append(s)
        if len(results) >= limit:
            break

    return results

def mark_station_failed(url):
    """재생 실패한 방송 기록 (3회 실패 시 dead 처리)"""
    if not os.path.exists(DB_PATH):
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE stations
            SET fail_count = COALESCE(fail_count, 0) + 1,
                is_alive = CASE WHEN COALESCE(fail_count, 0) >= 2 THEN 0 ELSE is_alive END,
                last_checked_at = datetime('now')
            WHERE url = ? OR url_resolved = ?
        """, (url, url))
        conn.commit()
        conn.close()
        global _db_cache
        _db_cache = None  # 캐시 무효화
    except:
        pass

def cleanup_dead_stations():
    """죽은 방송 정리 (is_alive=0인 것들 삭제)"""
    if not os.path.exists(DB_PATH):
        return 0
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM stations WHERE is_alive = 0")
        count = cursor.fetchone()[0]
        if count > 0:
            cursor.execute("DELETE FROM stations WHERE is_alive = 0")
            conn.commit()
        conn.close()
        global _db_cache
        _db_cache = None
        return count
    except:
        return 0

# 인기 장르 (tag, translation_key)
GENRES = {
    "1": ("pop", "genre_pop"),
    "2": ("rock", "genre_rock"),
    "3": ("jazz", "genre_jazz"),
    "4": ("classical", "genre_classical"),
    "5": ("kpop", "genre_kpop"),
    "6": ("hiphop", "genre_hiphop"),
    "7": ("electronic", "genre_electronic"),
    "8": ("lounge", "genre_lounge"),
    "9": ("news", "genre_news"),
    "0": ("talk", "genre_talk"),
}

# 주요 국가 (code, translation_key)
COUNTRIES = {
    "kr": ("KR", "country_kr"),
    "us": ("US", "country_us"),
    "jp": ("JP", "country_jp"),
    "gb": ("GB", "country_gb"),
    "de": ("DE", "country_de"),
    "fr": ("FR", "country_fr"),
    "cn": ("CN", "country_cn"),
}

# 다국어 → 영어 매핑
LANG_MAP = {
    # === 국가 (한국어, 영어, 일본어, 중국어, 독일어, 프랑스어, 스페인어) ===
    # 한국
    "한국": "KR", "korea": "KR", "korean": "KR", "south korea": "KR",
    "韓国": "KR", "かんこく": "KR", "韩国": "KR", "corea": "KR", "corée": "KR",
    # 미국
    "미국": "US", "america": "US", "american": "US", "usa": "US", "united states": "US",
    "アメリカ": "US", "美国": "US", "amerika": "US", "états-unis": "US", "estados unidos": "US",
    # 일본
    "일본": "JP", "japan": "JP", "japanese": "JP",
    "日本": "JP", "にほん": "JP", "japón": "JP", "japon": "JP",
    # 영국
    "영국": "GB", "uk": "GB", "britain": "GB", "british": "GB", "england": "GB",
    "イギリス": "GB", "英国": "GB", "reino unido": "GB", "royaume-uni": "GB",
    # 독일
    "독일": "DE", "germany": "DE", "german": "DE", "deutschland": "DE",
    "ドイツ": "DE", "德国": "DE", "alemania": "DE", "allemagne": "DE",
    # 프랑스
    "프랑스": "FR", "france": "FR", "french": "FR", "frankreich": "FR",
    "フランス": "FR", "法国": "FR", "francia": "FR",
    # 중국
    "중국": "CN", "china": "CN", "chinese": "CN",
    "中国": "CN", "ちゅうごく": "CN", "chine": "CN",
    # 브라질
    "브라질": "BR", "brazil": "BR", "brasil": "BR", "brasilien": "BR",
    "ブラジル": "BR", "巴西": "BR", "brésil": "BR",
    # 호주
    "호주": "AU", "australia": "AU", "australian": "AU", "australien": "AU",
    "オーストラリア": "AU", "澳大利亚": "AU", "australie": "AU",
    # 캐나다
    "캐나다": "CA", "canada": "CA", "canadian": "CA", "kanada": "CA",
    "カナダ": "CA", "加拿大": "CA",
    # 이탈리아
    "이탈리아": "IT", "italy": "IT", "italian": "IT", "italien": "IT", "italia": "IT",
    "イタリア": "IT", "意大利": "IT", "italie": "IT",
    # 스페인
    "스페인": "ES", "spain": "ES", "spanish": "ES", "spanien": "ES", "españa": "ES",
    "スペイン": "ES", "西班牙": "ES", "espagne": "ES",
    # 러시아
    "러시아": "RU", "russia": "RU", "russian": "RU", "russland": "RU",
    "ロシア": "RU", "俄罗斯": "RU", "russie": "RU", "rusia": "RU",
    # 인도
    "인도": "IN", "india": "IN", "indian": "IN", "indien": "IN",
    "インド": "IN", "印度": "IN", "inde": "IN",
    # 멕시코
    "멕시코": "MX", "mexico": "MX", "mexican": "MX", "mexiko": "MX",
    "メキシコ": "MX", "墨西哥": "MX", "mexique": "MX", "méxico": "MX",
    # 네덜란드
    "네덜란드": "NL", "netherlands": "NL", "dutch": "NL", "holland": "NL",
    "オランダ": "NL", "荷兰": "NL", "pays-bas": "NL", "países bajos": "NL",
    # 스위스
    "스위스": "CH", "switzerland": "CH", "swiss": "CH", "schweiz": "CH",
    "スイス": "CH", "瑞士": "CH", "suisse": "CH", "suiza": "CH",

    # === 장르 (한국어, 영어, 일본어, 중국어, 독일어, 프랑스어, 스페인어) ===
    # 재즈
    "재즈": "jazz", "jazz": "jazz", "ジャズ": "jazz", "爵士": "jazz", "爵士乐": "jazz",
    # 클래식
    "클래식": "classical", "classical": "classical", "classic": "classical",
    "クラシック": "classical", "古典": "classical", "古典音乐": "classical",
    "klassik": "classical", "classique": "classical", "clásica": "classical",
    # 팝
    "팝": "pop", "pop": "pop", "pops": "pop", "ポップ": "pop", "流行": "pop",
    # 록
    "록": "rock", "rock": "rock", "ロック": "rock", "摇滚": "rock",
    # 힙합
    "힙합": "hiphop", "hiphop": "hiphop", "hip-hop": "hiphop", "hip hop": "hiphop",
    "ヒップホップ": "hiphop", "嘻哈": "hiphop", "rap": "hiphop", "랩": "hiphop",
    # K-pop
    "케이팝": "kpop", "kpop": "kpop", "k-pop": "kpop", "케이-팝": "kpop",
    "韓国ポップ": "kpop", "韩流": "kpop",
    # 뉴스 (확장)
    "뉴스": "news", "news": "news", "ニュース": "news", "新闻": "news",
    "nachrichten": "news", "nouvelles": "news", "noticias": "news",
    "시사": "news", "교양": "news", "정보": "news", "보도": "news",
    "information": "news", "current affairs": "news",
    # 토크 (확장)
    "토크": "talk", "talk": "talk", "トーク": "talk", "谈话": "talk",
    "라디오쇼": "talk", "radio show": "talk", "talkshow": "talk", "토크쇼": "talk",
    # 라운지
    "라운지": "lounge", "lounge": "lounge", "ラウンジ": "lounge",
    "chillout": "lounge", "chill": "lounge", "칠아웃": "lounge",
    # 블루스
    "블루스": "blues", "blues": "blues", "ブルース": "blues", "蓝调": "blues",
    # 컨트리
    "컨트리": "country", "country": "country", "カントリー": "country", "乡村": "country",
    # 일렉트로닉
    "일렉": "electronic", "electronic": "electronic", "electro": "electronic",
    "エレクトロ": "electronic", "电子": "electronic", "électronique": "electronic",
    "electronica": "electronic", "테크노": "electronic", "techno": "electronic",
    # 댄스
    "댄스": "dance", "dance": "dance", "ダンス": "dance", "舞曲": "dance",
    # 발라드
    "발라드": "ballad", "ballad": "ballad", "バラード": "ballad",
    # R&B
    "알앤비": "rnb", "rnb": "rnb", "r&b": "rnb", "r and b": "rnb",
    # 레게
    "레게": "reggae", "reggae": "reggae", "レゲエ": "reggae",
    # 소울
    "소울": "soul", "soul": "soul", "ソウル": "soul",
    # 펑크
    "펑크": "funk", "funk": "funk", "ファンク": "funk",
    # 메탈
    "메탈": "metal", "metal": "metal", "メタル": "metal", "heavy metal": "metal",
    # 앰비언트
    "앰비언트": "ambient", "ambient": "ambient", "アンビエント": "ambient",
    # 트로트
    "트로트": "trot", "trot": "trot", "トロット": "trot", "연가": "trot",
    # 종교
    "종교": "religious", "religious": "religious", "christian": "religious",
    "gospel": "religious", "기독교": "religious", "찬송": "religious",
    # 어린이
    "어린이": "children", "children": "children", "kids": "children",
    "子供": "children", "儿童": "children", "키즈": "children",
    # 올디스
    "올디스": "oldies", "oldies": "oldies", "オールディーズ": "oldies",
    "80년대": "80s", "80s": "80s", "90년대": "90s", "90s": "90s",
    "70년대": "70s", "70s": "70s", "60년대": "60s", "60s": "60s",
}

# 태그 확장 (관련 태그 함께 검색)
TAG_EXPAND = {
    "news": ["news", "talk", "information"],
    "talk": ["talk", "news", "spoken word"],
    "classical": ["classical", "classic", "orchestra", "symphony"],
    "jazz": ["jazz", "smooth jazz", "bebop", "swing"],
    "rock": ["rock", "classic rock", "alternative", "indie"],
    "pop": ["pop", "top 40", "hits", "charts"],
    "electronic": ["electronic", "edm", "techno", "house", "trance"],
    "lounge": ["lounge", "chillout", "ambient", "easy listening"],
    "hiphop": ["hiphop", "hip-hop", "rap", "urban"],
    "kpop": ["kpop", "k-pop", "korean pop"],
}

# 품질 필터
QUALITY_MAP = {
    # 한국어
    "고음질": {"min_bitrate": 192},
    "저음질": {"max_bitrate": 96},
    "최고음질": {"min_bitrate": 256},
    "hd": {"min_bitrate": 256},
    # 영어
    "high quality": {"min_bitrate": 192},
    "hq": {"min_bitrate": 192},
    "low quality": {"max_bitrate": 96},
    "lq": {"max_bitrate": 96},
    # 구체적
    "128k": {"min_bitrate": 128, "max_bitrate": 160},
    "192k": {"min_bitrate": 192, "max_bitrate": 224},
    "256k": {"min_bitrate": 256, "max_bitrate": 320},
    "320k": {"min_bitrate": 320},
}

# 영구 차단 목록 (이름에 포함되면 제외)
BLOCK_LIST = [
    "평양", "pyongyang", "north korea", "dprk", "조선중앙",
]

def is_blocked(name):
    """차단 목록에 있는지 확인"""
    if not name:
        return False
    name_lower = name.lower()
    for blocked in BLOCK_LIST:
        if blocked.lower() in name_lower:
            return True
    return False

def get_player():
    for p in ["mpv", "ffplay", "vlc"]:
        if shutil.which(p):
            return p
    return None

# === LLM 통합 ===
def llm_parse_query(query):
    """LLM으로 자연어 쿼리 파싱 → {"country": "KR", "tags": ["jazz"], "mood": "relaxing"}"""
    prompt = f"""사용자가 라디오 방송을 찾고 있습니다. 다음 요청을 분석해서 JSON으로 응답하세요.

요청: "{query}"

응답 형식 (JSON만, 설명 없이):
{{"country": "국가코드 또는 null", "tags": ["장르태그들"], "mood": "분위기", "time_of_day": "시간대"}}

예시:
- "한국 재즈" → {{"country": "KR", "tags": ["jazz"], "mood": null, "time_of_day": null}}
- "출근길 신나는 음악" → {{"country": null, "tags": ["pop", "dance"], "mood": "energetic", "time_of_day": "morning"}}
- "잠들기 전 편안한 클래식" → {{"country": null, "tags": ["classical", "ambient"], "mood": "relaxing", "time_of_day": "night"}}

JSON 응답:"""

    result = None

    # 1. Ollama (로컬)
    if LLM_PROVIDER in ["auto", "ollama"]:
        result = call_ollama(prompt)
        if result:
            return result

    # 2. Claude API
    if LLM_PROVIDER in ["auto", "claude"] and ANTHROPIC_API_KEY:
        result = call_claude(prompt)
        if result:
            return result

    # 3. OpenAI API
    if LLM_PROVIDER in ["auto", "openai"] and OPENAI_API_KEY:
        result = call_openai(prompt)
        if result:
            return result

    return None

def call_ollama(prompt):
    """Ollama 로컬 LLM 호출"""
    try:
        data = json.dumps({
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1}
        }).encode()

        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
            response_text = result.get("response", "")
            # JSON 추출
            return extract_json(response_text)
    except Exception as e:
        return None

def call_claude(prompt):
    """Claude API 호출"""
    try:
        data = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 200,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=data,
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01"
            }
        )

        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            response_text = result.get("content", [{}])[0].get("text", "")
            return extract_json(response_text)
    except Exception as e:
        return None

def call_openai(prompt):
    """OpenAI API 호출"""
    try:
        data = json.dumps({
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200,
            "temperature": 0.1
        }).encode()

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OPENAI_API_KEY}"
            }
        )

        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            response_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            return extract_json(response_text)
    except Exception as e:
        return None

def extract_json(text):
    """텍스트에서 JSON 추출"""
    try:
        # JSON 블록 찾기
        text = text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        # { } 찾기
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except:
        pass
    return None

def llm_search(query, limit=30):
    """LLM 기반 자연어 검색"""
    parsed = llm_parse_query(query)
    if not parsed:
        return None

    country = parsed.get("country")
    tags = parsed.get("tags", [])

    if country and tags:
        params = {
            "countrycode": country,
            "tag": tags[0],
            "limit": limit,
            "order": "votes",
            "reverse": "true"
        }
        return api_request("stations/search", params)
    elif tags:
        return search_by_tag(tags[0], limit)
    elif country:
        return search_by_country(country, limit)

    return None

# === 즐겨찾기 ===
def load_favorites():
    try:
        with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_favorites(favs):
    with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
        json.dump(favs, f, ensure_ascii=False, indent=2)

# === 청취 기록 ===
def load_history():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history[-500:], f, ensure_ascii=False, indent=2)  # 최근 500개만

def add_history(station, duration_sec):
    """청취 기록 추가"""
    if duration_sec < 10:  # 10초 미만은 무시
        return
    history = load_history()
    history.append({
        "name": station.get("name", ""),
        "url": station.get("url_resolved") or station.get("url", ""),
        "country": station.get("countrycode") or station.get("country", ""),
        "tags": station.get("tags", ""),
        "timestamp": datetime.now().isoformat(),
        "hour": datetime.now().hour,
        "weekday": datetime.now().weekday(),
        "duration": duration_sec
    })
    save_history(history)

# === 취향 분석 ===
def analyze_preferences():
    """청취 기록 분석해서 취향 파악"""
    history = load_history()
    if not history:
        return None

    # 태그 빈도 (청취 시간 가중치)
    tag_scores = Counter()
    country_scores = Counter()
    hour_tags = {}  # 시간대별 선호 태그

    for h in history:
        weight = min(h.get("duration", 60) / 60, 10)  # 최대 10분 가중치
        tags = h.get("tags", "").split(",")
        hour = h.get("hour", 12)

        for tag in tags:
            tag = tag.strip().lower()
            if tag:
                tag_scores[tag] += weight
                if hour not in hour_tags:
                    hour_tags[hour] = Counter()
                hour_tags[hour][tag] += weight

        country = h.get("country", "")
        if country:
            country_scores[country] += weight

    return {
        "top_tags": tag_scores.most_common(10),
        "top_countries": country_scores.most_common(5),
        "hour_preferences": {h: dict(tags.most_common(3)) for h, tags in hour_tags.items()},
        "total_listens": len(history),
        "total_minutes": sum(h.get("duration", 0) for h in history) // 60
    }

def get_mood_recommendations(limit=20):
    """시간대/분위기 기반 추천"""
    hour = datetime.now().hour
    weekday = datetime.now().weekday()  # 0=월, 6=일

    # 시간대별 분위기
    if 5 <= hour < 9:  # 이른 아침
        tags = ["classical", "ambient", "lofi"]
        mood = "아침 기상"
    elif 9 <= hour < 12:  # 오전
        tags = ["pop", "jazz", "acoustic"]
        mood = "활기찬 오전"
    elif 12 <= hour < 14:  # 점심
        tags = ["lounge", "pop", "jazz"]
        mood = "점심 휴식"
    elif 14 <= hour < 18:  # 오후
        tags = ["pop", "rock", "electronic"]
        mood = "집중 오후"
    elif 18 <= hour < 21:  # 저녁
        tags = ["jazz", "soul", "lounge"]
        mood = "퇴근 저녁"
    elif 21 <= hour < 24:  # 밤
        tags = ["ambient", "lounge", "classical"]
        mood = "편안한 밤"
    else:  # 새벽
        tags = ["ambient", "sleep", "classical"]
        mood = "고요한 새벽"

    # 주말이면 조금 더 활기차게
    if weekday >= 5:  # 토/일
        tags = ["pop", "dance", "rock"] + tags
        mood += " (주말)"

    print(f"  {t('mood')}: {mood}")

    # 여러 태그로 검색해서 합침
    all_results = []
    seen_urls = set()
    for tag in tags[:3]:
        results = search_by_tag(tag, limit)
        for s in results:
            url = s.get("url")
            if url not in seen_urls:
                seen_urls.add(url)
                all_results.append(s)
            if len(all_results) >= limit:
                break
        if len(all_results) >= limit:
            break

    return all_results[:limit]

def get_personalized_recommendations(limit=20):
    """취향 기반 개인화 추천"""
    prefs = analyze_preferences()
    if not prefs or not prefs["top_tags"]:
        return get_popular(limit)

    # 현재 시간대 선호 태그
    current_hour = datetime.now().hour
    hour_prefs = prefs.get("hour_preferences", {})

    # 시간대 매칭 (±2시간)
    best_tags = []
    for h in range(current_hour - 2, current_hour + 3):
        h = h % 24
        if h in hour_prefs:
            best_tags.extend(hour_prefs[h].keys())

    # 시간대 태그 없으면 전체 인기 태그 사용
    if not best_tags:
        best_tags = [t[0] for t in prefs["top_tags"][:3]]

    # 가장 많이 들은 태그로 검색
    if best_tags:
        tag = best_tags[0]
        results = search_by_tag(tag, limit * 2)
        # 이미 들은 방송은 뒤로
        history_urls = {h.get("url") for h in load_history()}
        new_stations = [s for s in results if s.get("url") not in history_urls]
        old_stations = [s for s in results if s.get("url") in history_urls]
        return (new_stations + old_stations)[:limit]

    return get_popular(limit)

def show_my_taste():
    """내 취향 보기"""
    prefs = analyze_preferences()
    if not prefs:
        print(f"\n  {t('no_history')}. {t('listen_first')}!\n")
        return

    print(f"\n  ═══ {t('taste_analysis')} ═══")
    print(f"  {t('total_listens').format(prefs['total_listens'], prefs['total_minutes'])}")

    print(f"\n  {t('fav_genres')}:")
    for tag, score in prefs["top_tags"][:5]:
        bar = "█" * min(int(score / 5), 20)
        print(f"    {tag:<15} {bar}")

    print(f"\n  {t('fav_countries')}:")
    for country, score in prefs["top_countries"][:3]:
        print(f"    {country}: {int(score)}{t('points')}")

    print()

def add_favorite(station):
    favs = load_favorites()
    # 중복 체크
    for f in favs:
        if f.get("url") == station.get("url"):
            return False
    favs.append({
        "name": station.get("name", ""),
        "url": station.get("url_resolved") or station.get("url", ""),
        "country": station.get("countrycode", ""),
        "tags": station.get("tags", ""),
        "bitrate": station.get("bitrate", 0)
    })
    save_favorites(favs)
    return True

def remove_favorite(idx):
    favs = load_favorites()
    if 0 <= idx < len(favs):
        removed = favs.pop(idx)
        save_favorites(favs)
        return removed
    return None

def print_favorites():
    favs = load_favorites()
    if not favs:
        print(f"\n  {t('no_fav')} (+ )\n")
        return []
    print(f"\n  {'#':<3} {t('station'):<30} {t('country'):<4} {t('genre'):<20} {t('quality'):<6}")
    print("  " + "-" * 70)
    for i, s in enumerate(favs, 1):
        name = s.get("name", "")[:28]
        country = s.get("country", "")[:3]
        tags = s.get("tags", "")[:18]
        bitrate = s.get("bitrate", 0)
        quality = f"{bitrate}k" if bitrate else ""
        print(f"  {i:<3} {name:<30} {country:<4} {tags:<20} {quality:<6}")
    print()
    return favs

def api_request(endpoint, params=None):
    url = f"{API_BASE}/{endpoint}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "RadioCli/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  {t('error')}: {e}")
        return []

def save_station_to_db(station):
    """재생 성공한 방송 DB에 저장"""
    if not station or not os.path.exists(DB_PATH):
        return False

    # 차단 목록 확인
    if is_blocked(station.get("name", "")):
        return False

    url = station.get("url_resolved") or station.get("url", "")
    if not url or "?" in url:  # 토큰 URL 제외
        return False

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO stations
            (stationuuid, name, url, url_resolved, country, countrycode,
             tags, bitrate, votes, clickcount, is_alive, fail_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0)
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
        ))
        conn.commit()
        conn.close()
        global _db_cache
        _db_cache = None
        return True
    except:
        return False

def merge_results(db_results, api_results, limit=30):
    """DB + API 결과 병합 (중복 제거, 차단 필터링)"""
    seen = set()
    merged = []

    # DB 먼저 (검증됨)
    for s in db_results:
        if is_blocked(s.get("name", "")):
            continue
        url = s.get("url_resolved") or s.get("url", "")
        if url and url not in seen:
            seen.add(url)
            s["source"] = "db"
            merged.append(s)

    # API 추가
    for s in api_results:
        if is_blocked(s.get("name", "")):
            continue
        url = s.get("url_resolved") or s.get("url", "")
        if url and url not in seen:
            seen.add(url)
            s["source"] = "api"
            merged.append(s)

    return merged[:limit]

def search(query, limit=20):
    """DB + API 검색 (USE_API=False면 DB만)"""
    db_results = db_search(query=query, limit=limit)
    if not USE_API:
        return db_results[:limit]
    api_results = api_request("stations/byname/" + urllib.parse.quote(query), {
        "limit": limit, "order": "clickcount", "reverse": "true", "lastcheckok": 1
    })
    return merge_results(db_results, api_results, limit)

def search_by_tag(tag, limit=20):
    """DB + API 태그 검색"""
    db_results = db_search(tag=tag, limit=limit)
    if not USE_API:
        return db_results[:limit]
    api_results = api_request("stations/bytag/" + urllib.parse.quote(tag), {
        "limit": limit, "order": "clickcount", "reverse": "true", "lastcheckok": 1
    })
    return merge_results(db_results, api_results, limit)

def search_by_country(code, limit=20):
    """DB + API 국가 검색"""
    db_results = db_search(country=code, limit=limit)
    if not USE_API:
        return db_results[:limit]
    api_results = api_request("stations/bycountrycodeexact/" + urllib.parse.quote(code.upper()), {
        "limit": limit, "order": "clickcount", "reverse": "true", "lastcheckok": 1
    })
    return merge_results(db_results, api_results, limit)

def get_popular(limit=20):
    """인기 방송 (DB 우선)"""
    if not USE_API:
        # DB에서 clickcount 순
        db_results = db_search(limit=limit)
        return sorted(db_results, key=lambda x: x.get("clickcount", 0), reverse=True)[:limit]
    return api_request("stations/topclick/" + str(limit))

def get_top_voted(limit=20):
    """인기 투표 상위"""
    return api_request("stations/topvote/" + str(limit))

def get_high_quality(limit=30):
    """고음질 방송 (256kbps 이상)"""
    params = {
        "bitrateMin": 256,
        "limit": limit,
        "order": "votes",
        "reverse": "true",
        "lastcheckok": 1
    }
    return api_request("stations/search", params)

def get_premium(limit=30):
    """프리미엄 방송 (고음질 + 인기) - 메타데이터 풍부할 가능성 높음"""
    params = {
        "bitrateMin": 192,
        "order": "votes",
        "reverse": "true",
        "limit": limit,
        "lastcheckok": 1
    }
    results = api_request("stations/search", params)
    # votes가 높은 것만 필터링
    return [s for s in results if s.get("votes", 0) >= 100][:limit]

# 자연어 → 태그 매핑 (분위기, 상황)
MOOD_MAP = {
    # 활기찬/신나는
    "신나는": ["dance", "electronic", "pop"], "신나": ["dance", "electronic"],
    "활기": ["dance", "pop", "rock"], "에너지": ["electronic", "dance"],
    "upbeat": ["dance", "pop"], "energetic": ["electronic", "rock"],
    "exciting": ["dance", "electronic"], "lively": ["pop", "dance"],
    # 편안한/잔잔한
    "편안": ["lounge", "ambient", "classical"], "잔잔": ["ambient", "classical", "piano"],
    "relaxing": ["lounge", "ambient"], "calm": ["classical", "ambient"],
    "peaceful": ["classical", "ambient"], "soothing": ["lounge", "piano"],
    "차분": ["classical", "ambient"], "힐링": ["ambient", "nature", "classical"],
    # 슬픈/감성
    "슬픈": ["ballad", "blues"], "감성": ["ballad", "soul", "jazz"],
    "우울": ["blues", "ambient"], "멜랑꼴리": ["blues", "classical"],
    "sad": ["blues", "ballad"], "emotional": ["soul", "ballad"],
    # 집중/공부
    "집중": ["classical", "ambient", "lofi"], "공부": ["classical", "lofi", "ambient"],
    "focus": ["classical", "ambient"], "study": ["lofi", "classical"],
    "work": ["lofi", "ambient"], "concentration": ["classical", "ambient"],
    # 수면
    "수면": ["ambient", "classical", "nature"], "잠": ["ambient", "sleep"],
    "sleep": ["ambient", "sleep", "nature"], "잠들": ["ambient", "sleep"],
    # 운동
    "운동": ["electronic", "dance", "rock"], "workout": ["electronic", "dance"],
    "gym": ["electronic", "rock"], "exercise": ["dance", "electronic"],
    "달리기": ["electronic", "dance"], "running": ["electronic", "dance"],
    # 아침/출근
    "아침": ["pop", "classical", "jazz"], "출근": ["pop", "news", "jazz"],
    "morning": ["pop", "classical"], "commute": ["news", "pop"],
    # 저녁/밤
    "저녁": ["jazz", "lounge", "classical"], "밤": ["lounge", "ambient", "jazz"],
    "evening": ["jazz", "lounge"], "night": ["lounge", "ambient"],
    # 파티
    "파티": ["dance", "electronic", "pop"], "party": ["dance", "electronic"],
    "클럽": ["electronic", "dance"], "club": ["electronic", "dance"],
    # 로맨틱
    "로맨틱": ["jazz", "ballad", "classical"], "romantic": ["jazz", "ballad"],
    "사랑": ["ballad", "pop"], "love": ["ballad", "pop"],
    # 빠른/느린
    "빠른": ["electronic", "dance", "rock"], "fast": ["electronic", "dance"],
    "느린": ["ambient", "classical", "lounge"], "slow": ["ambient", "lounge"],
}

def natural_language_search(query, limit=30):
    """자연어 쿼리를 분석해서 적절한 방송 검색"""
    query_lower = query.lower()
    found_tags = []
    found_country = None

    # 분위기/상황 키워드 찾기
    for keyword, tags in MOOD_MAP.items():
        if keyword in query_lower:
            found_tags.extend(tags)

    # 국가 키워드 찾기
    for keyword, code in LANG_MAP.items():
        if keyword.lower() in query_lower:
            if len(code) == 2 and code.isupper():
                found_country = code
                break

    # 장르 키워드 찾기
    for keyword, val in LANG_MAP.items():
        if keyword.lower() in query_lower and not (len(val) == 2 and val.isupper()):
            found_tags.append(val)

    # 국가만 찾으면 국가별 검색
    if found_country and not found_tags:
        return search_by_country(found_country, limit)

    # 태그 찾으면 태그 검색
    if found_tags:
        from collections import Counter
        tag_counts = Counter(found_tags)
        best_tag = tag_counts.most_common(1)[0][0]

        if found_country:
            params = {
                "countrycode": found_country,
                "tag": best_tag,
                "limit": limit,
                "order": "votes",
                "reverse": "true"
            }
            return api_request("stations/search", params)
        else:
            return search_by_tag(best_tag, limit)

    # 키워드 못 찾으면 일반 검색
    return None

def search_advanced(query, limit=50):
    """스마트 검색: 국가 + 장르 + 품질 복합 지원"""
    query_lower = query.lower().strip()

    country = None
    tags = []
    quality = {}  # {"min_bitrate": 192} 등
    name_parts = []

    # 1. 품질 필터 추출
    remaining = query_lower
    for phrase, q in sorted(QUALITY_MAP.items(), key=lambda x: -len(x[0])):
        if phrase.lower() in remaining:
            quality.update(q)
            remaining = remaining.replace(phrase.lower(), " ")

    # 2. 다중 단어 매핑 확인 (예: "south korea", "hip hop")
    for phrase, val in sorted(LANG_MAP.items(), key=lambda x: -len(x[0])):
        phrase_lower = phrase.lower()
        if phrase_lower in remaining:
            if len(val) == 2 and val.isupper():  # 국가코드
                if not country:
                    country = val
            else:  # 장르
                if val not in tags:
                    tags.append(val)
            remaining = remaining.replace(phrase_lower, " ")

    # 3. 남은 단어들 처리
    words = remaining.split()
    for w in words:
        w = w.strip()
        if not w:
            continue
        # 2글자 국가코드 직접 입력
        if len(w) == 2 and w.upper().isalpha():
            if not country:
                country = w.upper()
        elif len(w) > 1:
            name_parts.append(w)

    # 4. 태그 확장 (관련 태그 포함)
    expanded_tags = []
    for tag in tags:
        if tag in TAG_EXPAND:
            expanded_tags.extend(TAG_EXPAND[tag])
        else:
            expanded_tags.append(tag)
    # 중복 제거, 순서 유지
    seen = set()
    expanded_tags = [t for t in expanded_tags if not (t in seen or seen.add(t))]

    # 5. 검색 실행
    all_results = []

    # 국가 + 태그 조합
    if country and tags:
        if USE_API:
            params = {
                "countrycode": country,
                "tag": tags[0],
                "limit": limit,
                "order": "clickcount",
                "reverse": "true",
                "lastcheckok": 1
            }
            all_results = api_request("stations/search", params)
        else:
            # DB만: 국가 + 태그 필터
            all_results = [s for s in db_search(country=country, limit=limit*2)
                          if tags[0].lower() in s.get("tags", "").lower()]
    elif country:
        all_results = search_by_country(country, limit)
    elif tags:
        all_results = search_by_tag(tags[0], limit)
    elif name_parts:
        all_results = search(" ".join(name_parts), limit)
    else:
        all_results = search(query, limit)

    # 6. 중복 제거 + 차단 필터 (URL 기준)
    seen_urls = set()
    unique_results = []
    for s in all_results:
        if is_blocked(s.get("name", "")):
            continue
        url = s.get("url_resolved") or s.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_results.append(s)

    # 7. 품질 필터 적용 (결과 있으면)
    if quality and unique_results:
        filtered = []
        for s in unique_results:
            bitrate = s.get("bitrate", 0)
            if bitrate:
                if "min_bitrate" in quality and bitrate < quality["min_bitrate"]:
                    continue
                if "max_bitrate" in quality and bitrate > quality["max_bitrate"]:
                    continue
            filtered.append(s)
        # 필터 결과 있으면 사용, 없으면 원본 유지 (필터 완화)
        if filtered:
            unique_results = filtered
        else:
            # 품질 필터로 결과 없으면 정렬만 (높은 비트레이트 우선)
            pass

    # 8. 정렬: bitrate 높은 순 → votes 높은 순
    unique_results.sort(key=lambda x: (x.get("bitrate", 0), x.get("votes", 0)), reverse=True)

    return unique_results[:limit]

def print_stations(stations):
    if not stations:
        print(f"\n  {t('no_results')}\n")
        return
    print(f"\n  {'#':<3} {t('station'):<30} {t('country'):<4} {t('genre'):<20} {t('quality'):<6}")
    print("  " + "-" * 70)
    for i, s in enumerate(stations, 1):
        name = s.get("name", "")[:28]
        country = s.get("countrycode", "")[:3]
        tags = s.get("tags", "")[:18]
        bitrate = s.get("bitrate", 0)
        quality = f"{bitrate}k" if bitrate else ""
        print(f"  {i:<3} {name:<30} {country:<4} {tags:<20} {quality:<6}")
    print()
    print(f"  {t('press_num')} | m={t('menu')} | g={t('genre')} | c={t('country')} | /{t('searching')}")

def get_fresh_url(name):
    """API에서 방송 이름으로 새 URL 가져오기"""
    if not name:
        return None
    results = api_request("stations/byname/" + urllib.parse.quote(name), {
        "limit": 5, "order": "clickcount", "reverse": "true", "lastcheckok": 1
    })
    for s in results:
        if s.get("name", "").lower() == name.lower():
            return s.get("url_resolved") or s.get("url")
    # 정확한 매칭 없으면 첫번째 결과
    if results:
        return results[0].get("url_resolved") or results[0].get("url")
    return None

def update_station_url(old_url, new_url):
    """DB에서 방송 URL 업데이트"""
    if not os.path.exists(DB_PATH) or not new_url:
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE stations SET url_resolved = ?, fail_count = 0, is_alive = 1
            WHERE url = ? OR url_resolved = ?
        """, (new_url, old_url, old_url))
        conn.commit()
        conn.close()
        global _db_cache
        _db_cache = None
    except:
        pass

def play(url, name="", use_fresh_url=True):
    """
    라디오 재생
    use_fresh_url=True: API에서 최신 URL 먼저 가져옴 (토큰 만료 대응)
    """
    global PLAYER_PROC
    stop()
    if not PLAYER:
        print(f"  {t('no_player')}. brew install mpv")
        return False

    # API에서 최신 URL 가져오기 (토큰 방식 방송 대응)
    play_url = url
    if use_fresh_url and name:
        fresh_url = get_fresh_url(name)
        if fresh_url:
            play_url = fresh_url
            if fresh_url != url:
                print(f"  ↻ 최신 URL 사용")
                update_station_url(url, fresh_url)

    print(f"\n  ▶ {t('playing')}: {name}")
    print(f"    {play_url[:70]}{'...' if len(play_url) > 70 else ''}")
    print(f"    (n: {t('view_current')})\n")

    try:
        # 기존 소켓 파일 삭제
        if os.path.exists(MPV_SOCKET):
            os.remove(MPV_SOCKET)

        if PLAYER == "mpv":
            PLAYER_PROC = subprocess.Popen(
                ["mpv", "--no-video", "--really-quiet",
                 f"--input-ipc-server={MPV_SOCKET}", play_url],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        elif PLAYER == "ffplay":
            PLAYER_PROC = subprocess.Popen(
                ["ffplay", "-nodisp", "-loglevel", "quiet", play_url],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        elif PLAYER == "vlc":
            PLAYER_PROC = subprocess.Popen(
                ["vlc", "--intf", "dummy", play_url],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

        # 2초 대기 후 프로세스 살아있는지 확인
        time.sleep(2)
        if PLAYER_PROC and PLAYER_PROC.poll() is not None:
            # 프로세스 종료됨 = 재생 실패
            mark_station_failed(url)
            print(f"  ✗ 재생 실패. 방송이 종료되었거나 접속 불가합니다.")
            return False

        # 곡 모니터링 시작
        start_song_monitor(name)
        return True

    except Exception as e:
        print(f"  {t('play_error')}: {e}")
        return False

# 광고/필터 키워드
AD_KEYWORDS = [
    "advertisement", "advertising", "commercial", "werbung", "publicité",
    "광고", "公告", "広告", "reklam", "anuncio", "pubblicità",
    "ad break", "spot", "promo", "jingle", "station id", "station identification",
    "news", "뉴스", "weather", "날씨", "traffic", "교통",
]

def is_advertisement(title):
    """광고/비음악 콘텐츠 여부 확인"""
    if not title:
        return False
    title_lower = title.lower()
    for kw in AD_KEYWORDS:
        if kw.lower() in title_lower:
            return True
    return False

def get_current_song():
    """현재 재생 중인 곡 정보 가져오기 (mpv IPC)"""
    if PLAYER != "mpv" or not os.path.exists(MPV_SOCKET):
        return None

    try:
        import socket
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect(MPV_SOCKET)

        # icy-title 가져오기 (라디오 스트림 메타데이터)
        cmd = '{"command": ["get_property", "media-title"]}\n'
        sock.send(cmd.encode())
        response = sock.recv(4096).decode()
        sock.close()

        data = json.loads(response)
        title = data.get("data", "")
        if title:
            # 광고 필터링
            if is_advertisement(title):
                return {"title": title, "is_ad": True}
            return {"title": title, "is_ad": False}
    except Exception as e:
        pass

    return None

def show_current_song():
    """현재 곡 표시"""
    if not PLAYER_PROC:
        print(f"  {t('no_playing')}\n")
        return

    song = get_current_song()
    if song and song.get("title"):
        if song.get("is_ad"):
            print(f"\n  📢 {t('ad_playing')}: {song['title']}\n")
        else:
            print(f"\n  ♪ {t('current_song')}: {song['title']}\n")
    else:
        print(f"\n  {t('no_song_info')}\n")

# === 곡 기록 ===
_last_song_title = None

def load_songs():
    """곡 기록 로드"""
    if os.path.exists(SONGS_FILE):
        try:
            with open(SONGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return []

def save_songs(songs):
    """곡 기록 저장"""
    with open(SONGS_FILE, "w", encoding="utf-8") as f:
        json.dump(songs[-1000:], f, ensure_ascii=False, indent=2)  # 최대 1000곡

def parse_song_info(raw_title):
    """'Artist - Title' 형식 파싱"""
    if not raw_title:
        return None, None
    if " - " in raw_title:
        parts = raw_title.split(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    return None, raw_title.strip()

def add_song_to_history(raw_title, station_name):
    """곡 기록 추가"""
    global _last_song_title
    if not raw_title or raw_title == _last_song_title:
        return
    _last_song_title = raw_title

    artist, title = parse_song_info(raw_title)
    songs = load_songs()
    songs.append({
        "artist": artist or "",
        "title": title or raw_title,
        "station": station_name,
        "timestamp": datetime.now().isoformat(),
        "raw": raw_title
    })
    save_songs(songs)

def check_song_change(station_name):
    """곡 변경 감지하고 기록"""
    song = get_current_song()
    if song and song.get("title") and not song.get("is_ad"):
        add_song_to_history(song["title"], station_name)

def show_song_history(limit=20):
    """곡 기록 표시"""
    songs = load_songs()
    if not songs:
        print(f"\n  곡 기록 없음\n")
        return
    print(f"\n  최근 들은 곡 ({len(songs)}개 중 {min(limit, len(songs))}개)")
    print(f"  {'시간':<6} {'방송':<20} {'아티스트':<20} {'곡':<25}")
    print("  " + "-" * 75)
    for s in reversed(songs[-limit:]):
        ts = s.get("timestamp", "")
        time_str = ts[11:16] if ts else ""
        station = s.get("station", "")[:18]
        artist = s.get("artist", "-")[:18]
        title = s.get("title", "")[:23]
        print(f"  {time_str:<6} {station:<20} {artist:<20} {title:<25}")
    print()

# 곡 모니터링 설정
_song_monitor_thread = None
_song_monitor_running = False
SONG_MONITOR_ENABLED = True  # 곡 기록 온/오프

def start_song_monitor(station_name):
    """곡 변경 모니터링 시작 (백그라운드)"""
    global _song_monitor_thread, _song_monitor_running
    if not SONG_MONITOR_ENABLED:
        return

    def monitor():
        while _song_monitor_running and PLAYER_PROC:
            check_song_change(station_name)
            time.sleep(10)  # 10초마다 체크

    _song_monitor_running = True
    _song_monitor_thread = threading.Thread(target=monitor, daemon=True)
    _song_monitor_thread.start()

def stop_song_monitor():
    """곡 모니터링 중지"""
    global _song_monitor_running
    _song_monitor_running = False

def clear_song_history():
    """곡 기록 전체 삭제"""
    if os.path.exists(SONGS_FILE):
        os.remove(SONGS_FILE)
    global _last_song_title
    _last_song_title = None
    print("  곡 기록 삭제됨\n")

# === DJ 기능 (TTS) ===
DJ_ENABLED = os.environ.get("RADIOCLI_DJ", "0") == "1"
TTS_AUDIO_FILE = os.path.join(DATA_DIR, "tts_output.mp3")

# 언어별 음성 및 DJ 멘트
DJ_LANGUAGES = {
    "ko": {
        "voice": "ko-KR-SunHiNeural",
        "station_intros": [
            "자, 이제 {name}으로 가볼까요?",
            "{name}입니다. 좋은 음악 함께해요.",
            "다음은 {name}! 즐겨주세요.",
            "{tags} 음악 가득한 {name}입니다.",
        ],
        "song_intros": [
            "지금 나오는 곡은 {artist}의 {song}입니다.",
            "{artist}, {song} 듣고 계십니다.",
            "{song}, {artist}입니다.",
        ],
        "song_intros_no_artist": [
            "지금 나오는 곡은 {title}입니다.",
            "{title} 듣고 계십니다.",
        ],
    },
    "en": {
        "voice": "en-US-JennyNeural",
        "station_intros": [
            "Now let's go to {name}!",
            "This is {name}. Enjoy the music!",
            "Next up, {name}!",
            "Welcome to {name}, your {tags} station.",
        ],
        "song_intros": [
            "Now playing: {song} by {artist}.",
            "You're listening to {artist} with {song}.",
            "That was {song} by {artist}.",
        ],
        "song_intros_no_artist": [
            "Now playing: {title}.",
            "You're listening to {title}.",
        ],
    },
    "ja": {
        "voice": "ja-JP-NanamiNeural",
        "station_intros": [
            "さあ、{name}に行きましょう！",
            "{name}です。音楽をお楽しみください。",
            "次は{name}です！",
            "{tags}音楽いっぱいの{name}です。",
        ],
        "song_intros": [
            "今流れているのは{artist}の{song}です。",
            "{artist}で{song}をお聴きいただいています。",
            "{song}、{artist}でした。",
        ],
        "song_intros_no_artist": [
            "今流れているのは{title}です。",
            "{title}をお聴きいただいています。",
        ],
    },
    "fr": {
        "voice": "fr-FR-DeniseNeural",
        "station_intros": [
            "Allons maintenant sur {name}!",
            "Voici {name}. Profitez de la musique!",
            "Et maintenant, {name}!",
            "Bienvenue sur {name}, votre station {tags}.",
        ],
        "song_intros": [
            "Vous écoutez {song} par {artist}.",
            "C'était {song} de {artist}.",
            "{artist} avec {song}.",
        ],
        "song_intros_no_artist": [
            "Vous écoutez {title}.",
            "C'était {title}.",
        ],
    },
    "de": {
        "voice": "de-DE-KatjaNeural",
        "station_intros": [
            "Jetzt geht's zu {name}!",
            "Das ist {name}. Genießen Sie die Musik!",
            "Als nächstes: {name}!",
            "Willkommen bei {name}, Ihr {tags} Sender.",
        ],
        "song_intros": [
            "Jetzt läuft: {song} von {artist}.",
            "Sie hören {artist} mit {song}.",
            "Das war {song} von {artist}.",
        ],
        "song_intros_no_artist": [
            "Jetzt läuft: {title}.",
            "Sie hören {title}.",
        ],
    },
    "es": {
        "voice": "es-ES-ElviraNeural",
        "station_intros": [
            "¡Ahora vamos a {name}!",
            "Esto es {name}. ¡Disfruta la música!",
            "¡A continuación, {name}!",
            "Bienvenido a {name}, tu estación de {tags}.",
        ],
        "song_intros": [
            "Ahora suena: {song} de {artist}.",
            "Estás escuchando {artist} con {song}.",
            "Eso fue {song} de {artist}.",
        ],
        "song_intros_no_artist": [
            "Ahora suena: {title}.",
            "Estás escuchando {title}.",
        ],
    },
    "zh": {
        "voice": "zh-CN-XiaoxiaoNeural",
        "station_intros": [
            "现在让我们去{name}！",
            "这里是{name}，请欣赏音乐！",
            "接下来是{name}！",
            "欢迎来到{name}，您的{tags}电台。",
        ],
        "song_intros": [
            "正在播放：{artist}的{song}。",
            "您正在收听{artist}的{song}。",
            "刚才播放的是{artist}的{song}。",
        ],
        "song_intros_no_artist": [
            "正在播放：{title}。",
            "您正在收听{title}。",
        ],
    },
    "pt": {
        "voice": "pt-BR-FranciscaNeural",
        "station_intros": [
            "Agora vamos para {name}!",
            "Esta é {name}. Aproveite a música!",
            "A seguir, {name}!",
            "Bem-vindo à {name}, sua estação de {tags}.",
        ],
        "song_intros": [
            "Tocando agora: {song} de {artist}.",
            "Você está ouvindo {artist} com {song}.",
            "Essa foi {song} de {artist}.",
        ],
        "song_intros_no_artist": [
            "Tocando agora: {title}.",
            "Você está ouvindo {title}.",
        ],
    },
    "ru": {
        "voice": "ru-RU-SvetlanaNeural",
        "station_intros": [
            "А теперь переходим на {name}!",
            "Это {name}. Наслаждайтесь музыкой!",
            "Далее - {name}!",
            "Добро пожаловать на {name}.",
        ],
        "song_intros": [
            "Сейчас играет: {song} от {artist}.",
            "Вы слушаете {artist} с песней {song}.",
            "Это была {song} от {artist}.",
        ],
        "song_intros_no_artist": [
            "Сейчас играет: {title}.",
            "Вы слушаете {title}.",
        ],
    },
    "it": {
        "voice": "it-IT-ElsaNeural",
        "station_intros": [
            "Ora andiamo su {name}!",
            "Questa è {name}. Godetevi la musica!",
            "E ora, {name}!",
            "Benvenuti su {name}, la vostra stazione {tags}.",
        ],
        "song_intros": [
            "In onda ora: {song} di {artist}.",
            "State ascoltando {artist} con {song}.",
            "Quella era {song} di {artist}.",
        ],
        "song_intros_no_artist": [
            "In onda ora: {title}.",
            "State ascoltando {title}.",
        ],
    },
}

# 국가 코드 → 언어 매핑
COUNTRY_TO_LANG = {
    "KR": "ko", "KP": "ko",
    "US": "en", "GB": "en", "AU": "en", "CA": "en", "NZ": "en", "IE": "en",
    "JP": "ja",
    "FR": "fr", "BE": "fr", "CH": "fr",
    "DE": "de", "AT": "de",
    "ES": "es", "MX": "es", "AR": "es", "CO": "es", "CL": "es",
    "CN": "zh", "TW": "zh", "HK": "zh",
    "BR": "pt", "PT": "pt",
    "RU": "ru", "UA": "ru",
    "IT": "it",
}

def get_dj_language(station):
    """방송국의 국가로 DJ 언어 결정"""
    country = station.get("countrycode") or station.get("country", "")
    return COUNTRY_TO_LANG.get(country.upper(), "en")  # 기본값: 영어

# === 곡 인식 (Shazam-like) ===
def load_recognized_songs():
    try:
        with open(RECOGNIZED_SONGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_recognized_songs(songs):
    with open(RECOGNIZED_SONGS_FILE, "w", encoding="utf-8") as f:
        json.dump(songs[-100:], f, ensure_ascii=False, indent=2)  # 최근 100곡

def record_stream(url, duration=10):
    """스트림에서 오디오 녹음 (ffmpeg 사용)"""
    if not shutil.which("ffmpeg"):
        print(f"  {t('ffmpeg_needed')}: brew install ffmpeg")
        return False

    try:
        # 기존 파일 삭제
        if os.path.exists(RECORD_FILE):
            os.remove(RECORD_FILE)

        print(f"  {t('recording')}... ({duration}s)")
        result = subprocess.run(
            ["ffmpeg", "-y", "-t", str(duration), "-i", url,
             "-ac", "1", "-ar", "16000", "-acodec", "libmp3lame",
             "-loglevel", "quiet", RECORD_FILE],
            timeout=duration + 10
        )
        return os.path.exists(RECORD_FILE)
    except Exception as e:
        print(f"  {t('record_error')}: {e}")
        return False

def recognize_with_acoustid(audio_file):
    """AcoustID + Chromaprint로 곡 인식 (무료, 하루 3000회)"""
    # fpcalc 필요 (brew install chromaprint)
    if not shutil.which("fpcalc"):
        return None

    try:
        # 1. 오디오 핑거프린트 생성
        result = subprocess.run(
            ["fpcalc", "-json", audio_file],
            capture_output=True, text=True, timeout=30
        )
        fp_data = json.loads(result.stdout)
        fingerprint = fp_data.get("fingerprint", "")
        duration = int(fp_data.get("duration", 0))

        if not fingerprint:
            return None

        # 2. AcoustID API로 조회 (무료)
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
    except Exception as e:
        pass
    return None

def recognize_with_whisper(audio_file):
    """Whisper로 DJ 음성 인식 (로컬, 완전 무료)"""
    # whisper 또는 mlx-whisper 필요
    try:
        # mlx-whisper 시도 (Apple Silicon 최적화)
        result = subprocess.run(
            ["mlx_whisper", audio_file, "--language", "auto", "--output-format", "json"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            # 결과 파싱
            text = result.stdout.strip()
            if text:
                return {"transcription": text, "method": "mlx-whisper"}
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

def parse_song_from_text(text):
    """텍스트에서 곡 정보 추출 (LLM 사용)"""
    if not text:
        return None

    # LLM으로 파싱 시도
    prompt = f"""다음 라디오 DJ 멘트에서 곡 정보를 추출하세요.
텍스트: "{text}"

JSON 형식으로만 답하세요:
{{"title": "곡제목", "artist": "아티스트"}}
정보가 없으면: {{"title": null, "artist": null}}"""

    parsed = llm_parse_query(prompt)  # 기존 LLM 함수 재사용
    if parsed and parsed.get("title"):
        return parsed
    return None

def recognize_song(station=None):
    """현재 재생 중인 곡 인식 (무료 방식들)"""
    if not PLAYER_PROC:
        print(f"  {t('no_playing')}\n")
        return None

    url = None
    if station:
        url = station.get("url_resolved") or station.get("url")

    if not url:
        print(f"  {t('no_stream')}\n")
        return None

    # 1. 먼저 ICY 메타데이터 확인 (가장 빠름)
    song = get_current_song()
    if song and song.get("title"):
        if song.get("is_ad"):
            print(f"\n  📢 {t('ad_playing')}\n")
            return None
        print(f"\n  🎵 {t('metadata')}: {song['title']}\n")
        # 이미 저장된 정보 사용
        result = {"title": song["title"], "method": "metadata"}
        if " - " in song["title"]:
            parts = song["title"].split(" - ", 1)
            result["artist"] = parts[0].strip()
            result["title"] = parts[1].strip()
        save_song_result(result, station)
        return result

    # 2. Chromaprint + AcoustID (무료, 무제한에 가까움)
    print(f"  {t('no_metadata')}. {t('analyzing')}...")

    if not record_stream(url, duration=12):
        return None

    # fpcalc 있으면 AcoustID 시도
    if shutil.which("fpcalc"):
        print(f"  AcoustID {t('searching')}...")
        result = recognize_with_acoustid(RECORD_FILE)
        if result:
            result["method"] = "acoustid"
            save_song_result(result, station)
            print(f"\n  🎵 {t('result')}:")
            print(f"     {t('title_label')}: {result.get('title', '?')}")
            print(f"     {t('artist')}: {result.get('artist', '?')}")
            if result.get('album'):
                print(f"     {t('album')}: {result['album']}")
            print(f"     ({t('accuracy')}: {result.get('score', 0):.0%})\n")
            return result

    # 3. Whisper로 DJ 멘트 인식 (로컬)
    if shutil.which("whisper") or shutil.which("mlx_whisper"):
        print(f"  {t('recognizing')} (Whisper)...")
        whisper_result = recognize_with_whisper(RECORD_FILE)
        if whisper_result and whisper_result.get("transcription"):
            print(f"  DJ: \"{whisper_result['transcription'][:100]}...\"")
            # LLM으로 곡 정보 추출
            parsed = parse_song_from_text(whisper_result["transcription"])
            if parsed and parsed.get("title"):
                parsed["method"] = "whisper+llm"
                save_song_result(parsed, station)
                print(f"\n  🎵 {t('result')}:")
                print(f"     {t('title_label')}: {parsed.get('title', '?')}")
                print(f"     {t('artist')}: {parsed.get('artist', '?')}\n")
                return parsed

    print(f"  {t('no_results')}")
    print(f"  {t('tip')}: brew install chromaprint\n")
    return None

def save_song_result(result, station):
    """인식 결과 저장 (광고 제외)"""
    # 광고면 저장 안함
    title = result.get("title", "")
    if is_advertisement(title):
        return

    songs = load_recognized_songs()
    result["recognized_at"] = datetime.now().isoformat()
    result["station"] = station.get("name", "") if station else ""
    songs.append(result)
    save_recognized_songs(songs)

def recognize_song_acoustid(station=None):
    """AcoustID만 강제 테스트"""
    if not PLAYER_PROC:
        print(f"  {t('no_playing')}\n")
        return None

    url = station.get("url_resolved") or station.get("url") if station else None
    if not url:
        print(f"  {t('no_stream')}\n")
        return None

    if not shutil.which("fpcalc"):
        print(f"  {t('fpcalc_needed')}: brew install chromaprint\n")
        return None

    print(f"  [AcoustID {t('testing')}] {t('recording')}...")
    if not record_stream(url, duration=12):
        return None

    print(f"  AcoustID {t('searching')}...")
    result = recognize_with_acoustid(RECORD_FILE)

    if result:
        result["method"] = "acoustid"
        save_song_result(result, station)
        print(f"\n  🎵 AcoustID {t('result')}:")
        print(f"     {t('title_label')}: {result.get('title', '?')}")
        print(f"     {t('artist')}: {result.get('artist', '?')}")
        print(f"     {t('accuracy')}: {result.get('score', 0):.0%}\n")
        return result
    else:
        print(f"  AcoustID: {t('recognition_failed')}\n")
        return None

def recognize_song_whisper(station=None):
    """Whisper만 강제 테스트"""
    if not PLAYER_PROC:
        print(f"  {t('no_playing')}\n")
        return None

    url = station.get("url_resolved") or station.get("url") if station else None
    if not url:
        print(f"  {t('no_stream')}\n")
        return None

    if not shutil.which("whisper") and not shutil.which("mlx_whisper"):
        print(f"  {t('whisper_needed')}: pip install openai-whisper\n")
        return None

    print(f"  [Whisper {t('testing')}] {t('recording')}...")
    if not record_stream(url, duration=15):
        return None

    print(f"  {t('recognizing')} ({t('takes_time')})...")
    result = recognize_with_whisper(RECORD_FILE)

    if result and result.get("transcription"):
        print(f"\n  🎤 {t('voice_result')}:")
        print(f"     \"{result['transcription'][:200]}\"")

        # LLM으로 곡 정보 추출 시도
        parsed = parse_song_from_text(result["transcription"])
        if parsed and parsed.get("title"):
            print(f"\n  🎵 {t('extracted_info')}:")
            print(f"     {t('title_label')}: {parsed.get('title', '?')}")
            print(f"     {t('artist')}: {parsed.get('artist', '?')}\n")
            parsed["method"] = "whisper+llm"
            save_song_result(parsed, station)
            return parsed
        else:
            print(f"  {t('extract_failed')}\n")
    else:
        print(f"  Whisper: {t('recognition_failed')}\n")

    return None

def show_recognized_songs():
    """인식된 곡 목록 표시"""
    songs = load_recognized_songs()
    if not songs:
        print(f"\n  {t('no_recognized')} (i)\n")
        return

    print(f"\n  ═══ {t('recognized_list')} ({len(songs)} {t('songs')}) ═══")
    for i, s in enumerate(reversed(songs[-20:]), 1):
        title = s.get("title", "?")[:25]
        artist = s.get("artist", "?")[:20]
        station = s.get("station", "")[:15]
        print(f"  {i:2}. {title:<25} - {artist:<20} ({station})")
    print()

def mpv_command(cmd):
    """mpv IPC 명령 전송"""
    if not os.path.exists(MPV_SOCKET):
        return False
    try:
        import socket
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect(MPV_SOCKET)
        sock.send((json.dumps({"command": cmd}) + "\n").encode())
        sock.close()
        return True
    except:
        return False

def pause_radio():
    """라디오 일시정지"""
    mpv_command(["set_property", "pause", True])

def resume_radio():
    """라디오 재개"""
    mpv_command(["set_property", "pause", False])

def speak(text, voice=None, pause_radio_playback=True):
    """TTS로 말하기 (Edge TTS)"""
    voice = voice or TTS_VOICE
    try:
        # 1. 라디오 재생 중이면 일시정지
        radio_was_playing = PLAYER_PROC is not None and pause_radio_playback
        if radio_was_playing:
            pause_radio()
            time.sleep(0.3)

        # 2. edge-tts로 음성 생성
        subprocess.run(
            ["edge-tts", "--voice", voice, "--text", text, "--write-media", TTS_AUDIO_FILE],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=10
        )

        # 3. TTS 재생 (완료까지 대기)
        if shutil.which("afplay"):
            subprocess.run(["afplay", TTS_AUDIO_FILE],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif shutil.which("mpv"):
            subprocess.run(["mpv", "--no-video", "--really-quiet", TTS_AUDIO_FILE],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif shutil.which("ffplay"):
            subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", TTS_AUDIO_FILE],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 4. 라디오 재개
        if radio_was_playing:
            time.sleep(0.2)
            resume_radio()

        return True
    except Exception as e:
        if radio_was_playing and PLAYER_PROC:
            resume_radio()
        return False

def dj_announce_station(station):
    """방송국 소개 - 다국어 DJ"""
    if not DJ_ENABLED:
        return

    import random

    name = station.get("name", "")
    tags = station.get("tags", "").split(",")[0] if station.get("tags") else "music"

    # 언어 결정
    lang = get_dj_language(station)
    lang_data = DJ_LANGUAGES.get(lang, DJ_LANGUAGES["en"])

    # 템플릿 선택 및 포맷
    template = random.choice(lang_data["station_intros"])
    text = template.format(name=name, tags=tags)

    speak(text, voice=lang_data["voice"])

def dj_announce_song(title, station=None):
    """현재 곡 소개 - 다국어 DJ"""
    if not DJ_ENABLED or not title:
        return

    import random

    # 언어 결정
    lang = "en"  # 기본값
    if station:
        lang = get_dj_language(station)
    lang_data = DJ_LANGUAGES.get(lang, DJ_LANGUAGES["en"])

    # 아티스트 - 제목 형식 파싱
    if " - " in title:
        parts = title.split(" - ", 1)
        artist, song = parts[0].strip(), parts[1].strip()
        template = random.choice(lang_data["song_intros"])
        text = template.format(artist=artist, song=song)
    else:
        template = random.choice(lang_data["song_intros_no_artist"])
        text = template.format(title=title)

    speak(text, voice=lang_data["voice"])

def toggle_dj():
    """DJ 모드 토글"""
    global DJ_ENABLED
    DJ_ENABLED = not DJ_ENABLED
    if DJ_ENABLED:
        print(f"  🎙 {t('dj_on')}")
        speak(t('dj_on_speak'))
    else:
        print(f"  🎙 {t('dj_off')}")
    print()

# === 플레이리스트 ===
PLAYLIST_FILE = os.path.join(DATA_DIR, "playlists.json")

def load_playlists():
    try:
        with open(PLAYLIST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_playlists(playlists):
    with open(PLAYLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(playlists, f, ensure_ascii=False, indent=2)

def create_smart_playlist(name, criteria):
    """스마트 플레이리스트 생성"""
    stations = []

    if criteria == "favorites":
        # 즐겨찾기 기반
        stations = load_favorites()
    elif criteria == "history":
        # 최근 청취 기반 (중복 제거)
        history = load_history()
        seen = set()
        for h in reversed(history):
            url = h.get("url")
            if url and url not in seen:
                seen.add(url)
                stations.append(h)
            if len(stations) >= 20:
                break
    elif criteria == "mood":
        # 현재 분위기 기반
        stations = get_mood_recommendations(20)
    elif criteria == "ai":
        # AI 추천 기반
        stations = get_personalized_recommendations(20)
    elif criteria.startswith("tag:"):
        # 특정 태그
        tag = criteria[4:]
        stations = search_by_tag(tag, 20)
    elif criteria.startswith("country:"):
        # 특정 국가
        code = criteria[8:]
        stations = search_by_country(code, 20)

    if stations:
        playlists = load_playlists()
        playlists[name] = {
            "created": datetime.now().isoformat(),
            "criteria": criteria,
            "stations": stations[:20]
        }
        save_playlists(playlists)
        return len(stations)
    return 0

def show_playlists():
    """플레이리스트 목록"""
    playlists = load_playlists()
    if not playlists:
        print(f"\n  {t('no_playlist')}")
        print(f"  ({t('create_pl')}: pl name type)")
        print(f"  {t('pl_types')}: favorites, history, mood, ai, tag:jazz, country:KR")
        print()
        return None

    print(f"\n  ═══ {t('playlist')} ═══")
    for i, (name, pl) in enumerate(playlists.items(), 1):
        count = len(pl.get("stations", []))
        criteria = pl.get("criteria", "")
        print(f"  {i}. {name} ({count} {t('songs')}) - {criteria}")
    print()
    return list(playlists.keys())

def get_playlist_stations(name):
    """플레이리스트의 방송국 목록"""
    playlists = load_playlists()
    if name in playlists:
        return playlists[name].get("stations", [])
    # 번호로 접근
    try:
        idx = int(name) - 1
        keys = list(playlists.keys())
        if 0 <= idx < len(keys):
            return playlists[keys[idx]].get("stations", [])
    except:
        pass
    return []

def delete_playlist(name):
    """플레이리스트 삭제"""
    playlists = load_playlists()
    # 번호로 삭제
    try:
        idx = int(name) - 1
        keys = list(playlists.keys())
        if 0 <= idx < len(keys):
            name = keys[idx]
    except:
        pass

    if name in playlists:
        del playlists[name]
        save_playlists(playlists)
        return True
    return False

def stop():
    global PLAYER_PROC
    stop_song_monitor()  # 곡 모니터링 중지
    if PLAYER_PROC:
        PLAYER_PROC.terminate()
        PLAYER_PROC = None
        return True
    return False

def get_llm_status():
    """LLM 상태 확인"""
    if LLM_PROVIDER == "none":
        return "off"
    if LLM_PROVIDER == "ollama" or LLM_PROVIDER == "auto":
        try:
            req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return f"ollama:{OLLAMA_MODEL}"
        except:
            pass
    if ANTHROPIC_API_KEY and LLM_PROVIDER in ["auto", "claude"]:
        return "claude"
    if OPENAI_API_KEY and LLM_PROVIDER in ["auto", "openai"]:
        return "openai"
    return "keyword"

def show_menu():
    fav_count = len(load_favorites())
    history_count = len(load_history())
    llm_status = get_llm_status()
    print(f"""
  ╭─────────────────────────────────────╮
  │         {t('title'):^25}   │
  ├─────────────────────────────────────┤
  │  {t('search_hint'):<35}│
  │  {t('search_examples'):<35}│
  ├─────────────────────────────────────┤
  │  a  {t('ai_recommend'):<10} t  {t('my_taste'):<13}│
  │  w  {t('mood_now'):<10} i  {t('song_recognize'):<13}│
  │  p  {t('popular'):<10} h  {t('hq'):<13}│
  │  g  {t('genre'):<10} c  {t('country'):<13}│
  │  f  {t('favorites')}({fav_count})    l  {t('playlist'):<13}│
  │  r  {t('premium'):<10} d  {t('dj_mode'):<13}│
  ├─────────────────────────────────────┤
  │  s  {t('stop'):<10} q  {t('quit'):<13}│
  │  lang {t('lang_setting'):<24}│
  ╰─────────────────────────────────────╯
  {t('llm')}: {llm_status} | {t('history')}: {history_count}
""")

def show_genres():
    print(f"\n  {t('genre_select')}:")
    for k, (tag, name_key) in GENRES.items():
        print(f"    {k}. {t(name_key)}")
    print()

def show_countries():
    print(f"\n  {t('country_select')}:")
    for k, (code, name_key) in COUNTRIES.items():
        print(f"    {k}. {t(name_key)} ({code})")
    print(f"    ({t('press_num')}: us, jp, de ...)")
    print()

def main():
    global PLAYER

    # 언어 자동 감지
    init_language()

    PLAYER = get_player()
    if not PLAYER:
        print(t('no_results'))  # 플레이어 없음 메시지
        print("  brew install mpv")
        sys.exit(1)

    stations = []
    current_station = None  # 현재 재생 중인 방송
    play_start_time = None  # 재생 시작 시간
    mode = "menu"  # menu, genre, country, search, list, fav

    def signal_handler(sig, frame):
        stop()
        print("\n")
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)

    print(f"\n  RadioCli ({PLAYER})")
    show_menu()

    while True:
        try:
            if mode == "menu":
                prompt = "> "
            elif mode == "genre":
                prompt = f"{t('prompt_genre')}> "
            elif mode == "country":
                prompt = f"{t('prompt_country')}> "
            elif mode == "search":
                prompt = f"{t('prompt_search')}> "
            elif mode == "list":
                prompt = f"{t('prompt_number')}> "
            else:
                prompt = "> "

            cmd = input(prompt).strip().lower()
        except EOFError:
            break

        if not cmd:
            if mode != "menu":
                mode = "menu"
                show_menu()
            continue

        # 종료
        if cmd == "q":
            stop()
            break

        # API 모드 토글
        if cmd == "!":
            global USE_API
            USE_API = not USE_API
            mode_str = "DB+API" if USE_API else "DB만 (빠름)"
            print(f"  검색 모드: {mode_str}\n")
            continue

        # 정지
        if cmd == "s":
            if PLAYER_PROC and current_station and play_start_time:
                duration = int(time.time() - play_start_time)
                add_history(current_station, duration)
            if stop():
                print(f"  ■ {t('stopped_playing')}\n")
                current_station = None
                play_start_time = None
            continue

        # 현재 곡 보기
        if cmd == "n":
            show_current_song()
            # DJ 모드면 곡 소개
            song = get_current_song()
            if song and song.get("title"):
                dj_announce_song(song["title"], current_station)
            continue

        # 곡 인식 (Shazam-like)
        if cmd == "i":
            recognize_song(current_station)
            continue

        # 강제 AcoustID 테스트
        if cmd == "i2":
            recognize_song_acoustid(current_station)
            continue

        # 강제 Whisper 테스트
        if cmd == "i3":
            recognize_song_whisper(current_station)
            continue

        # 인식된 곡 목록
        if cmd == "il":
            show_recognized_songs()
            continue

        # 곡 기록 보기
        if cmd == "sl":
            show_song_history()
            continue

        # 곡 기록 토글 (온/오프)
        if cmd == "st":
            global SONG_MONITOR_ENABLED
            SONG_MONITOR_ENABLED = not SONG_MONITOR_ENABLED
            status = "ON" if SONG_MONITOR_ENABLED else "OFF"
            print(f"  곡 기록: {status}\n")
            continue

        # 곡 기록 삭제
        if cmd == "sc":
            clear_song_history()
            continue

        # DJ 모드 토글
        if cmd == "d":
            toggle_dj()
            continue

        # 언어 변경
        if cmd == "lang":
            show_languages()
            mode = "lang"
            continue

        # 언어 선택
        if mode == "lang":
            if change_language(cmd):
                mode = "menu"
                show_menu()
            continue

        # 플레이리스트
        if cmd == "l":
            pl_names = show_playlists()
            if pl_names:
                mode = "playlist"
                print(f"  ({t('enter_num_play')}, -{t('enter_num_del')})")
            continue

        # 플레이리스트 생성: pl 이름 타입
        if cmd.startswith("pl "):
            parts = cmd[3:].split()
            if len(parts) >= 2:
                name = parts[0]
                criteria = parts[1]
                count = create_smart_playlist(name, criteria)
                if count:
                    print(f"  ✓ '{name}' {t('pl_created')} ({count} {t('songs')})\n")
                else:
                    print(f"  ✗ {t('create_failed')}\n")
            else:
                print(f"  {t('usage')}: pl name type")
                print(f"  {t('pl_types')}: favorites, history, mood, ai, tag:jazz, country:KR\n")
            continue

        # 플레이리스트 모드에서 선택
        if mode == "playlist":
            if cmd.startswith("-"):
                # 삭제
                if delete_playlist(cmd[1:]):
                    print(f"  ✗ {t('deleted')}\n")
                    show_playlists()
                continue
            # 재생 목록 표시
            pl_stations = get_playlist_stations(cmd)
            if pl_stations:
                stations = pl_stations
                print_stations(stations)
                mode = "list"
            else:
                print(f"  {t('invalid_num')}\n")
            continue

        # 메뉴
        if cmd == "m":
            mode = "menu"
            show_menu()
            continue

        # 장르 모드
        if cmd == "g":
            mode = "genre"
            show_genres()
            continue

        # 국가 모드
        if cmd == "c":
            mode = "country"
            show_countries()
            continue

        # 인기
        if cmd == "p":
            print(f"  {t('popular_loading')}...")
            stations = get_popular()
            print_stations(stations)
            if stations:
                mode = "list"
            continue

        # 고음질
        if cmd == "h":
            print(f"  {t('hq_loading')} (256k+)...")
            stations = get_high_quality()
            print_stations(stations)
            if stations:
                mode = "list"
            continue

        # 추천 (프리미엄)
        if cmd == "r":
            print(f"  {t('recommend_loading')}...")
            stations = get_premium()
            print_stations(stations)
            if stations:
                mode = "list"
            continue

        # AI 추천 (내 취향 기반)
        if cmd == "a":
            print(f"  {t('ai_recommend_loading')}...")
            stations = get_personalized_recommendations()
            print_stations(stations)
            if stations:
                mode = "list"
            continue

        # 분위기 추천 (시간대 기반)
        if cmd == "w":
            print(f"  {t('mood_recommend')} ({t('time_based')})...")
            stations = get_mood_recommendations()
            print_stations(stations)
            if stations:
                mode = "list"
            continue

        # 내 취향 분석
        if cmd == "t":
            show_my_taste()
            continue

        # 즐겨찾기 보기
        if cmd == "f":
            favs = print_favorites()
            if favs:
                stations = favs
                mode = "fav"
                print(f"  ({t('enter_num_play')}, -{t('enter_num_del')})")
            continue

        # 즐겨찾기 추가
        if cmd == "+" and current_station:
            if add_favorite(current_station):
                print(f"  ★ {t('added_fav')}: {current_station.get('name', '')}\n")
            else:
                print(f"  {t('already_fav')}\n")
            continue

        # 즐겨찾기 제거 (현재 재생 중인 방송)
        if cmd == "-" and current_station:
            url = current_station.get("url_resolved") or current_station.get("url", "")
            favs = load_favorites()
            new_favs = [f for f in favs if f.get("url") != url]
            if len(new_favs) < len(favs):
                save_favorites(new_favs)
                print(f"  ✗ {t('removed_fav')}: {current_station.get('name', '')}\n")
            else:
                print(f"  {t('no_fav')}\n")
            continue

        # 검색 모드
        if cmd == "/":
            mode = "search"
            print(f"  {t('enter_search')} ({t('enter_cancel')})")
            continue

        # 장르 선택
        if mode == "genre":
            if cmd in GENRES:
                tag, name_key = GENRES[cmd]
                print(f"  '{t(name_key)}' {t('searching_for')}...")
                stations = search_by_tag(tag)
                print_stations(stations)
                if stations:
                    mode = "list"
            else:
                # 직접 입력한 장르
                print(f"  '{cmd}' {t('searching_for')}...")
                stations = search_by_tag(cmd)
                print_stations(stations)
                if stations:
                    mode = "list"
            continue

        # 국가 선택
        if mode == "country":
            if cmd in COUNTRIES:
                code, name_key = COUNTRIES[cmd]
                display_name = t(name_key)
            else:
                code = cmd.upper()
                display_name = code
            print(f"  '{display_name}' {t('searching_for')}...")
            stations = search_by_country(code)
            print_stations(stations)
            if stations:
                mode = "list"
            continue

        # 검색
        if mode == "search":
            print(f"  '{cmd}' {t('searching_for')}...")
            stations = search_advanced(cmd)
            print_stations(stations)
            if stations:
                mode = "list"
            continue

        # 즐겨찾기 삭제 (-번호)
        if cmd.startswith("-") and cmd[1:].isdigit():
            idx = int(cmd[1:]) - 1
            removed = remove_favorite(idx)
            if removed:
                print(f"  ✗ {t('deleted')}: {removed.get('name', '')}\n")
                favs = print_favorites()
                stations = favs if favs else []
            else:
                print(f"  {t('invalid_num')}")
            continue

        # 번호로 재생
        if cmd.isdigit():
            idx = int(cmd) - 1
            if 0 <= idx < len(stations):
                # 이전 청취 기록 저장
                if PLAYER_PROC and current_station and play_start_time:
                    duration = int(time.time() - play_start_time)
                    add_history(current_station, duration)

                s = stations[idx]
                current_station = s
                url = s.get("url_resolved") or s.get("url")

                # DJ 먼저 소개 → 라디오 시작
                dj_announce_station(s)
                play(url, s.get("name", ""))
                play_start_time = time.time()

                # 재생 성공 시 DB에 저장 (API에서 가져온 것만)
                if s.get("source") == "api":
                    save_station_to_db(s)

                print(f"  {t('help_after_play')}")
                mode = "menu"  # 검색 가능하게 메뉴 모드로
            else:
                print(f"  {t('invalid_num')}")
            continue

        # 메뉴에서 바로 스마트 검색
        if mode == "menu" and len(cmd) > 0:
            print(f"  '{cmd}' {t('searching_for')}...")
            stations = search_advanced(cmd)
            print_stations(stations)
            if stations:
                mode = "list"
            continue

        print(f"  ? {t('help_hint')}: g={t('genre')}, c={t('country')}, p={t('popular')}, /={t('searching')}, s={t('stop')}, q={t('quit')}")

if __name__ == "__main__":
    # --cleanup: 죽은 방송 정리
    if len(sys.argv) > 1 and sys.argv[1] == "--cleanup":
        count = cleanup_dead_stations()
        print(f"죽은 방송 {count}개 삭제됨")
        sys.exit(0)

    # --db-stats: DB 통계
    if len(sys.argv) > 1 and sys.argv[1] == "--db-stats":
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM stations")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM stations WHERE is_alive = 1")
            alive = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM stations WHERE is_alive = 0")
            dead = cursor.fetchone()[0]
            conn.close()
            print(f"DB 통계: 전체 {total}개, 활성 {alive}개, 죽음 {dead}개")
        else:
            print("DB 파일 없음")
        sys.exit(0)

    main()
