# RadioCli & Radio MCP Server - Complete Documentation

## Overview

RadioCli is a terminal-based internet radio player with 24,000+ verified stations. It consists of two components:

1. **RadioCli (CLI)** - Terminal application for direct radio playback
2. **Radio MCP Server** - Model Context Protocol server for AI assistant integration

Both share the same SQLite database and support multilingual search, song recognition, and personalized recommendations.

---

## Architecture

```
+---------------------------+---------------------------+
|      CLI (radio.py)       |    MCP Server (server.py) |
|      - Terminal UI        |    - Claude Desktop       |
|      - Direct input       |    - Natural language     |
+-------------+-------------+-------------+-------------+
              |                           |
              v                           v
+-----------------------------------------------------------+
|                     Core Components                        |
+-----------------------------------------------------------+
|  SQLite DB        |  Radio Browser API  |  mpv Player     |
|  (24k+ stations)  |  (fallback search)  |  (IPC socket)   |
+-------------------+---------------------+-----------------+
|  Favorites/History (JSON)  |  Song Recognition (AcoustID) |
+----------------------------+------------------------------+
|  DJ Mode (edge-tts)        |  LLM Integration (optional)  |
+----------------------------+------------------------------+
```

---

## File Structure

```
RadioCli/
|-- radio.py                 # Main CLI application
|-- radio_stations.db        # SQLite database (24k+ stations)
|-- languages.json           # UI translations (ko, en, ja, zh)
|-- README.md                # Project readme
|
|-- radio-mcp/               # MCP Server
|   |-- server.py            # MCP server implementation
|   |-- README.md            # MCP setup guide
|   |-- HELP.md              # MCP tool reference
|   +-- daily_maintenance.py # DB maintenance script
|
+-- docs/                    # Documentation
    |-- DOCUMENTATION.md     # English docs
    +-- DOCUMENTATION_KO.md  # Korean docs

~/.radiocli/                 # User Data Directory
|-- favorites.json           # Saved favorite stations
|-- history.json             # Listening history
|-- playlists.json           # Custom playlists
|-- recognized_songs.json    # Song recognition history
|-- songs.json               # Auto-tracked songs (CLI)
|-- last_station.json        # Last playing (for resume)
+-- mpv.sock                 # mpv IPC socket (runtime)
```

---

## Database Structure

### Location
- **Database**: `~/RadioCli/radio_stations.db`
- **User Data**: `~/.radiocli/`

### Schema

```sql
CREATE TABLE stations (
    stationuuid TEXT PRIMARY KEY,
    name TEXT,
    url TEXT,
    url_resolved TEXT,
    country TEXT,
    countrycode TEXT,
    tags TEXT,
    bitrate INTEGER,
    votes INTEGER,
    clickcount INTEGER,
    is_alive INTEGER DEFAULT 1,
    fail_count INTEGER DEFAULT 0,
    last_checked TEXT
);
```

### Data Files

| File | Description |
|------|-------------|
| `favorites.json` | Saved favorite stations |
| `history.json` | Station listening history |
| `songs.json` | Auto-tracked song history (CLI) |
| `recognized_songs.json` | Shazam-like recognized songs |
| `playlists.json` | Custom playlists |
| `last_station.json` | Last playing station (for resume) |

---

## Search System

### Search Modes

| Mode | Speed | Description |
|------|-------|-------------|
| DB Only | ~0.1s | Local SQLite search (default) |
| DB + API | ~1.0s | Local + Radio Browser API |

Toggle with `!` key in CLI.

### Search Flow

```
User Query: "한국 재즈 고음질"
         │
         ▼
┌─────────────────────────────┐
│  1. Parse Query             │
│  - "한국" → country: KR     │
│  - "재즈" → tag: jazz       │
│  - "고음질" → min_bitrate:192│
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│  2. Search Execution        │
│  - DB search (instant)      │
│  - API search (if enabled)  │
│  - Merge & deduplicate      │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│  3. Filter & Sort           │
│  - Apply bitrate filter     │
│  - Remove blocked stations  │
│  - Sort by quality/votes    │
└─────────────────────────────┘
```

### Multilingual Support

| Language | Country Examples | Genre Examples |
|----------|------------------|----------------|
| Korean | 한국, 미국, 일본, 영국 | 재즈, 클래식, 뉴스, 팝 |
| Japanese | 日本, アメリカ, 韓国 | ジャズ, クラシック |
| Chinese | 中国, 美国, 韩国 | 爵士乐, 古典音乐 |
| German | Deutschland, Amerika | Jazz, Klassik |
| French | France, Allemagne | Jazz, Classique |

### Related Terms

```python
TAG_EXPAND = {
    "news": ["news", "talk", "information"],
    "jazz": ["jazz", "smooth jazz", "bebop", "swing"],
    "classical": ["classical", "orchestra", "symphony"],
    "electronic": ["electronic", "edm", "techno", "house"],
}
```

### Quality Filters

| Keyword | Filter |
|---------|--------|
| 고음질, HQ, high quality | min_bitrate: 192 |
| 최고음질, HD | min_bitrate: 256 |
| 저음질, LQ | max_bitrate: 96 |

---

## Playback System

### Auto URL Refresh

Token-based streams (KBS, MBC, etc.) expire frequently. The system automatically:

1. Fetches fresh URL from Radio Browser API before playing
2. Updates local DB with new URL
3. Falls back to cached URL if API fails

### Song Tracking

Songs are automatically tracked during playback:

```json
{
  "artist": "Norah Jones",
  "title": "Come Away With Me",
  "station": "Smooth Jazz FM",
  "timestamp": "2024-03-02T14:30:00"
}
```

