# Radio MCP Server

MCP server for internet radio search and playback with Claude Desktop.

## Installation

```bash
# Install dependencies
pip install "mcp[cli]"

# Install mpv (required for playback)
brew install mpv
```

## Claude Desktop Setup

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "radio": {
      "command": "python3",
      "args": ["/path/to/radiomcp/server.py"]
    }
  }
}
```

Restart Claude Desktop after configuration.

## Tools

| Tool | Description |
|------|-------------|
| `search` | Search radio stations by keyword |
| `search_by_country` | Search by country code (KR, US, JP...) |
| `get_popular` | Get popular stations |
| `play` | Play a radio stream |
| `stop` | Stop playback |
| `now_playing` | Get current song info |
| `get_favorites` | List favorites |
| `add_favorite` | Add to favorites |
| `remove_favorite` | Remove from favorites |
| `get_history` | Listening history |
| `recommend` | Mood-based recommendations |

## Usage

Just ask Claude naturally:

- "Play some jazz radio"
- "Find Korean radio stations"
- "What's playing now?"
- "I want relaxing music"
- "Stop the radio"
- "Add this to favorites"

## API

Uses [Radio Browser API](https://api.radio-browser.info/) for station data.

## Requirements

- Python 3.10+
- mcp[cli]
- mpv

## License

MIT
