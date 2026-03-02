# Radio MCP Server - Help

Internet radio search and playback MCP server for Claude Desktop.

## Available Tools

### Search

| Tool | Description | Example |
|------|-------------|---------|
| `search` | Search by genre, name, keyword | "jazz", "BBC", "lounge" |
| `search_by_country` | Search by country code | "KR", "US", "JP", "DE" |
| `advanced_search` | Combined filters (country + tag + bitrate) | country="KR", tag="jazz", min_bitrate=128 |
| `get_popular` | Get top stations by clicks | - |
| `recommend` | Mood-based recommendations | "relaxing", "energetic", "focus" |

### Playback

| Tool | Description |
|------|-------------|
| `play` | Play station (auto-fetches fresh URL for token handling) |
| `stop` | Stop playback |
| `now_playing` | Get current song info (artist, title) |
| `set_volume` | Volume control (0-100) |

### Song Recognition

| Tool | Description |
|------|-------------|
| `recognize_song` | Shazam-like recognition (AcoustID + Whisper) |
| `get_recognized_songs` | List of recognized songs history |

### Favorites

| Tool | Description |
|------|-------------|
| `get_favorites` | List all favorites |
| `add_favorite` | Add station to favorites |
| `remove_favorite` | Remove by index (0-based) |

### History & Personalization

| Tool | Description |
|------|-------------|
| `get_history` | Recent listening history |
| `get_user_profile` | Analyze listening patterns (tags, time, day preferences) |
| `personalized_recommend` | AI recommendations based on your listening history |

### Context-Aware Features

| Tool | Description |
|------|-------------|
| `recommend_by_weather` | Weather-based recommendations (Seoul, etc.) |
| `sleep_timer` | Auto-stop after N minutes |
| `set_alarm` | Wake-up alarm with radio |
| `get_similar` | Find similar stations |

### Database Management

| Tool | Description |
|------|-------------|
| `get_db_stats` | Show DB statistics (total, alive, dead, countries) |
| `purge_dead` | Delete all dead stations from DB |
| `health_check` | Verify station URLs (HEAD request), update is_alive status |
| `sync_with_api` | Sync with Radio Browser API (fetch new/updated stations) |

## Usage Examples

### Natural Language Prompts

```
"Play some jazz radio"
→ search("jazz") → play(url, name)

"Find Korean news stations"
→ advanced_search(country="KR", tag="news")

"What song is playing now?"
→ now_playing()

"I want relaxing music"
→ recommend("relaxing") → play(url, name)

"Recognize this song"
→ recognize_song()

"What songs did I hear today?"
→ get_recognized_songs()

"Stop the radio"
→ stop()
```

### Advanced Search

```
"Korean jazz stations"
→ advanced_search(country="KR", tag="jazz")

"High quality classical"
→ advanced_search(tag="classical", min_bitrate=192)

"US pop stations over 128k"
→ advanced_search(country="US", tag="pop", min_bitrate=128)
```

### Database Management

```
"Show database stats"
→ get_db_stats()

"Clean up dead stations"
→ purge_dead()

"Sync Korean stations from Radio Browser"
→ sync_with_api(country_code="KR")

"Check health of 50 stations"
→ health_check(limit=50)
```

### AI Personalization

```
"What are my listening patterns?"
→ get_user_profile()

"Recommend based on my taste"
→ personalized_recommend()

"Recommend music for this weather"
→ recommend_by_weather("Seoul")

"Set sleep timer for 30 minutes"
→ sleep_timer(30)

"Wake me up at 7am with jazz"
→ set_alarm("07:00", "jazz")
```

## Multilingual Search

Supports Korean, Japanese, Chinese, German, French, Spanish keywords:

| Language | Example | Translated |
|----------|---------|------------|
| Korean | "재즈", "클래식", "뉴스" | jazz, classical, news |
| Japanese | "ジャズ", "クラシック" | jazz, classical |
| Chinese | "爵士乐", "古典音乐" | jazz, classical |
| Korean | "한국", "미국", "일본" | KR, US, JP |

Related terms also work:
- "시사", "교양", "보도" → news
- "토크쇼", "라디오쇼" → talk

## Quality Filters

| Keyword | Filter |
|---------|--------|
| "고음질", "HQ", "high quality" | min_bitrate=192 |
| "최고음질", "HD" | min_bitrate=256 |
| "저음질", "LQ" | max_bitrate=96 |

## Mood Keywords

| Mood | Tags |
|------|------|
| relaxing | lounge, ambient, classical, jazz |
| energetic | dance, electronic, pop, rock |
| focus | classical, ambient, instrumental |
| sleep | ambient, classical |
| morning | pop, jazz |
| workout | electronic, dance, rock |
| romantic | jazz, classical |

## Country Codes

| Code | Country |
|------|---------|
| KR | South Korea |
| US | United States |
| JP | Japan |
| GB | United Kingdom |
| DE | Germany |
| FR | France |
| CN | China |
| BR | Brazil |
| AU | Australia |
| CA | Canada |

## Search Logic

1. **DB Search** - Local SQLite database (24k+ verified stations)
2. **API Search** - Radio Browser API (fresh results)
3. **Merge & Dedupe** - Combine both, remove duplicates
4. **Block Filter** - Remove blocked stations (e.g., propaganda)

## Playback Features

### Auto Fresh URL
When playing a station, the server automatically fetches the latest URL from API.
This handles token-based streams that expire (KBS, MBC, etc.).

### Song Tracking
Songs are automatically tracked and saved to `recognized_songs.json`:
- Artist, title parsed from stream metadata
- Station name and timestamp
- Accessible via `get_recognized_songs()`

## Block List

The following stations are permanently blocked:
- 평양FM, Pyongyang, North Korea, DPRK, 조선중앙

## Data Storage

All data is stored in `~/.radiocli/`:

| File | Description |
|------|-------------|
| `favorites.json` | Saved favorite stations |
| `history.json` | Listening history (stations) |
| `recognized_songs.json` | Song recognition history |
| `songs.json` | Auto-tracked songs (CLI) |
| `mpv.sock` | mpv IPC socket |

Database: `~/RadioCli/radio_stations.db` (SQLite)

## Requirements

- **mpv**: Required for audio playback
  ```bash
  brew install mpv
  ```

- **chromaprint** (optional): For AcoustID song recognition
  ```bash
  brew install chromaprint
  ```

## Troubleshooting

### Radio won't play
- Check if mpv is installed: `which mpv`
- Check if another mpv instance is running: `pkill mpv`

### No song info
- Not all stations provide metadata
- Try premium/high-quality stations for better metadata

### Connection errors
- Check internet connection
- Radio Browser API may be temporarily unavailable

### Dead stations appearing
- Run `purge_dead()` to remove dead stations
- Run `health_check()` to verify and update status
