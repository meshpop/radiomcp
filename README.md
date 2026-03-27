# radiomcp

[![PyPI](https://img.shields.io/pypi/v/radiomcp)](https://pypi.org/project/radiomcp/)
[![Python](https://img.shields.io/pypi/pyversions/radiomcp)](https://pypi.org/project/radiomcp/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Internet radio for Claude and your terminal. ~25,000 verified live stations, 197 countries.**

```bash
pip install radiomcp && radiomcp
```

First run auto-registers with Claude Desktop / Claude Code. Restart Claude and you're done.

[한국어](README.ko.md) · Powered by [Airtune API](https://api.airtune.ai)

---

## Two ways to use it

| | Command | What it does |
|---|---|---|
| **MCP server** | `radiomcp` | Connects to Claude — control radio in plain language |
| **TUI player** | `radio` | Interactive terminal player with search and favorites |

---

## MCP — control radio with Claude

```bash
pip install radiomcp && radiomcp
```

Auto-detected and registered on first run. Or manually add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "radio": { "command": "radiomcp" }
  }
}
```

Then just ask Claude:

> "Play some late-night jazz"
> "Find Korean news stations"
> "What's playing right now?"
> "Recommend something for focus work"
> "Play a French station"
> "Stop the radio"

### MCP Tools

| Tool | Description |
|---|---|
| `play` | Play by URL or search query |
| `stop` | Stop playback |
| `now_playing` | Current station and track |
| `search` | Search by keyword, genre, country |
| `recommend` | AI recommendations by mood or context |
| `get_favorites` / `add_favorite` | Saved stations |
| `get_history` | Listening history |
| `set_volume` / `get_volume` | Volume control |
| `get_popular` | Most popular stations |
| `search_by_country` | Stations by country code |
| `search_by_language` | Stations by language |
| `recognize_song` | Identify currently playing song |
| `get_radio_status` | Player status |

---

## TUI Player

```bash
radio
```

Interactive terminal player. Type to search, numbers to play.

### Search

```
> jazz              # keyword
> korea news        # combined
> japan classical   # multilingual
> jazz HQ           # high quality only (192k+)
```

Supports 50+ languages — Korean, Japanese, Chinese, Russian, Arabic and more are normalized automatically.

| Key | Function |
|---|---|
| `g` | Genre browser |
| `c` | Country browser |
| `p` | Popular stations |
| `/` | Search |
| `!` | Toggle: local DB ↔ DB + live API |

### Playback & Volume

| Key | Function |
|---|---|
| `1`–`9` | Play station from list |
| `r` | Resume last station |
| `s` | Stop |
| `v` / `v+` / `v-` / `v50` | Show / up / down / set volume |
| `q` | Quit |

### Favorites

| Key | Function |
|---|---|
| `f` | View favorites |
| `+` / `-` | Add / remove current station |
| `<` / `>` | Previous / next favorite |

### AI & Song Info

| Key | Function |
|---|---|
| `a` | Personalized recommendations |
| `w` | Time-based mood recommendations |
| `i` | Recognize current song (Shazam-like) |
| `n` | Current song info |

### DJ Mode

```bash
RADIOCLI_DJ=1 radio
```

AI-voiced DJ commentary between tracks. Supports 10 languages.

---

## Player Backends

Auto-detected: **mpv → vlc → ffplay → browser**

| Backend | Install |
|---|---|
| mpv *(recommended)* | `brew install mpv` / `apt install mpv` |
| vlc | `brew install vlc` / `apt install vlc` |
| ffplay | `brew install ffmpeg` / `apt install ffmpeg` |

---

## CLI

```bash
radiomcp search jazz
radiomcp play <url> "Station Name"
radiomcp stop
radiomcp now
radiomcp recommend focus
radiomcp update          # Sync latest stations from Airtune API
radiomcp serve           # Start HTTP API server
```

---

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `RADIOCLI_LLM` | LLM provider: `claude`, `openai`, `ollama`, `none` | `none` |
| `RADIOCLI_DJ` | DJ mode | `0` |
| `RADIOCLI_LANG` | UI language | auto-detect |
| `ANTHROPIC_API_KEY` | For Claude-powered features | — |
| `OPENAI_API_KEY` | For OpenAI-powered features | — |
| `OLLAMA_URL` | Ollama server URL | `http://localhost:11434` |

---

## Data

Station database (~25,000 verified live stations) stored in `~/.radiocli/` on first run.

```bash
radiomcp update    # Pull latest from Airtune API
```

---

## License

- **Code**: MIT — [LICENSE](LICENSE)
- **Station data**: ODbL 1.0 — [DATA_LICENSE.md](DATA_LICENSE.md)