Metadata is parsed from stream's `icy-title` (format: "Artist - Title").

### Song Recognition

Multiple recognition methods:

1. **Stream Metadata** - Parse artist/title from `icy-title`
2. **AcoustID** - Audio fingerprinting (requires chromaprint)
3. **Whisper** - Speech-to-text for DJ mentions

---

## Block List

Permanently blocked stations:

```python
BLOCK_LIST = ["평양", "pyongyang", "north korea", "dprk", "조선중앙"]
```

Blocked stations are:
- Never saved to DB
- Filtered from search results
- Cannot be played

---

## CLI Commands

### Main Menu

```
RadioCli (DB)

a AI추천   t 취향   p 인기   h 고음질
g 장르     c 국가   f 즐찾(2)  l 리스트
w 분위기   i 인식   n 현재곡  sl 곡(0)
r 이어듣기 s 정지   < 이전   > 다음
q 종료     ! 모드   d DJ
```

### Command Reference

| Key | Function |
|-----|----------|
| `a` | AI recommendation based on listening history |
| `t` | Show taste analysis |
| `w` | Mood-based recommendation (time of day) |
| `i` | Recognize current song (Shazam-like) |
| `p` | Popular stations |
| `h` | High quality stations (256k+) |
| `g` | Genre selection |
| `c` | Country selection |
| `f` | Favorites |
| `+` | Add to favorites |
| `-` | Remove from favorites |
| `<` | Previous favorite |
| `>` | Next favorite |
| `l` | Playlists |
| `n` | Show current song |
| `sl` | Song history |
| `st` | Toggle song tracking |
| `sc` | Clear song history |
| `r` | Resume last station |
| `s` | Stop playback |
| `q` | Quit |
| `!` | Toggle search mode (DB/API) |
| `d` | Toggle DJ mode |
| `lang` | Change language |

### Natural Language Search

```
> 한국 재즈
> 신나는 음악
> japan classical
> relaxing lounge
> 미국 뉴스 고음질
```

---

## MCP Server Tools

### Search Tools

| Tool | Parameters | Description |
|------|------------|-------------|
| `search` | query, limit | Search by keyword |
| `search_by_country` | country_code, limit | Search by country |
| `advanced_search` | country, tag, min_bitrate, max_bitrate | Combined filters |
| `get_popular` | limit | Top stations by clicks |
| `recommend` | mood | Mood-based search |

### Playback Tools

| Tool | Parameters | Description |
|------|------------|-------------|
| `play` | url, name | Play station |
| `stop` | - | Stop playback |
| `resume` | - | Resume last station |
| `now_playing` | - | Current song info |
| `set_volume` | volume (0-100) | Adjust volume |

### Recognition Tools

| Tool | Parameters | Description |
|------|------------|-------------|
| `recognize_song` | duration | Recognize current song |
| `get_recognized_songs` | limit | Recognition history |

### Favorites & History

| Tool | Parameters | Description |
|------|------------|-------------|
| `get_favorites` | - | List favorites |
| `add_favorite` | station | Add to favorites |
| `remove_favorite` | index | Remove from favorites |
| `get_history` | limit | Listening history |

### Personalization

| Tool | Parameters | Description |
|------|------------|-------------|
| `get_user_profile` | - | Analyze listening patterns |
| `personalized_recommend` | limit | AI recommendations |
| `recommend_by_weather` | city | Weather-based recommendation |
| `get_similar` | station_name | Find similar stations |

### Utility

| Tool | Parameters | Description |
|------|------------|-------------|
| `sleep_timer` | minutes | Auto-stop timer |
| `set_alarm` | time, genre | Wake-up alarm |

### Database Management

| Tool | Parameters | Description |
|------|------------|-------------|
| `get_db_stats` | - | Database statistics |
| `health_check` | limit | Check station URLs |
| `purge_dead` | - | Remove dead stations |
| `sync_with_api` | country_code, tag | Sync from Radio Browser |

---

## Session Lifecycle

### MCP Server

```
Start Claude Code
       │
       ▼
┌─────────────────┐
│ MCP Server Init │
│ - Load DB       │
│ - Build index   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ User Commands   │◄──┐
│ - search()      │   │
│ - play()        │   │
│ - now_playing() │───┘
└────────┬────────┘
         │
         ▼ (Exit)
┌─────────────────┐
│ Cleanup         │
│ - Save last     │
│ - Stop mpv      │
│ - Remove socket │
└─────────────────┘
```

### Resume Feature

Last playing station is saved to `last_station.json` on exit.
Use `resume()` to continue playback in next session.

---

## Requirements

### Required

- Python 3.8+
- mpv (`brew install mpv`)

### Optional

- chromaprint (`brew install chromaprint`) - AcoustID recognition
- ffmpeg (`brew install ffmpeg`) - Audio recording
- edge-tts (`pip install edge-tts`) - DJ mode TTS
- ollama - Local LLM for advanced parsing

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `RADIOCLI_LLM` | LLM provider (auto/ollama/claude/none) | auto |
| `RADIOCLI_DJ` | Enable DJ mode | 0 |
| `RADIOCLI_LANG` | UI language | ko |
| `OLLAMA_MODEL` | Ollama model name | llama3.2 |
| `ANTHROPIC_API_KEY` | Claude API key | - |
| `OPENAI_API_KEY` | OpenAI API key | - |

---

## Performance

| Operation | DB Only | DB + API |
|-----------|---------|----------|
| Search | ~0.1s | ~1.0s |
| Play | ~2.0s | ~2.0s |
| Song info | <0.1s | <0.1s |

DB-only mode is 10x faster and recommended for normal use.

---

## License

MIT
