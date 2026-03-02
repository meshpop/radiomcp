# Radio MCP Server - Help

Internet radio search and playback MCP server for Claude Desktop.

## Available Tools

### Search

| Tool | Description | Example |
|------|-------------|---------|
| `search` | Search by genre, name, keyword | "jazz", "BBC", "lounge" |
| `search_by_country` | Search by country code | "KR", "US", "JP", "DE" |
| `get_popular` | Get top stations by clicks | - |
| `recommend` | Mood-based recommendations | "relaxing", "energetic", "focus" |

### Playback

| Tool | Description |
|------|-------------|
| `play` | Play a radio station (requires url, optional name) |
| `stop` | Stop playback |
| `now_playing` | Get current song info (artist, title) |

### Favorites

| Tool | Description |
|------|-------------|
| `get_favorites` | List all favorites |
| `add_favorite` | Add station to favorites |
| `remove_favorite` | Remove by index (0-based) |

### History

| Tool | Description |
|------|-------------|
| `get_history` | Recent listening history |

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

"Find Korean radio stations"
→ search_by_country("KR")

"What song is playing now?"
→ now_playing()

"I want relaxing music"
→ recommend("relaxing") → play(url, name)

"Add this to favorites"
→ add_favorite({name, url})

"Stop the radio"
→ stop()
```

### Database Management

```
"Show database stats"
→ get_db_stats()

"Clean up dead stations"
→ purge_dead()

"Sync Korean stations from Radio Browser"
→ sync_with_api(country_code="KR")

"Sync jazz stations"
→ sync_with_api(tag="jazz")

"Check health of 50 stations"
→ health_check(limit=50)
```

### Mood Keywords for recommend()

| Mood | Tags |
|------|------|
| relaxing | lounge, ambient, classical, jazz |
| energetic | dance, electronic, pop, rock |
| focus | classical, ambient, instrumental |
| sleep | ambient, classical |
| morning | pop, jazz |
| workout | electronic, dance, rock |
| romantic | jazz, classical |

### Country Codes

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

1. **DB Search** - Local SQLite database (27k+ verified stations)
2. **API Search** - Radio Browser API (fresh results, `lastcheckok=1`)
3. **Merge & Dedupe** - Combine both, remove duplicates
4. **Auto-save** - Valid new stations saved to DB (no tokens/proxies)

Results include `source` field:
- `"db"` - From local database (verified)
- `"api"` - From Radio Browser (live)

## Station Validation

Stations are saved to DB only if:
- No tokens in URL (no `?` or `&`)
- No proxy domains (duckdns, no-ip, etc.)
- No direct IP addresses
- At least 5 votes

## Requirements

- **mpv**: Required for audio playback
  ```bash
  brew install mpv
  ```

## Data Storage

All data is stored in `~/.radiocli/`:

| File | Description |
|------|-------------|
| `favorites.json` | Saved favorite stations |
| `history.json` | Listening history |
| `mpv.sock` | mpv IPC socket |

Database: `~/RadioCli/radio_stations.db` (SQLite)

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
