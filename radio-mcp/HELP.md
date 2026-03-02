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

### Mood Keywords for recommend()

| Mood | Tags |
|------|------|
| relaxing | lounge, ambient, classical, jazz |
| energetic | dance, electronic, pop, rock |
| focus | classical, ambient, lofi, instrumental |
| sleep | ambient, nature, classical |
| morning | pop, jazz, news |
| workout | electronic, dance, rock, hiphop |
| romantic | jazz, ballad, classical |

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
