# radiomcp

MCP server for internet radio - search and play 24,000+ stations from 197 countries.

## Installation

```bash
pip install radiomcp

# Required for playback
brew install mpv  # macOS
# apt install mpv  # Linux
```

## Claude Desktop Setup

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "radio": {
      "command": "python3",
      "args": ["-m", "radiomcp"]
    }
  }
}
```

Restart Claude Desktop.

## Usage

Just ask Claude naturally:

- "Play some jazz radio"
- "Find Korean news stations"
- "What song is playing?"
- "I want relaxing music"
- "Stop the radio"

## Features

- **24,000+ stations** from 197 countries
- **Fast search** (~5ms local DB)
- **Song recognition** (stream metadata + AcoustID)
- **AI recommendations** (mood, time, weather)
- **Multilingual** (Korean, Japanese, Chinese, etc.)
- **Favorites & history**
- **Auto URL refresh** (handles token expiration)
- **Remote blocklist** (GitHub-based updates)

## Tools

| Tool | Description |
|------|-------------|
| `search` | Search by keyword |
| `search_by_country` | Search by country code |
| `get_popular` | Popular stations |
| `recommend` | Mood-based (relaxing, energetic, focus) |
| `play` | Start playback |
| `stop` | Stop playback |
| `resume` | Resume last station |
| `now_playing` | Current song info |
| `get_favorites` | List favorites |
| `add_favorite` | Save to favorites |
| `get_radio_guide` | Full usage guide for AI |

## Requirements

- Python 3.10+
- mpv (audio playback)

## Data Sources

- [Radio Browser API](https://api.radio-browser.info/) - station database
- [AcoustID](https://acoustid.org/) - song recognition

## License

MIT - See [LICENSE](LICENSE)

## Disclaimer

See [DISCLAIMER.md](DISCLAIMER.md) for terms of use.
