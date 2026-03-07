#!/usr/bin/env python3
"""
Radio MCP Server - Internet radio search and playback
SQLite DB first, Radio Browser API fallback
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
import webbrowser
import sys
from typing import Any
from datetime import datetime

from mcp.server.fastmcp import FastMCP

# ============================================================
# Player Backend Abstraction
# ============================================================
# Priority: mpv > vlc > ffplay > browser
# ============================================================

PLAYER_BACKEND = None  # 'mpv', 'vlc', 'ffplay', 'browser'

def detect_player_backend():
    """Detect available player backend"""
    global PLAYER_BACKEND

    # 1. mpv (best)
    if shutil.which("mpv"):
        PLAYER_BACKEND = "mpv"
        return "mpv"

    # 2. VLC (widely installed)
    if shutil.which("vlc") or shutil.which("cvlc"):
        PLAYER_BACKEND = "vlc"
        return "vlc"

    # 3. ffplay (included with ffmpeg)
    if shutil.which("ffplay"):
        PLAYER_BACKEND = "ffplay"
        return "ffplay"

    # 4. Browser fallback (always available)
    PLAYER_BACKEND = "browser"
    return "browser"

# Detect backend on init
detect_player_backend()

# ============================================================
# Miniaudio player (used when mpv unavailable)
# ============================================================
class MiniaudioPlayer:
    """Miniaudio-based streaming player"""

    def __init__(self):
        self.stream_thread = None
        self.playing = False
        self.device = None

    def play(self, url):
        """Play URL stream"""
        self.stop()
        self.playing = True

        def stream_worker():
            try:
                import miniaudio
                import urllib.request

                # Open HTTP stream
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'RadioMCP/1.0',
                    'Icy-MetaData': '1'
                })
                response = urllib.request.urlopen(req, timeout=30)

                # Setup miniaudio decoder
                def read_data(num_bytes):
                    if not self.playing:
                        return b''
                    return response.read(num_bytes)

                # Play stream
                self.device = miniaudio.PlaybackDevice()
                stream = miniaudio.stream_any(
                    source=response,
                    source_format=miniaudio.FileFormat.MP3
                )
                self.device.start(stream)

                while self.playing:
                    time.sleep(0.1)

            except Exception as e:
                pass
            finally:
                self.playing = False
                if self.device:
                    self.device.close()

        self.stream_thread = threading.Thread(target=stream_worker, daemon=True)
        self.stream_thread.start()
        return True

    def stop(self):
        """Stop playback"""
        self.playing = False
        if self.device:
            try:
                self.device.close()
            except:
                pass
            self.device = None

    def is_playing(self):
        return self.playing

# Global miniaudio player instance
_miniaudio_player = None

def get_miniaudio_player():
    global _miniaudio_player
    if _miniaudio_player is None:
        _miniaudio_player = MiniaudioPlayer()
    return _miniaudio_player

# ============================================================
# VLC Player
# ============================================================
class VLCPlayer:
    """VLC-based player (using cvlc)"""

    def __init__(self):
        self.process = None
        self.pid_file = os.path.join(os.path.expanduser("~/.radiocli"), "vlc.pid")

    def play(self, url):
        """Play with VLC"""
        self.stop()
        try:
            # Use cvlc (console VLC)
            vlc_cmd = shutil.which("cvlc") or shutil.which("vlc")
            self.process = subprocess.Popen(
                [vlc_cmd, "--intf", "dummy", "--no-video", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setpgrp
            )
            with open(self.pid_file, 'w') as f:
                f.write(str(self.process.pid))
            return True
        except Exception:
            return False

    def stop(self):
        """Stop VLC"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except:
                try:
                    self.process.kill()
                except:
                    pass
            self.process = None
        # Stop via PID file
        if os.path.exists(self.pid_file):
            try:
                with open(self.pid_file) as f:
                    pid = int(f.read().strip())
                os.kill(pid, signal.SIGTERM)
            except:
                pass
            try:
                os.remove(self.pid_file)
            except:
                pass

    def is_playing(self):
        return self.process is not None and self.process.poll() is None

_vlc_player = None

def get_vlc_player():
    global _vlc_player
    if _vlc_player is None:
        _vlc_player = VLCPlayer()
    return _vlc_player

# ============================================================
# FFplay Player
# ============================================================
class FFplayPlayer:
    """ffplay-based player (included with ffmpeg)"""

    def __init__(self):
        self.process = None
        self.pid_file = os.path.join(os.path.expanduser("~/.radiocli"), "ffplay.pid")

    def play(self, url):
        """Play with ffplay"""
        self.stop()
        try:
            self.process = subprocess.Popen(
                ["ffplay", "-nodisp", "-loglevel", "quiet", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setpgrp
            )
            with open(self.pid_file, 'w') as f:
                f.write(str(self.process.pid))
            return True
        except Exception:
            return False

    def stop(self):
        """Stop ffplay"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except:
                try:
                    self.process.kill()
                except:
                    pass
            self.process = None
        # Stop via PID file
        if os.path.exists(self.pid_file):
            try:
                with open(self.pid_file) as f:
                    pid = int(f.read().strip())
                os.kill(pid, signal.SIGTERM)
            except:
                pass
            try:
                os.remove(self.pid_file)
            except:
                pass

    def is_playing(self):
        return self.process is not None and self.process.poll() is None

_ffplay_player = None

def get_ffplay_player():
    global _ffplay_player
    if _ffplay_player is None:
        _ffplay_player = FFplayPlayer()
    return _ffplay_player

# ============================================================
# Browser Player (last resort fallback)
# ============================================================
class BrowserPlayer:
    """Open stream in browser"""

    def __init__(self):
        self.current_url = None

    def play(self, url):
        """Open URL in browser"""
        self.current_url = url
        webbrowser.open(url)
        return True

    def stop(self):
        """Browser must be closed manually"""
        self.current_url = None
        return {"note": "Please close the browser tab manually"}

    def is_playing(self):
        return self.current_url is not None

_browser_player = None

def get_browser_player():
    global _browser_player
    if _browser_player is None:
        _browser_player = BrowserPlayer()
    return _browser_player

# Create MCP server
mcp = FastMCP("radio")

# Configuration
DATA_DIR = os.path.expanduser("~/.radiocli")
FAVORITES_FILE = os.path.join(DATA_DIR, "favorites.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
RECOGNIZED_FILE = os.path.join(DATA_DIR, "recognized_songs.json")
RECORD_FILE = os.path.join(DATA_DIR, "record.mp3")
MPV_SOCKET = os.path.join(DATA_DIR, "mpv.sock")
MPV_PID_FILE = os.path.join(DATA_DIR, "mpv.pid")  # Shared with CLI
LOCK_FILE = os.path.join(DATA_DIR, "server.lock")
API_BASE = "https://de1.api.radio-browser.info/json"

# G3 URL Validator API (optional, for detailed stream info)
G3_VALIDATOR_URL = os.environ.get("G3_VALIDATOR_URL", "http://g3:8100/api/validate")
G3_VALIDATOR_ENABLED = os.environ.get("G3_VALIDATOR_ENABLED", "false").lower() == "true"


def g3_validate_url(url: str, timeout: int = 5) -> dict:
    """
    Validate URL using G3 URL Validator API.
    Returns detailed stream info (bitrate, format, etc.)
    """
    if not G3_VALIDATOR_ENABLED:
        return {"valid": False, "error": "G3 validator disabled"}
    
    try:
        api_url = f"{G3_VALIDATOR_URL}?url={urllib.parse.quote(url)}"
        req = urllib.request.Request(api_url, headers={"User-Agent": "RadioMCP/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"valid": False, "error": str(e)}


def g3_batch_validate(urls: list, timeout: int = 10) -> list:
    """
    Batch validate URLs using G3 API.
    """
    if not G3_VALIDATOR_ENABLED:
        return [{"url": u, "valid": False, "error": "G3 validator disabled"} for u in urls]
    
    try:
        req = urllib.request.Request(
            f"{G3_VALIDATOR_URL.replace('/validate', '/validate/batch')}",
            data=json.dumps({"urls": urls, "timeout": timeout}).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "RadioMCP/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout + 5) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return [{"url": u, "valid": False, "error": str(e)} for u in urls]
ACOUSTID_API_KEY = os.environ.get("ACOUSTID_API_KEY", "vQEDUkpM7e")

# DB path (priority: local > package > project)
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATHS = [
    os.path.join(DATA_DIR, "radio_stations.db"),
    os.path.join(PACKAGE_DIR, "radio_stations.db"),  # DB in package
    os.path.expanduser("~/RadioCli/radio_stations.db"),
]

# Global state
current_station = None
player_proc = None
db_conn = None
sleep_timer = None  # Sleep timer
lock_fd = None  # Singleton lock file descriptor

LAST_STATION_FILE = os.path.join(DATA_DIR, "last_station.json")

import fcntl  # For file locking

def acquire_singleton_lock():
    """Acquire singleton lock - terminate existing process if running"""
    global lock_fd
    os.makedirs(DATA_DIR, exist_ok=True)

    lock_fd = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Lock acquired - record PID
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
        return True
    except BlockingIOError:
        # Another server running - force terminate
        try:
            with open(LOCK_FILE, 'r') as f:
                old_pid = int(f.read().strip())
            # Try SIGTERM
            try:
                os.kill(old_pid, signal.SIGTERM)
                time.sleep(0.3)
            except:
                pass
            # SIGKILL if still alive
            try:
                os.kill(old_pid, 0)  # Check if exists
                os.kill(old_pid, signal.SIGKILL)
                time.sleep(0.3)
            except ProcessLookupError:
                pass
            # Retry
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_fd.seek(0)
            lock_fd.truncate()
            lock_fd.write(str(os.getpid()))
            lock_fd.flush()
            return True
        except:
            return False

def release_singleton_lock():
    """Release singleton lock"""
    global lock_fd
    if lock_fd:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
            os.remove(LOCK_FILE)
        except:
            pass
        lock_fd = None

def kill_existing_mpv():
    """Stop existing mpv process (shared with CLI)"""
    # 1. Try IPC socket quit
    if os.path.exists(MPV_SOCKET):
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(1)
            sock.connect(MPV_SOCKET)
            sock.send(b'{"command": ["quit"]}\n')
            sock.close()
            time.sleep(0.5)
        except:
            pass

    # 2. Terminate via PID file
    if os.path.exists(MPV_PID_FILE):
        try:
            with open(MPV_PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.5)
            try:
                os.kill(pid, 0)  # Still alive?
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        except:
            pass
        try:
            os.remove(MPV_PID_FILE)
        except:
            pass

    # 3. Last resort: pkill radiocli mpv
    try:
        subprocess.run(["pkill", "-f", "mpv.*radiocli"], timeout=2)
        time.sleep(0.3)
    except:
        pass

    # 4. Clean up socket file
    if os.path.exists(MPV_SOCKET):
        try:
            os.remove(MPV_SOCKET)
        except:
            pass

def save_last_station():
    """Save last played station"""
    if current_station:
        try:
            with open(LAST_STATION_FILE, "w", encoding="utf-8") as f:
                json.dump(current_station, f, ensure_ascii=False)
        except:
            pass

def load_last_station():
    """Load last played station"""
    if os.path.exists(LAST_STATION_FILE):
        try:
            with open(LAST_STATION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return None

def cleanup():
    """Save state on exit (mpv keeps playing)"""
    global player_proc
    # Save last station
    save_last_station()
    # Don't kill mpv - keep playing after server restart
    # Only stop mpv when stop() is called
    player_proc = None
    # Release singleton lock
    release_singleton_lock()

# Register exit handler only (let anyio handle signals)
atexit.register(cleanup)
# Note: Don't override SIGTERM/SIGINT - anyio needs them for graceful shutdown
# The atexit handler will run cleanup on normal exit

# Watchdog: Monitor Claude Desktop in separate process
def start_mpv_watchdog():
    """Start watchdog process when mpv starts (cross-platform)"""
    import sys
    platform = sys.platform

    watchdog_script = f'''
import time, os, subprocess, signal, sys

mpv_pid_file = "{os.path.join(DATA_DIR, "mpv.pid")}"
mpv_sock = "{MPV_SOCKET}"
platform = "{platform}"

def is_claude_running():
    """Check if Claude Desktop is running (cross-platform)"""
    try:
        if platform == "darwin":  # macOS
            result = subprocess.run(
                ["osascript", "-e", 'tell application "System Events" to (name of processes) contains "Claude"'],
                capture_output=True, text=True
            )
            return "true" in result.stdout.lower()
        elif platform == "win32":  # Windows
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Claude.exe"],
                capture_output=True, text=True
            )
            return "Claude.exe" in result.stdout
        else:  # Linux
            result = subprocess.run(
                ["pgrep", "-f", "claude-desktop|Claude"],
                capture_output=True
            )
            return result.returncode == 0
    except:
        return True  # Assume running if check fails

def kill_mpv():
    """Stop mpv"""
    if os.path.exists(mpv_pid_file):
        try:
            with open(mpv_pid_file) as f:
                pid = int(f.read().strip())
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.5)
            try: os.kill(pid, signal.SIGKILL)
            except: pass
        except: pass
        try: os.remove(mpv_pid_file)
        except: pass
    if os.path.exists(mpv_sock):
        try: os.remove(mpv_sock)
        except: pass
    if platform != "win32":
        subprocess.run(["pkill", "-f", "mpv.*mpv.sock"], capture_output=True)
    else:
        subprocess.run(["taskkill", "/F", "/IM", "mpv.exe"], capture_output=True)

while True:
    time.sleep(5)
    if not is_claude_running():
        kill_mpv()
        break
'''
    # Kill existing watchdog
    subprocess.run(["pkill", "-f", "mpv_pid_file"], capture_output=True)
    # Start new watchdog (independent process)
    kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if platform != "win32":
        kwargs["start_new_session"] = True
    else:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(["python3", "-c", watchdog_script], **kwargs)

# Synonym mapping (tag expansion)
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
# Multilingual search mapping (v2.0)
# ============================================================

# Multilingual -> English tag mapping
LANG_MAP = {
    # Korean
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

    # Japanese
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

    # Chinese (Simplified)
    "爵士乐": "jazz", "爵士": "jazz", "古典音乐": "classical", "古典": "classical",
    "摇滚": "rock", "流行": "pop", "新闻": "news", "嘻哈": "hip hop",
    "电子": "electronic", "电子音乐": "electronic", "舞曲": "dance",
    "轻音乐": "easy listening", "休闲": "lounge", "咖啡": "cafe",
    "睡眠": "sleep", "冥想": "meditation", "学习": "study", "工作": "focus",
    "早晨": "morning", "夜晚": "night", "夏天": "summer", "冬天": "winter",
    "灵魂乐": "soul", "蓝调": "blues", "雷鬼": "reggae", "民谣": "folk",
    "金属": "metal", "朋克": "punk", "动漫": "anime", "游戏": "game",
    "华语": "chinese", "粤语": "cantonese", "国语": "mandarin",

    # Chinese (Traditional)
    "爵士樂": "jazz", "古典音樂": "classical", "搖滾": "rock", "流行音樂": "pop",
    "電子音樂": "electronic", "輕音樂": "easy listening",

    # Spanish
    "música clásica": "classical", "música pop": "pop", "música rock": "rock",
    "noticias": "news", "jazz latino": "latin jazz", "salsa": "salsa",
    "reggaeton": "reggaeton", "bachata": "bachata", "merengue": "merengue",
    "cumbia": "cumbia", "flamenco": "flamenco", "latina": "latin",
    "relajante": "relaxing", "dormir": "sleep", "estudiar": "study",

    # German
    "klassische musik": "classical", "nachrichten": "news", "schlager": "schlager",
    "volksmusik": "folk", "deutsche musik": "german",

    # French
    "musique classique": "classical", "musique pop": "pop", "actualités": "news",
    "chanson française": "chanson", "musique française": "french",

    # Portuguese
    "música brasileira": "brazilian", "samba": "samba", "forró": "forro",
    "sertanejo": "sertanejo", "mpb": "mpb", "axé": "axe",

    # Russian
    "джаз": "jazz", "классика": "classical", "рок": "rock", "поп": "pop",
    "новости": "news", "электронная": "electronic", "русская": "russian",

    # Arabic
    "جاز": "jazz", "كلاسيكي": "classical", "أخبار": "news",
    "موسيقى عربية": "arabic", "عربي": "arabic",

    # Hindi
    "जैज़": "jazz", "शास्त्रीय": "classical", "समाचार": "news",
    "बॉलीवुड": "bollywood", "हिंदी": "hindi",

    # Vietnamese
    "nhạc jazz": "jazz", "nhạc cổ điển": "classical", "tin tức": "news",
    "nhạc việt": "vietnamese", "nhạc trẻ": "vpop",

    # Thai
    "แจ๊ส": "jazz", "คลาสสิก": "classical", "ข่าว": "news",
    "เพลงไทย": "thai", "ลูกทุ่ง": "luk thung",

    # Indonesian
    "berita": "news", "musik indonesia": "indonesian", "dangdut": "dangdut",
}

# Compound genres (for token merge)
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

# Country name -> code mapping (for country-first sorting)
COUNTRY_NAMES = {
    # Korean
    "한국": "KR", "대한민국": "KR", "미국": "US", "일본": "JP", "중국": "CN",
    "영국": "GB", "프랑스": "FR", "독일": "DE", "이탈리아": "IT", "스페인": "ES",
    "캐나다": "CA", "호주": "AU", "브라질": "BR", "멕시코": "MX", "러시아": "RU",
    "인도": "IN", "태국": "TH", "베트남": "VN", "인도네시아": "ID", "필리핀": "PH",
    "대만": "TW", "홍콩": "HK", "싱가포르": "SG", "말레이시아": "MY",
    # English
    "korea": "KR", "korean": "KR", "usa": "US", "america": "US", "american": "US",
    "japan": "JP", "japanese": "JP", "china": "CN", "chinese": "CN",
    "uk": "GB", "british": "GB", "england": "GB", "france": "FR", "french": "FR",
    "germany": "DE", "german": "DE", "italy": "IT", "italian": "IT",
    "spain": "ES", "spanish": "ES", "canada": "CA", "canadian": "CA",
    "australia": "AU", "australian": "AU", "brazil": "BR", "brazilian": "BR",
    "mexico": "MX", "mexican": "MX", "russia": "RU", "russian": "RU",
    "india": "IN", "indian": "IN", "thailand": "TH", "thai": "TH",
    "vietnam": "VN", "vietnamese": "VN", "indonesia": "ID", "indonesian": "ID",
    "philippines": "PH", "filipino": "PH", "taiwan": "TW", "taiwanese": "TW",
    "hongkong": "HK", "singapore": "SG", "malaysia": "MY", "malaysian": "MY",
    # Japanese
    "韓国": "KR", "アメリカ": "US", "日本": "JP", "中国": "CN",
    "イギリス": "GB", "フランス": "FR", "ドイツ": "DE",
}

# Known tags list (for fuzzy search)
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

# Weather/season -> tag mapping
WEATHER_TAGS = {
    "rainy": ["jazz", "lounge", "piano", "ambient"],
    "sunny": ["pop", "bossa nova", "tropical", "summer"],
    "cloudy": ["indie", "acoustic", "folk", "ambient"],
    "snowy": ["classical", "christmas", "cozy", "piano"],
    "hot": ["tropical", "latin", "reggae", "summer"],
    "cold": ["jazz", "classical", "lounge", "cozy"],
}

# Time of day -> tag mapping
TIME_TAGS = {
    "morning": ["pop", "acoustic", "breakfast", "morning"],      # 6-10
    "daytime": ["pop", "rock", "hits", "energetic"],             # 10-17
    "evening": ["jazz", "lounge", "dinner", "relaxing"],         # 17-21
    "night": ["ambient", "chillout", "sleep", "lounge"],         # 21-6
}


# ============================================================
# Search engine helper functions (v2.0)
# ============================================================

def translate_query(query: str) -> str:
    """Convert multilingual query to English tags"""
    query_lower = query.lower().strip()

    # 1. Check exact mapping
    if query in LANG_MAP:
        return LANG_MAP[query]
    if query_lower in LANG_MAP:
        return LANG_MAP[query_lower]

    # 2. Convert each word
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
    """Calculate edit distance between two strings"""
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
    """Typo correction - return closest known tag"""
    query_lower = query.lower().strip()

    # Return as-is if exact match
    if query_lower in KNOWN_TAGS:
        return query_lower

    # Skip fuzzy for short words (<3 chars) to prevent fm->edm
    if len(query_lower) < 3:
        return query_lower

    # Exclude generic radio words from fuzzy
    SKIP_WORDS = {"radio", "fm", "am", "hd", "the", "and", "or", "with"}
    if query_lower in SKIP_WORDS:
        return query_lower

    # Find closest tag
    best_match = None
    best_distance = threshold + 1

    for tag in KNOWN_TAGS:
        # Skip tags too short or long
        if abs(len(tag) - len(query_lower)) > threshold:
            continue

        distance = levenshtein_distance(query_lower, tag)
        if distance < best_distance:
            best_distance = distance
            best_match = tag

    return best_match if best_match else query_lower


def merge_compound_tokens(tokens: list) -> list:
    """Merge compound genres from token list"""
    if len(tokens) < 2:
        return tokens

    result = []
    i = 0
    while i < len(tokens):
        merged = False

        # Check 3-word combinations
        if i + 2 < len(tokens):
            key3 = (tokens[i], tokens[i+1], tokens[i+2])
            if key3 in COMPOUND_GENRES:
                result.append(COMPOUND_GENRES[key3])
                i += 3
                merged = True
                continue

        # Check 2-word combinations
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
    Parse search query (with operators)

    Supported operators:
    - AND: default (space)
    - OR: '|' or 'OR'
    - NOT: '-' prefix
    - "exact": quotes for exact phrase

    Returns:
        {
            "must": [...],      # AND condition (all must match)
            "should": [...],    # OR condition (at least one)
            "must_not": [...],  # NOT condition (exclude)
            "exact": [...],     # Exact phrase
        }
    """
    result = {
        "must": [],
        "should": [],
        "must_not": [],
        "exact": [],
    }

    # Extract exact phrases in quotes
    import re
    exact_matches = re.findall(r'"([^"]+)"', query)
    for match in exact_matches:
        result["exact"].append(match.lower())
    query = re.sub(r'"[^"]+"', '', query)

    # Split by OR
    if ' OR ' in query or '|' in query:
        query = query.replace(' OR ', '|')
        or_parts = [p.strip() for p in query.split('|') if p.strip()]
        for part in or_parts:
            if part.startswith('-'):
                result["must_not"].append(part[1:].lower())
            else:
                result["should"].append(part.lower())
    else:
        # Split by space (AND)
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
    """Calculate station score"""
    score = 0.0

    # Base popularity score (log scale)
    import math
    votes = station.get("votes", 0)
    if votes > 0:
        score += math.log10(votes + 1)

    # Bitrate bonus
    bitrate = station.get("bitrate", 0)
    if bitrate >= 320:
        score += 3
    elif bitrate >= 256:
        score += 2
    elif bitrate >= 192:
        score += 1

    # Matching tags count bonus
    station_tags = station.get("tags", "").lower()
    match_count = sum(1 for tag in matched_tags if tag in station_tags)
    score += match_count * 2

    # Exact phrase match bonus
    for exact in query_parts.get("exact", []):
        if exact in station_tags or exact in station.get("name", "").lower():
            score += 5

    # must_not penalty
    for exclude in query_parts.get("must_not", []):
        if exclude in station_tags:
            score -= 100  # Effectively exclude

    return score


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def get_db():
    """SQLite DB connection (singleton)"""
    global db_conn
    if db_conn:
        return db_conn

    for path in DB_PATHS:
        if os.path.exists(path):
            db_conn = sqlite3.connect(path, check_same_thread=False)
            db_conn.row_factory = sqlite3.Row
            pass  # DB loaded
            return db_conn

    pass  # No DB
    return None


# ============================================================
# Memory index (ultra-fast search)
# ============================================================

# Global index
_stations_cache = None      # All stations list
_tag_index = None           # {tag: [indices...]}
_name_words_index = None    # {word: [indices...]}


def build_memory_index():
    """Load DB to memory and build index (once)"""
    global _stations_cache, _tag_index, _name_words_index

    if _stations_cache is not None:
        return  # Already loaded

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
            # Tag index
            tags = station.get("tags", "").lower()
            for tag in tags.split(","):
                tag = tag.strip()
                if tag:
                    if tag not in _tag_index:
                        _tag_index[tag] = []
                    _tag_index[tag].append(idx)

            # Name word index
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
    """Ultra-fast search by name"""
    build_memory_index()

    if not _stations_cache:
        return []

    query_lower = query.lower()
    query_words = query_lower.split()

    # 1. Exact name matching
    exact_matches = []
    partial_matches = []

    for idx, station in enumerate(_stations_cache):
        name_lower = station.get("name", "").lower()

        # Full query in name
        if query_lower in name_lower:
            exact_matches.append(idx)
        # All words in name
        elif all(w in name_lower for w in query_words):
            partial_matches.append(idx)

    result_indices = (exact_matches + partial_matches)[:limit]
    return [_stations_cache[i] for i in result_indices]


def fast_search_by_tag(tags: list, limit: int = 20) -> list:
    """Ultra-fast search by tag"""
    build_memory_index()

    if not _stations_cache or not _tag_index:
        return []

    # Collect indices for each tag
    all_indices = set()
    for tag in tags:
        tag_lower = tag.lower()
        # Exact match
        if tag_lower in _tag_index:
            all_indices.update(_tag_index[tag_lower])
        # Partial match (word in tag)
        else:
            for idx_tag, indices in _tag_index.items():
                if tag_lower in idx_tag or idx_tag in tag_lower:
                    all_indices.update(indices[:50])  # Limit partial matches

    # Sort by votes (already sorted, just get by index order)
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
    """Radio Browser API GET call"""
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
    """Get latest URL from API by name (handle token expiry)"""
    if not name:
        return ""
    encoded = urllib.parse.quote(name)
    results = api_get(f"stations/byname/{encoded}", {
        "limit": 5, "order": "clickcount", "reverse": "true", "lastcheckok": 1
    })
    # Exact match first
    for s in results:
        if s.get("name", "").lower() == name.lower():
            return s.get("url_resolved") or s.get("url", "")
    # If none, first result
    if results:
        return results[0].get("url_resolved") or results[0].get("url", "")
    return ""


# Blocklist (load from local file)
BLOCK_LIST = []
BLOCKED_URLS = set()
BLOCKED_UUIDS = set()

# Local blocklist.json path (in package or project root)
LOCAL_BLOCKLIST_PATHS = [
    os.path.join(PACKAGE_DIR, "blocklist.json"),
    os.path.expanduser("~/RadioCli/blocklist.json"),
]

# Remote blocklist URLs (GitHub -> Cloudflare fallback)
BLOCKLIST_URLS = [
    "https://raw.githubusercontent.com/dragonflydiy/radiomcp/main/blocklist.json",  # GitHub (primary)
    "https://radiomcp.pages.dev/blocklist.json",  # Cloudflare Pages (fallback)
]
REMOTE_BLOCKLIST_URL = BLOCKLIST_URLS[0]  # Backward compatibility

def load_local_blocklist():
    """Load from local blocklist.json"""
    global BLOCK_LIST, BLOCKED_URLS, BLOCKED_UUIDS
    for path in LOCAL_BLOCKLIST_PATHS:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                BLOCK_LIST = [b["pattern"] for b in data.get("blocked", [])]
                BLOCKED_URLS = set(data.get("blocked_urls", []))
                BLOCKED_UUIDS = set(data.get("blocked_uuids", []))
                return
            except Exception:
                pass

# Load local blocklist on startup
load_local_blocklist()

def fetch_remote_blocklist():
    """Fetch blocklist (GitHub -> Cloudflare fallback)"""
    global BLOCK_LIST, BLOCKED_URLS, BLOCKED_UUIDS

    data = None
    last_error = None

    # Try in order
    for url in BLOCKLIST_URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "RadioMCP/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                break  # Stop on success
        except Exception as e:
            last_error = e
            continue  # Try next URL

    if not data:
        return  # Use local only if all sources fail

    # Pattern block (name matching)
    remote_patterns = [b["pattern"] for b in data.get("blocked", [])]
    for p in remote_patterns:
        if p not in BLOCK_LIST:
            BLOCK_LIST.append(p)
    # URL block
    BLOCKED_URLS.update(data.get("blocked_urls", []))
    # UUID block
    BLOCKED_UUIDS.update(data.get("blocked_uuids", []))
    # Remove blocked stations from DB
    purge_blocked_from_db()

def purge_blocked_from_db():
    """Remove blocked stations from DB"""
    conn = get_db()
    if not conn:
        return
    try:
        cursor = conn.cursor()
        # Delete by name pattern
        for pattern in BLOCK_LIST:
            cursor.execute("DELETE FROM stations WHERE LOWER(name) LIKE ?", (f"%{pattern.lower()}%",))
        # Delete by UUID
        for uuid in BLOCKED_UUIDS:
            cursor.execute("DELETE FROM stations WHERE stationuuid = ?", (uuid,))
        # Delete by URL
        for url in BLOCKED_URLS:
            cursor.execute("DELETE FROM stations WHERE url = ? OR url_resolved = ?", (url, url))
        conn.commit()
    except Exception:
        pass

# Fetch remote blocklist on startup
fetch_remote_blocklist()

def sync_popular_stations():
    """Sync popular stations on startup (Radio Browser -> DB)"""
    db = get_db()
    if not db:
        return

    # Sync popular stations from major countries
    countries = ["KR", "US", "JP", "GB", "DE", "FR"]
    total_added = 0

    for country in countries:
        try:
            url = f"{API_BASE}/stations/bycountrycodeexact/{country}?limit=50&order=clickcount&reverse=true"
            req = urllib.request.Request(url, headers={"User-Agent": "RadioMCP/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                stations = json.loads(resp.read().decode())

            cursor = db.cursor()
            for s in stations:
                uuid = s.get("stationuuid", "")
                if not uuid:
                    continue

                # If exists, update URL only (token refresh)
                cursor.execute("SELECT url_resolved FROM stations WHERE stationuuid = ?", (uuid,))
                existing = cursor.fetchone()

                new_url = s.get("url_resolved") or s.get("url", "")
                if existing:
                    # Update if URL changed
                    if existing[0] != new_url:
                        cursor.execute("""
                            UPDATE stations SET url_resolved = ?, is_alive = 1 WHERE stationuuid = ?
                        """, (new_url, uuid))
                else:
                    # Add new
                    name = s.get("name", "")
                    if is_blocked(name, new_url, uuid):
                        continue

                    # Auto-set tags (Korean stations)
                    tags = s.get("tags", "")
                    if not tags and country == "KR":
                        if any(x in name for x in ["Classic", "클래식"]):
                            tags = "classical,클래식"
                        elif any(x in name for x in ["1R", "1Radio", "표준", "뉴스", "News"]):
                            tags = "news,talk,뉴스"
                        elif any(x in name for x in ["Cool", "FM4U", "Power", "Love"]):
                            tags = "music,pop,kpop"
                        elif "FM" in name:
                            tags = "music,pop"

                    cursor.execute("""
                        INSERT OR IGNORE INTO stations
                        (stationuuid, name, url, url_resolved, country, countrycode, tags, bitrate, votes, clickcount, is_alive)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """, (
                        uuid, name, s.get("url", ""), new_url,
                        s.get("country", ""), country, tags,
                        s.get("bitrate", 0), s.get("votes", 0), s.get("clickcount", 0)
                    ))
                    total_added += 1

            db.commit()
        except Exception:
            pass

# Sync popular stations on startup (called from main)

def is_blocked(name: str, url: str = "", uuid: str = "") -> bool:
    """Check blocklist (name, URL, UUID)"""
    if not name and not url and not uuid:
        return False
    # UUID block
    if uuid and uuid in BLOCKED_UUIDS:
        return True
    # URL block
    if url and url in BLOCKED_URLS:
        return True
    # Name pattern block
    if name:
        name_lower = name.lower()
        if any(b.lower() in name_lower for b in BLOCK_LIST):
            return True
    return False


def format_station(s) -> dict:
    """Format station info (dict or sqlite Row). None if blocked"""
    if isinstance(s, sqlite3.Row):
        s = dict(s)
    name = s.get("name", "Unknown")
    url = s.get("url_resolved") or s.get("url", "")
    uuid = s.get("stationuuid", "")
    if is_blocked(name, url, uuid):
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
    """Format multiple stations (filter blocked)"""
    return [s for s in (format_station(x) for x in items) if s]


def expand_tags(query: str) -> list:
    """Expand query to multiple tags (compound + synonyms)"""
    # Split by space
    words = query.lower().strip().split()
    all_tags = set()

    # Include original query
    all_tags.add(query.lower().strip())

    # Expand synonyms for each word
    for word in words:
        all_tags.add(word)
        if word in TAG_SYNONYMS:
            all_tags.update(TAG_SYNONYMS[word])

    # Check 2-word combos (e.g. "bossa nova")
    if len(words) >= 2:
        for i in range(len(words) - 1):
            combo = f"{words[i]} {words[i+1]}"
            all_tags.add(combo)
            if combo in TAG_SYNONYMS:
                all_tags.update(TAG_SYNONYMS[combo])

    return list(all_tags)


def get_time_of_day() -> str:
    """Return current time slot"""
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
    """Search from DB"""
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
        pass  # DB error
        return []


def db_search_country(code: str, limit: int = 20) -> list:
    """Search by country from DB"""
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
        pass  # DB error
        return []


def db_get_popular(limit: int = 20) -> list:
    """Popular stations from DB"""
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
        pass  # DB error
        return []


def mark_station_dead(url: str):
    """Mark station as dead"""
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
        pass  # DB update error


def is_valid_station(station: dict) -> bool:
    """Validate if station can be added to DB"""
    url = station.get("url_resolved") or station.get("url", "")

    # Exclude URLs with token/session params
    if "?" in url or "&" in url:
        return False

    # Exclude suspicious domains
    blocked_domains = [
        "duckdns.org", "no-ip.org", "ddns.net", "iptime.org",
        "zstream.win", "bsod.kr", "localhost", "127.0.0.1"
    ]
    url_lower = url.lower()
    for domain in blocked_domains:
        if domain in url_lower:
            return False

    # Exclude direct IP addresses
    import re
    if re.search(r"https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", url_lower):
        return False

    # Minimum quality criteria
    if station.get("votes", 0) < 5:
        return False

    return True


def add_station_to_db(station: dict):
    """Add new station to DB (if validation passes)"""
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
        # print(f"Added to DB: {station.get('name')}", flush=True)
    except Exception as e:
        pass  # DB insert error


def db_advanced_search(
    tags: list = None,
    country: str = None,
    language: str = None,
    min_bitrate: int = 0,
    codec: str = None,
    limit: int = 50
) -> list:
    """Search with compound filters from DB"""
    db = get_db()
    if not db:
        return []

    try:
        cursor = db.cursor()
        conditions = ["(is_alive = 1 OR is_alive IS NULL)"]
        params = []

        # Tag filter (OR)
        if tags:
            tag_conditions = []
            for tag in tags:
                tag_conditions.append("tags LIKE ?")
                params.append(f"%{tag}%")
            conditions.append(f"({' OR '.join(tag_conditions)})")

        # Country filter
        if country:
            conditions.append("countrycode = ?")
            params.append(country.upper())

        # Language filter
        if language:
            conditions.append("language LIKE ?")
            params.append(f"%{language}%")

        # Bitrate filter
        if min_bitrate > 0:
            conditions.append("bitrate >= ?")
            params.append(min_bitrate)

        # Codec filter
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
        pass  # DB search error
        return []


@mcp.tool()
def search(query: str, limit: int = 20) -> list[dict]:
    """
    Search radio stations by keyword. Fast local DB search (~5ms).

    SEARCH TIPS:
    - Genre: jazz, rock, classical, electronic, lounge, ambient, news, talk
    - Combine terms: "smooth jazz", "korean pop", "japanese news"
    - Station names: "BBC", "NPR", "KBS"
    - For country-specific: use search_by_country(country_code)
    - For high quality: use advanced_search(min_bitrate=192)
    - For mood-based: use recommend(mood)

    EXPAND SEARCH: If few results, try related terms:
    - jazz → smooth jazz, bebop, swing
    - news → talk, information
    - relaxing → lounge, ambient, chillout

    Multilingual supported: 재즈, ジャズ, 爵士 all work.

    Args:
        query: Search term (genre, station name, keyword)
        limit: Number of results (default 20)

    Returns:
        List of stations with name, url, country, tags, bitrate
    """
    # Detect country name (korea, japan, etc.)
    detected_country = None
    query_lower = query.lower()
    for name, code in COUNTRY_NAMES.items():
        if name in query_lower:
            detected_country = code
            break

    name_results = []
    tag_results = []
    country_results = []
    seen_urls = set()

    # 1. Search by name first (most accurate)
    for r in fast_search_by_name(query, limit):
        if r["url"] not in seen_urls:
            seen_urls.add(r["url"])
            r["source"] = "db"
            r["match_type"] = "name"
            name_results.append(r)

    # Return early if name match sufficient (skip tag search)
    if len(name_results) >= limit:
        return name_results[:limit]

    # 2. Multilingual + tag search (if name match insufficient)
    translated = translate_query(query)
    words = translated.lower().split()
    corrected_words = [fuzzy_match(w) for w in words]
    merged = merge_compound_tokens(corrected_words)

    # Expand synonyms (genre queries only)
    # Skip tag expansion for generic words (fm, radio, beach)
    SKIP_TAG_EXPAND = {"fm", "am", "radio", "beach", "music", "the", "and", "or"}
    all_tags = []
    for word in merged:
        if word.lower() not in SKIP_TAG_EXPAND:
            all_tags.append(word)
            if word in TAG_SYNONYMS:
                all_tags.extend(TAG_SYNONYMS[word][:2])

    # 2-1. If country detected, search that country first (priority!)
    if detected_country:
        # Search country + tag/name combo
        db = get_db()
        if db:
            try:
                cursor = db.cursor()
                # Search both original + translated tags
                original_words = [w for w in query.split() if w.lower() not in COUNTRY_NAMES]
                search_terms = list(set(original_words + [t for t in all_tags if t.lower() not in COUNTRY_NAMES]))

                if search_terms:
                    # Search in tags OR name
                    conditions = []
                    params = []
                    for term in search_terms:
                        conditions.append("(LOWER(tags) LIKE ? OR LOWER(name) LIKE ?)")
                        params.extend([f"%{term.lower()}%", f"%{term.lower()}%"])

                    sql = f"""
                        SELECT * FROM stations
                        WHERE countrycode = ? AND (is_alive = 1 OR is_alive IS NULL)
                        AND ({' OR '.join(conditions)})
                        ORDER BY votes DESC, clickcount DESC
                        LIMIT ?
                    """
                    cursor.execute(sql, [detected_country] + params + [limit])
                    for r in format_stations(cursor.fetchall()):
                        if r["url"] not in seen_urls:
                            seen_urls.add(r["url"])
                            r["source"] = "db"
                            r["match_type"] = "country_tag"
                            country_results.append(r)
            except Exception:
                pass

    # Search only if tags exist (when country results insufficient)
    if all_tags and len(country_results) < limit // 2:
        for r in fast_search_by_tag(all_tags, limit):
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                r["source"] = "db"
                r["match_type"] = "tag"
                tag_results.append(r)

    # Return country results first if available
    if country_results:
        # Country matches first, fill with name/tag matches if needed
        remaining = limit - len(country_results)
        if remaining > 0:
            # Add name matches (country filter)
            for r in name_results:
                if r.get("countrycode", "").upper() == detected_country and r["url"] not in seen_urls:
                    country_results.append(r)
                    if len(country_results) >= limit:
                        break
        country_results.sort(key=lambda x: x.get("votes", 0), reverse=True)
        return country_results[:limit]

    # Name matches first + fill with tag matches
    all_results = name_results + tag_results

    # 3. API search (only if no name match and results insufficient)
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

    # Sort: country match > name match > votes
    def sort_key(r):
        country_match = 1 if detected_country and r.get("countrycode", "").upper() == detected_country else 0
        name_match = 1 if r.get("match_type") == "name" else 0
        votes = r.get("votes", 0)
        return (country_match, name_match, votes)

    all_results.sort(key=sort_key, reverse=True)
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

    # 1. Query processing
    if query:
        # Multilingual translation
        translated = translate_query(query)

        # Parse search operators
        parsed = parse_search_query(translated)

        # Fuzzy matching + compound word merge
        must_tags = []
        for term in parsed["must"]:
            corrected = fuzzy_match(term)
            must_tags.append(corrected)

        # Merge compound words
        merged = merge_compound_tokens(must_tags)

        # Expand synonyms
        for tag in merged:
            search_tags.append(tag)
            if tag in TAG_SYNONYMS:
                search_tags.extend(TAG_SYNONYMS[tag][:3])

        # should (OR) condition
        for term in parsed["should"]:
            corrected = fuzzy_match(term)
            search_tags.append(corrected)

        # exact condition (filter later)
        exact_phrases = parsed["exact"]

        # must_not condition (filter later)
        exclude_terms = parsed["must_not"]
    else:
        exact_phrases = []
        exclude_terms = []

    # 2. Process tag parameters
    if tags:
        for tag in tags.split(","):
            tag = tag.strip().lower()
            if tag:
                search_tags.append(tag)

    # 3. DB search
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
            # exact phrase filter
            if exact_phrases:
                station_text = f"{r.get('name', '')} {r.get('tags', '')}".lower()
                if not all(phrase in station_text for phrase in exact_phrases):
                    continue

            # exclude filter
            if exclude_terms:
                station_tags = r.get("tags", "").lower()
                if any(term in station_tags for term in exclude_terms):
                    continue

            seen_urls.add(r["url"])
            r["source"] = "db"
            all_results.append(r)

    # 4. API search (if results insufficient)
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
                    # Force country filter (API may ignore)
                    if country and s.get("countrycode", "").upper() != country.upper():
                        continue

                    station = format_station(s)
                    if not station:
                        continue

                    # exact/exclude filter
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

    # 5. Sorting
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

    # 1. Search DB (verified stations)
    db_results = db_search_country(country_code, limit)
    for r in db_results:
        if r["url"] not in seen_urls:
            seen_urls.add(r["url"])
            r["source"] = "db"
            all_results.append(r)

    # 2. Radio Browser API (latest results)
    code = urllib.parse.quote(country_code.upper())
    api_results = api_get(f"stations/bycountrycodeexact/{code}", {
        "limit": limit,
        "order": "clickcount",
        "reverse": "true",
        "lastcheckok": 1
    })

    # Merge API results (force country filter)
    for s in api_results:
        url = s.get("url_resolved") or s.get("url", "")
        if url and url not in seen_urls:
            # Verify country code (API may ignore)
            if s.get("countrycode", "").upper() != country_code.upper():
                continue
            station = format_station(s)
            if not station:
                continue
            seen_urls.add(url)
            station["source"] = "api"
            all_results.append(station)
            # Save only valid stations to DB
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
    # Language code -> full name mapping
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

    # DB search
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
                if r and r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    r["source"] = "db"
                    all_results.append(r)
        except Exception as e:
            pass  # DB error

    # API search (if results insufficient)
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
                if station:
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
    # 1. Get from DB
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

    # Stop existing playback
    stop()

    # Get latest URL from API (handle token expiry)
    play_url = url
    url_refreshed = False
    if name:
        fresh_url = get_fresh_url(name)
        if fresh_url:
            play_url = fresh_url
            url_refreshed = (fresh_url != url)

    # Play by backend
    try:
        if PLAYER_BACKEND == "mpv":
            # === mpv backend ===
            kill_existing_mpv()

            mpv_log = open(os.path.join(DATA_DIR, "mpv.log"), "w")
            player_proc = subprocess.Popen(
                ["mpv", "--no-video", "--no-terminal",
                 "--cache=yes",
                 "--cache-secs=30",
                 "--demuxer-max-bytes=50M",
                 "--demuxer-readahead-secs=20",
                 "--stream-buffer-size=1M",
                 "--network-timeout=30",
                 "--stream-lavf-o=reconnect=1,reconnect_streamed=1,reconnect_delay_max=5",
                 f"--input-ipc-server={MPV_SOCKET}", play_url],
                stdout=subprocess.DEVNULL,
                stderr=mpv_log,
                preexec_fn=os.setpgrp
            )

            with open(MPV_PID_FILE, 'w') as f:
                f.write(str(player_proc.pid))

            start_mpv_watchdog()

            time.sleep(1)
            if player_proc.poll() is not None:
                mark_station_dead(url)
                return {"status": "error", "message": "Stream failed to start"}

        elif PLAYER_BACKEND == "vlc":
            # === VLC backend ===
            player = get_vlc_player()
            if not player.play(play_url):
                return {"status": "error", "message": "VLC failed to start"}
            time.sleep(1)
            if not player.is_playing():
                mark_station_dead(url)
                return {"status": "error", "message": "Stream failed to start"}

        elif PLAYER_BACKEND == "ffplay":
            # === ffplay backend ===
            player = get_ffplay_player()
            if not player.play(play_url):
                return {"status": "error", "message": "ffplay failed to start"}
            time.sleep(1)
            if not player.is_playing():
                mark_station_dead(url)
                return {"status": "error", "message": "Stream failed to start"}

        elif PLAYER_BACKEND == "browser":
            # === Browser backend ===
            player = get_browser_player()
            player.play(play_url)
            # Browser cannot confirm playback

        else:
            return {"status": "error", "message": f"Unknown player backend: {PLAYER_BACKEND}"}

        # Get station details from DB
        station_info = {"name": name, "url": play_url}
        db = get_db()
        if db and name:
            try:
                cursor = db.cursor()
                cursor.execute(
                    "SELECT country, countrycode, tags, bitrate, votes FROM stations WHERE name = ? LIMIT 1",
                    (name,)
                )
                row = cursor.fetchone()
                if row:
                    station_info["country"] = row[0] or ""
                    station_info["countrycode"] = row[1] or ""
                    station_info["tags"] = row[2] or ""
                    station_info["bitrate"] = row[3] or 0
                    station_info["votes"] = row[4] or 0
            except:
                pass

        current_station = station_info
        save_last_station()  # Save immediately (for resume)

        # Return detailed info for AI
        result = {
            "status": "playing",
            "name": name,
            "url": play_url,
            "country": station_info.get("country", ""),
            "countrycode": station_info.get("countrycode", ""),
            "tags": station_info.get("tags", ""),
            "bitrate": station_info.get("bitrate", 0),
            "votes": station_info.get("votes", 0),
            "tip": "You can describe: genre, country, audio quality to the user"
        }
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

    result = {"status": "stopped", "backend": PLAYER_BACKEND}

    if PLAYER_BACKEND == "mpv":
        kill_existing_mpv()
        player_proc = None
    elif PLAYER_BACKEND == "vlc":
        player = get_vlc_player()
        player.stop()
    elif PLAYER_BACKEND == "ffplay":
        player = get_ffplay_player()
        player.stop()
    elif PLAYER_BACKEND == "browser":
        player = get_browser_player()
        player.stop()
        result["note"] = "Please close the browser tab manually"

    current_station = None
    return result


@mcp.tool()
def get_player_backend() -> dict:
    """
    Get current player backend info.

    Returns:
        Current backend and available options
    """
    available = []
    install_guide = []

    if shutil.which("mpv"):
        available.append("mpv")
    else:
        install_guide.append("mpv: brew install mpv (macOS) / apt install mpv (Linux)")

    if shutil.which("vlc") or shutil.which("cvlc"):
        available.append("vlc")
    else:
        install_guide.append("vlc: brew install vlc (macOS) / apt install vlc (Linux)")

    if shutil.which("ffplay"):
        available.append("ffplay")
    else:
        install_guide.append("ffplay: brew install ffmpeg (macOS) / apt install ffmpeg (Linux)")

    available.append("browser")  # Always available

    result = {
        "current": PLAYER_BACKEND,
        "available": available,
        "recommendation": available[0] if available else "browser"
    }

    # Show install guide if only browser available
    if len(available) == 1:
        result["install_guide"] = install_guide
        result["note"] = "Install mpv, vlc, or ffmpeg for better playback quality"

    return result


@mcp.tool()
def set_player_backend(backend: str) -> dict:
    """
    Set player backend.

    Args:
        backend: 'mpv', 'vlc', 'ffplay', or 'browser'

    Returns:
        New backend status
    """
    global PLAYER_BACKEND

    valid_backends = ["mpv", "vlc", "ffplay", "browser"]
    if backend not in valid_backends:
        return {"status": "error", "message": f"Invalid backend. Choose from: {valid_backends}"}

    # Check backend availability
    if backend == "mpv" and not shutil.which("mpv"):
        return {"status": "error", "message": "mpv not installed. Install: brew install mpv (macOS) / apt install mpv (Linux)"}
    if backend == "vlc" and not (shutil.which("vlc") or shutil.which("cvlc")):
        return {"status": "error", "message": "VLC not installed. Install: brew install vlc (macOS) / apt install vlc (Linux)"}
    if backend == "ffplay" and not shutil.which("ffplay"):
        return {"status": "error", "message": "ffplay not installed. Install: brew install ffmpeg (macOS) / apt install ffmpeg (Linux)"}

    PLAYER_BACKEND = backend
    return {"status": "ok", "backend": PLAYER_BACKEND}


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
    """Record audio from stream (using ffmpeg)"""
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
    """Recognize song with AcoustID + Chromaprint"""
    if not shutil.which("fpcalc"):
        return None

    try:
        # Generate audio fingerprint
        result = subprocess.run(
            ["fpcalc", "-json", audio_file],
            capture_output=True, text=True, timeout=30
        )
        fp_data = json.loads(result.stdout)
        fingerprint = fp_data.get("fingerprint", "")
        duration = int(fp_data.get("duration", 0))

        if not fingerprint:
            return None

        # Query AcoustID API
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
    """Speech recognition with Whisper"""
    try:
        # Try mlx-whisper (Apple Silicon)
        result = subprocess.run(
            ["mlx_whisper", audio_file, "--language", "auto", "--output-format", "json"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0 and result.stdout.strip():
            return {"transcription": result.stdout.strip(), "method": "mlx-whisper"}
    except:
        pass

    try:
        # Try openai-whisper
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

    # 1. Check metadata first (fastest)
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

    # 2. Record audio
    if not shutil.which("ffmpeg"):
        return {"error": "ffmpeg_not_installed", "hint": "brew install ffmpeg"}

    if not record_stream(url, duration):
        return {"error": "recording_failed"}

    # 3. Try AcoustID
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

    # 4. Try Whisper
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
    """Save recognition result"""
    songs = load_json(RECOGNIZED_FILE)
    result["recognized_at"] = datetime.now().isoformat()
    songs.append(result)
    save_json(RECOGNIZED_FILE, songs[-100:])  # Keep last 100


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
def play_favorite(index: int = 0) -> dict:
    """
    Play a station from favorites.

    Args:
        index: Index of the favorite station (0-based, default: 0 = first)

    Returns:
        Playback status
    """
    favorites = load_json(FAVORITES_FILE)

    if not favorites:
        return {"status": "error", "message": "No favorites yet"}

    if not 0 <= index < len(favorites):
        return {"status": "error", "message": f"Invalid index. You have {len(favorites)} favorites (0-{len(favorites)-1})"}

    station = favorites[index]
    url = station.get("url_resolved") or station.get("url")
    name = station.get("name", "Unknown")

    result = play(url)
    if result.get("status") == "playing":
        return {
            "status": "playing",
            "index": index,
            "name": name,
            "url": url
        }
    return result


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
        # DB search
        db_results = db_search(tag, "tags", 15)
        for r in db_results:
            if r["url"] not in seen:
                seen.add(r["url"])
                r["source"] = "db"
                all_results.append(r)

        # API search
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
        # Prioritize old verified or unverified stations
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

    # Get from API
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

            # Validate
            if not is_valid_station(s):
                skipped += 1
                continue

            # Check if in DB
            cursor.execute("SELECT stationuuid, url_resolved FROM stations WHERE stationuuid = ?", (uuid,))
            existing = cursor.fetchone()

            if not existing:
                # Add new
                add_station_to_db(s)
                new_count += 1
            elif existing[1] != url:
                # URL changed - update
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

    # Cancel existing timer
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

    # If time passed, set for tomorrow
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

    # Get current station tags
    db = get_db()
    if db:
        cursor = db.cursor()
        cursor.execute("SELECT tags FROM stations WHERE url = ? OR url_resolved = ?",
                      (current_station.get("url"), current_station.get("url")))
        row = cursor.fetchone()
        if row and row[0]:
            tags = row[0].split(",")
            if tags:
                # Search by first tag
                main_tag = tags[0].strip()
                results = search(main_tag, limit + 1)
                # Exclude current station
                return [r for r in results if r["url"] != current_station.get("url")][:limit]

    return []


@mcp.tool()
def recommend_by_weather(city: str = "") -> dict:
    """
    Recommend stations based on current weather.

    Args:
        city: City name (auto-detect from IP if empty)

    Returns:
        Weather-based recommendations
    """
    lat, lon = 37.5665, 126.978  # Seoul default
    
    # Get location from IP (ip-api.com: 45 req/min free)
    try:
        req = urllib.request.Request("http://ip-api.com/json/?fields=city,lat,lon", 
                                     headers={"User-Agent": "RadioMCP/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            loc_data = json.loads(resp.read().decode())
            if not city:
                city = loc_data.get("city", "Seoul")
            lat = loc_data.get("lat", lat)
            lon = loc_data.get("lon", lon)
    except:
        if not city:
            city = "Seoul"
    
    # Open-Meteo API (free, no API key, 10k req/day)
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        req = urllib.request.Request(url, headers={"User-Agent": "RadioMCP/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        current = data.get("current_weather", {})
        weather_code = int(current.get("weathercode", 0))
        temp = current.get("temperature", 20)
        is_day = current.get("is_day", 1)

        # WMO Weather codes -> mood
        # 0: Clear, 1-3: Cloudy, 45-48: Fog
        # 51-67: Drizzle/Rain, 71-77: Snow, 80-82: Showers, 85-86: Snow showers
        # 95-99: Thunderstorm
        if weather_code in [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82]:
            mood = "rainy"
        elif weather_code in [71, 73, 75, 77, 85, 86]:
            mood = "snowy"
        elif weather_code in [95, 96, 99]:
            mood = "stormy"
        elif weather_code == 0:
            mood = "sunny" if temp > 20 else ("cold" if temp < 10 else "clear")
        elif weather_code in [1, 2, 3]:
            mood = "cloudy"
        elif weather_code in [45, 48]:
            mood = "foggy"
        else:
            mood = "cloudy"

        # Temperature adjustment
        if temp > 28:
            mood = "hot"
        elif temp < 0:
            mood = "cold"

        # Night time adjustment
        if not is_day and mood in ["sunny", "clear"]:
            mood = "night"

        tags = WEATHER_TAGS.get(mood, ["pop", "jazz"])

        # Search
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
            "temp_c": round(temp, 1),
            "stations": all_results[:10]
        }
    except Exception as e:
        # Fallback: time-based recommendation
        try:
            time_result = recommend_by_time()
            fallback_stations = time_result.get("stations", [])
        except:
            fallback_stations = []
        return {
            "city": city,
            "weather": "unknown",
            "temp_c": None,
            "error": str(e),
            "stations": fallback_stations
        }


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

    # Tag weights (duration based)
    tag_weights = {}

    # Time of day preferences
    time_prefs = {
        "morning": {},    # 6-10
        "daytime": {},    # 10-17
        "evening": {},    # 17-21
        "night": {},      # 21-6
    }

    # Day of week preferences
    day_prefs = {i: {} for i in range(7)}  # 0=Monday

    total_duration = 0
    total_listens = len(history)

    for entry in history:
        tags_str = entry.get("tags", "")
        duration = entry.get("duration", 60)  # Default 1 min
        timestamp = entry.get("timestamp", "")

        total_duration += duration

        # Parse tags
        tags = [t.strip().lower() for t in tags_str.split(",") if t.strip()]
        if not tags:
            continue

        # Duration weight (in minutes, max 10)
        weight = min(duration / 60, 10)

        # Parse time
        try:
            dt = datetime.fromisoformat(timestamp)
            hour = dt.hour
            weekday = dt.weekday()

            # Determine time slot
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
            # Total weight
            tag_weights[tag] = tag_weights.get(tag, 0) + weight

            # By time slot
            time_prefs[time_slot][tag] = time_prefs[time_slot].get(tag, 0) + weight

            # By day
            day_prefs[weekday][tag] = day_prefs[weekday].get(tag, 0) + weight

    # Sort
    top_tags = sorted(tag_weights.items(), key=lambda x: -x[1])[:10]

    # Top tags by time slot
    time_top = {}
    for slot, tags in time_prefs.items():
        if tags:
            time_top[slot] = sorted(tags.items(), key=lambda x: -x[1])[:5]

    # Top tags by day
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
def personalized_recommend(limit: int = 10) -> dict:
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
        # If no history, recommend by time slot
        return recommend_by_time()

    # Current context
    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    # Time slot
    if 6 <= hour < 10:
        time_slot = "morning"
    elif 10 <= hour < 17:
        time_slot = "daytime"
    elif 17 <= hour < 21:
        time_slot = "evening"
    else:
        time_slot = "night"

    # Collect tags (priority: slot+day > slot > all)
    recommended_tags = []

    # 1. Preferred tags for this day
    day_prefs = profile.get("day_preferences", {}).get(day_names[weekday], [])
    for tag, _ in day_prefs[:2]:
        recommended_tags.append(tag)

    # 2. Preferred tags for this time slot
    time_prefs = profile.get("time_preferences", {}).get(time_slot, [])
    for tag, _ in time_prefs[:3]:
        if tag not in recommended_tags:
            recommended_tags.append(tag)

    # 3. Overall preferred tags
    for tag, _ in profile.get("top_tags", [])[:5]:
        if tag not in recommended_tags:
            recommended_tags.append(tag)

    # Search
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


@mcp.tool()
def get_blocklist() -> dict:
    """
    Get current blocklist status.

    Returns:
        Blocklist patterns, URLs, UUIDs and source URL
    """
    return {
        "patterns": BLOCK_LIST,
        "blocked_urls": list(BLOCKED_URLS),
        "blocked_uuids": list(BLOCKED_UUIDS),
        "sources": BLOCKLIST_URLS
    }


@mcp.tool()
def refresh_blocklist() -> dict:
    """
    Refresh blocklist from GitHub and purge blocked stations from DB.

    Returns:
        Refresh status
    """
    old_count = len(BLOCK_LIST) + len(BLOCKED_URLS) + len(BLOCKED_UUIDS)
    fetch_remote_blocklist()
    new_count = len(BLOCK_LIST) + len(BLOCKED_URLS) + len(BLOCKED_UUIDS)
    return {
        "status": "refreshed",
        "patterns": len(BLOCK_LIST),
        "blocked_urls": len(BLOCKED_URLS),
        "blocked_uuids": len(BLOCKED_UUIDS),
        "new_entries": new_count - old_count
    }


# ============================================================
# AI Helper Tools - Easy for AI to use
# ============================================================

@mcp.tool()
def get_radio_guide() -> dict:
    """
    IMPORTANT: Call this first when user asks about radio.
    Returns complete guide for AI to use radio tools effectively.

    Returns:
        Guide with available tools, search tips, examples
    """
    return {
        "overview": "Internet radio with 24,000+ stations from 197 countries",
        "quick_start": [
            "1. search('jazz') → find jazz stations",
            "2. play(url, name) → start playback",
            "3. now_playing() → see current song",
            "4. stop() → stop playback"
        ],
        "search_tools": {
            "search(query)": "General keyword search (genre, name, etc.)",
            "search_by_country(code)": "Country-specific (KR, US, JP, DE, FR...)",
            "advanced_search(...)": "Filters: country + tag + bitrate",
            "get_popular()": "Top stations by popularity",
            "recommend(mood)": "Mood-based: relaxing, energetic, focus, sleep"
        },
        "playback_tools": {
            "play(url, name)": "Start playing (auto-refreshes URL)",
            "stop()": "Stop playback",
            "resume()": "Resume last station",
            "now_playing()": "Current song info",
            "set_volume(0-100)": "Adjust volume"
        },
        "user_tools": {
            "add_favorite(station)": "Save to favorites",
            "get_favorites()": "List favorites",
            "get_history()": "Listening history"
        },
        "search_tips": {
            "genres": ["jazz", "rock", "classical", "electronic", "pop", "lounge", "ambient", "news", "talk"],
            "moods": ["relaxing", "energetic", "focus", "sleep", "romantic", "workout"],
            "quality": "Use advanced_search(min_bitrate=192) for HQ",
            "multilingual": "Korean(재즈), Japanese(ジャズ), Chinese(爵士) supported"
        }
    }


@mcp.tool()
def expand_search(query: str) -> dict:
    """
    Get related search terms to expand search results.
    Use when initial search returns few results.

    Args:
        query: Original search term

    Returns:
        Related terms to try
    """
    expansions = {
        # Genres
        "jazz": ["smooth jazz", "bebop", "swing", "bossa nova", "jazz fusion"],
        "rock": ["classic rock", "hard rock", "alternative", "indie rock"],
        "classical": ["orchestra", "symphony", "chamber", "opera", "baroque"],
        "electronic": ["edm", "techno", "house", "trance", "ambient"],
        "pop": ["top 40", "hits", "chart", "contemporary"],
        "lounge": ["chillout", "cafe", "easy listening", "smooth"],
        "ambient": ["chillout", "new age", "meditation", "sleep"],
        "news": ["talk", "information", "current affairs", "public radio"],

        # Moods
        "relaxing": ["lounge", "ambient", "chillout", "smooth jazz"],
        "energetic": ["dance", "electronic", "rock", "pop hits"],
        "focus": ["classical", "ambient", "instrumental", "lo-fi"],
        "sleep": ["ambient", "nature", "meditation", "classical"],

        # Languages
        "korean": ["kpop", "한국", "korea"],
        "japanese": ["jpop", "日本", "japan"],
        "chinese": ["cpop", "中国", "china"],
    }

    query_lower = query.lower()
    related = []

    # Direct match
    if query_lower in expansions:
        related = expansions[query_lower]
    else:
        # Partial match
        for key, terms in expansions.items():
            if key in query_lower or query_lower in key:
                related.extend(terms)

    return {
        "original": query,
        "related_terms": list(set(related))[:8],
        "tip": "Try searching with these related terms for more results"
    }


@mcp.tool()
def get_radio_status() -> dict:
    """
    Get current radio system status.
    Useful for AI to understand current state.

    Returns:
        Current playback status, station info, system state
    """
    db = get_db()

    status = {
        "playback": "stopped",
        "current_station": None,
        "current_song": None,
        "volume": 100,
        "favorites_count": 0,
        "history_count": 0,
        "db_stations": 0
    }

    # Playback status
    if current_station:
        status["playback"] = "playing"
        status["current_station"] = current_station

        # Current song
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(1)
            sock.connect(MPV_SOCKET)
            sock.send(b'{"command": ["get_property", "media-title"]}\n')
            response = sock.recv(4096).decode()
            sock.close()
            data = json.loads(response)
            if "data" in data and data["data"]:
                status["current_song"] = data["data"]
        except:
            pass

    # Favorites/history
    favs = load_json(FAVORITES_FILE)
    history = load_json(HISTORY_FILE)
    status["favorites_count"] = len(favs) if favs else 0
    status["history_count"] = len(history) if history else 0

    # DB status
    if db:
        try:
            count = db.execute("SELECT COUNT(*) FROM stations WHERE is_alive = 1").fetchone()[0]
            status["db_stations"] = count
        except:
            pass

    return status


@mcp.tool()
def check_stream(url: str) -> dict:
    """
    Check if a stream URL is alive before playing.
    Use this to avoid playing dead streams.

    Args:
        url: Stream URL to check

    Returns:
        Stream status (alive, dead, or error)
    """
    try:
        req = urllib.request.Request(url, method='HEAD')
        req.add_header('User-Agent', 'RadioMCP/1.0')
        req.add_header('Icy-MetaData', '1')

        with urllib.request.urlopen(req, timeout=5) as resp:
            content_type = resp.headers.get('Content-Type', '')
            icy_name = resp.headers.get('icy-name', '')

            # Check stream type
            is_stream = any(t in content_type.lower() for t in
                          ['audio/', 'application/ogg', 'mpegurl', 'x-scpls'])

            return {
                "status": "alive",
                "url": url,
                "content_type": content_type,
                "icy_name": icy_name,
                "is_stream": is_stream
            }
    except urllib.error.HTTPError as e:
        return {"status": "dead", "url": url, "error": f"HTTP {e.code}"}
    except urllib.error.URLError as e:
        return {"status": "dead", "url": url, "error": str(e.reason)}
    except Exception as e:
        return {"status": "error", "url": url, "error": str(e)}


@mcp.tool()
def check_stream_detailed(url: str) -> dict:
    """
    Check stream with detailed info via G3 validator (if enabled).
    Returns bitrate, audio format, stream name, server location.
    
    Requires: G3_VALIDATOR_ENABLED=true environment variable

    Args:
        url: Stream URL to check

    Returns:
        Detailed stream info
    """
    if not G3_VALIDATOR_ENABLED:
        # Fallback to basic check
        return check_stream(url)
    
    result = g3_validate_url(url)
    if result.get("valid"):
        return {
            "status": "alive",
            "url": url,
            "is_media_stream": result.get("is_media_stream", False),
            "bitrate": result.get("bitrate"),
            "audio_format": result.get("audio_format"),
            "stream_name": result.get("stream_name"),
            "server": result.get("server"),
            "server_location": result.get("server_location"),
            "response_time_ms": result.get("response_time_ms")
        }
    else:
        return {
            "status": "dead",
            "url": url,
            "error": result.get("error", "Validation failed")
        }


@mcp.tool()
def get_categories() -> dict:
    """
    Get major station categories for quick navigation.

    Returns:
        Categories with example search queries
    """
    return {
        "music": {
            "description": "Music stations",
            "genres": ["pop", "rock", "jazz", "classical", "electronic", "hip hop",
                      "country", "r&b", "metal", "indie", "ambient", "lounge"],
            "search_tip": "search('jazz') or recommend('relaxing')"
        },
        "news": {
            "description": "News & Talk radio",
            "types": ["news", "talk", "public radio", "npr"],
            "search_tip": "search('news') or search_by_country('US', 'news')"
        },
        "sports": {
            "description": "Sports radio",
            "types": ["sports", "football", "baseball"],
            "search_tip": "search('sports')"
        },
        "culture": {
            "description": "Culture & Entertainment",
            "types": ["culture", "entertainment", "comedy"],
            "search_tip": "search('culture')"
        },
        "regional": {
            "description": "By country/region",
            "examples": ["KR (Korea)", "US (USA)", "JP (Japan)", "DE (Germany)", "FR (France)"],
            "search_tip": "search_by_country('KR') or search_by_country('JP', 'jazz')"
        },
        "mood": {
            "description": "By mood/activity",
            "moods": ["relaxing", "energetic", "focus", "sleep", "workout", "romantic"],
            "search_tip": "recommend('relaxing') or recommend('focus')"
        }
    }


@mcp.tool()
def get_listening_stats(period: str = "week") -> dict:
    """
    Get listening statistics for a specific period.

    Args:
        period: Time period - "today", "week", "month", "all"

    Returns:
        Listening stats: total time, top stations, top genres, daily breakdown
    """
    from datetime import timedelta

    history = load_json(HISTORY_FILE)
    if not history:
        return {"status": "no_history", "message": "No listening history yet"}

    now = datetime.now()

    # Period filter
    if period == "today":
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        cutoff = now - timedelta(days=7)
    elif period == "month":
        cutoff = now - timedelta(days=30)
    else:  # all
        cutoff = datetime.min

    # Filter
    filtered = []
    for entry in history:
        try:
            ts = datetime.fromisoformat(entry.get("timestamp", ""))
            if ts >= cutoff:
                filtered.append(entry)
        except:
            if period == "all":
                filtered.append(entry)

    if not filtered:
        return {"status": "no_data", "period": period, "message": f"No listening data for {period}"}

    # Calculate stats
    total_duration = sum(e.get("duration", 60) for e in filtered)

    # Listens per station
    station_times = {}
    for e in filtered:
        name = e.get("name", "Unknown")
        station_times[name] = station_times.get(name, 0) + e.get("duration", 60)

    top_stations = sorted(station_times.items(), key=lambda x: -x[1])[:5]

    # Listens per genre
    tag_times = {}
    for e in filtered:
        tags = e.get("tags", "").split(",")
        duration = e.get("duration", 60)
        for tag in tags:
            tag = tag.strip().lower()
            if tag:
                tag_times[tag] = tag_times.get(tag, 0) + duration

    top_tags = sorted(tag_times.items(), key=lambda x: -x[1])[:5]

    # Daily listening time (last 7 days)
    daily = {}
    for e in filtered:
        try:
            ts = datetime.fromisoformat(e.get("timestamp", ""))
            day = ts.strftime("%Y-%m-%d")
            daily[day] = daily.get(day, 0) + e.get("duration", 60)
        except:
            pass

    # Last 7 days only
    recent_days = sorted(daily.items(), reverse=True)[:7]

    return {
        "period": period,
        "total_listens": len(filtered),
        "total_minutes": round(total_duration / 60, 1),
        "total_hours": round(total_duration / 3600, 1),
        "top_stations": [{"name": n, "minutes": round(m/60, 1)} for n, m in top_stations],
        "top_genres": [{"tag": t, "minutes": round(m/60, 1)} for t, m in top_tags],
        "daily_minutes": [{"date": d, "minutes": round(m/60, 1)} for d, m in recent_days],
        "average_per_day": round(total_duration / 60 / max(len(daily), 1), 1)
    }


# ============================================================
# Station health check
# ============================================================
@mcp.tool()
def check_station(url: str) -> dict:
    """
    Check if a radio station URL is alive.

    Args:
        url: Stream URL to check

    Returns:
        Station status (alive, dead, or error)
    """
    try:
        req = urllib.request.Request(url, method='HEAD', headers={
            'User-Agent': 'RadioMCP/1.0'
        })
        response = urllib.request.urlopen(req, timeout=10)
        content_type = response.headers.get('Content-Type', '')

        return {
            "status": "alive",
            "url": url,
            "content_type": content_type,
            "is_audio": "audio" in content_type.lower() or "mpegurl" in content_type.lower()
        }
    except urllib.error.HTTPError as e:
        return {"status": "dead", "url": url, "error": f"HTTP {e.code}"}
    except urllib.error.URLError as e:
        return {"status": "dead", "url": url, "error": str(e.reason)}
    except Exception as e:
        return {"status": "error", "url": url, "error": str(e)}


# ============================================================
# Station sharing
# ============================================================
@mcp.tool()
def share_station(name: str = "") -> dict:
    """
    Get shareable info for current or specified station.

    Args:
        name: Station name (optional, uses current if empty)

    Returns:
        Shareable station info
    """
    station = None

    if name:
        # Search from DB
        db = get_db()
        if db:
            try:
                cursor = db.cursor()
                cursor.execute(
                    "SELECT name, url, country, tags, homepage FROM stations WHERE name LIKE ? LIMIT 1",
                    (f"%{name}%",)
                )
                row = cursor.fetchone()
                if row:
                    station = {
                        "name": row[0],
                        "url": row[1],
                        "country": row[2],
                        "tags": row[3],
                        "homepage": row[4] or ""
                    }
            except:
                pass
    else:
        # Currently playing station
        station = current_station

    if not station:
        return {"status": "error", "message": "No station found"}

    return {
        "status": "ok",
        "share": {
            "name": station.get("name", ""),
            "url": station.get("url", ""),
            "country": station.get("country", ""),
            "tags": station.get("tags", ""),
            "homepage": station.get("homepage", ""),
            "text": f"🎵 {station.get('name', '')} - {station.get('tags', '')}"
        }
    }


def cpu_watchdog():
    """Monitor CPU usage and auto-terminate if spinning"""
    import resource
    last_cpu = resource.getrusage(resource.RUSAGE_SELF).ru_utime
    high_cpu_count = 0
    while True:
        time.sleep(60)  # Check every minute
        current_cpu = resource.getrusage(resource.RUSAGE_SELF).ru_utime
        cpu_delta = current_cpu - last_cpu
        if cpu_delta > 30:  # More than 30s CPU in 1 minute = spinning
            high_cpu_count += 1
            print(f"[WATCHDOG] High CPU detected: {cpu_delta:.1f}s ({high_cpu_count}/3)", flush=True)
            if high_cpu_count >= 3:  # 3 consecutive = terminate
                print("[WATCHDOG] CPU spinning detected, terminating process", flush=True)
                os._exit(1)  # Force exit
        else:
            high_cpu_count = 0  # Reset counter
        last_cpu = current_cpu


def main():
    """Entry point for radiomcp command"""
    import sys

    # Log startup info
    print(f"[radiomcp] Starting PID={os.getpid()} Python={sys.version.split()[0]} MCP=1.26.0", flush=True)

    # Singleton lock disabled - Claude Desktop may spawn multiple servers
    # Share mpv via PID file instead
    # acquire_singleton_lock()  # Disabled

    # Start CPU watchdog (auto-terminate if spinning)
    watchdog = threading.Thread(target=cpu_watchdog, daemon=True)
    watchdog.start()

    # Sync popular stations in background
    sync_thread = threading.Thread(target=sync_popular_stations, daemon=True)
    sync_thread.start()

    try:
        mcp.run()
    except Exception as e:
        print(f"[radiomcp] Fatal error: {e}", flush=True)
        raise
    finally:
        print(f"[radiomcp] Shutting down PID={os.getpid()}", flush=True)


if __name__ == "__main__":
    main()
