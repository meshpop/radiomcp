# radiomcp

**Internet radio for Claude and your terminal. 55,000+ stations, 200+ countries.**

```bash
pipx install radiomcp
```

Powered by [Airtune API](https://api.airtune.ai) | [한국어](README.ko.md)

---

## Components

| Component | Command | Description |
|---|---|---|
| **radiomcp** | `radiomcp` | MCP server + HTTP API + CLI |
| **radio** | `radio` | Interactive TUI player |

Both install together with `pip install radiomcp`.

---

## MCP Server

Connect radiomcp to Claude (or any MCP-compatible AI) and control internet radio in plain language.

### Installation

```bash
pipx install radiomcp
```

> Use `pipx` to ensure the `radio` command is on PATH. If using `pip`, add the scripts directory manually.

### Add to Claude Desktop

`claude_desktop_config.json`:
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

### Ask Claude to control radio

> "Play some jazz radio"
> "Find Korean news stations"
> "What's playing now?"
> "Stop the radio"
> "Recommend something for late-night focus work"
> "Play a French station"

### MCP Tools

| Tool | Description |
|---|---|
| `play` | Play a station by URL or search query |
| `stop` | Stop playback |
| `now_playing` | Current station and track info |
| `search` | Search by keyword, genre, country |
| `recommend` | AI recommendations by mood or context |
| `get_favorites` | List saved favorites |
| `add_favorite` | Save a station |
| `get_history` | Recent listening history |
| `set_volume` | Set volume level |
| `get_volume` | Get current volume |
| `get_popular` | Most popular stations |
| `search_by_country` | Stations by country code |
| `search_by_language` | Stations by language |
| `recognize_song` | Identify current song (Shazam-like) |
| `get_radio_status` | Player status and current station |
| `health_check` | Service health |

---

## Player Backends

| Backend | Quality | Install |
|---|---|---|
| **mpv** (recommended) | Best — auto-reconnect, ICY metadata | `brew install mpv` / `apt install mpv` |
| **vlc** | Stable, widely installed | `brew install vlc` / `apt install vlc` |
| **ffplay** | Lightweight, with ffmpeg | `brew install ffmpeg` / `apt install ffmpeg` |
| **browser** | No install needed | Auto fallback |

Auto-detection order: mpv → vlc → ffplay → browser

---

## CLI Mode

```bash
radiomcp search jazz
radiomcp search "korean news"
radiomcp play <url> "Station Name"
radiomcp stop
radiomcp now
radiomcp recommend focus
radiomcp update              # Sync latest stations from Airtune API
radiomcp serve --port 8100   # Start HTTP API server
```

---

## TUI Player (`radio`)

Interactive terminal player with keyboard controls.

```bash
radio
```

### Search

```
> jazz              # keyword
> korea news        # combined
> relaxing music    # mood
> japan classical   # multilingual
```

| Key | Function |
|---|---|
| `g` | Genre selection |
| `c` | Country selection |
| `p` | Popular stations |
| `h` | High quality (256k+) |
| `/` | Search mode |
| `!` | Toggle search mode (local DB / DB + API) |

Search modes:

| Mode | Speed | Description |
|---|---|---|
| DB only | ~0.1s | Local SQLite — instant |
| DB + API | ~1s | Includes live RadioGraph API |

### Playback

| Key | Function |
|---|---|
| `number` | Play station from list |
| `r` | Resume last station |
| `s` | Stop |
| `q` | Quit |

### Volume

| Key | Function |
|---|---|
| `v` | Show volume |
| `v+` | Volume up |
| `v-` | Volume down |
| `v50` | Set to 50% |

### Favorites & Playlists

| Key | Function |
|---|---|
| `f` | View favorites |
| `+` | Add to favorites |
| `-` | Remove from favorites |
| `<` / `>` | Previous / next favorite |
| `l` | Playlists |

Playlist types: `favorites`, `history`, `mood`, `ai`, `tag:jazz`, `country:KR`

### AI Recommendations

| Key | Function |
|---|---|
| `a` | Personalized recommendations |
| `t` | Taste analysis |
| `w` | Time-based mood recommendations |

### Song Info

| Key | Function |
|---|---|
| `n` | Current song |
| `i` | Song recognition (Shazam-like) |
| `il` | Recognized songs list |
| `sl` | Song history |
| `st` | Toggle auto song history |

### DJ Mode

```bash
RADIOCLI_DJ=1 radio
```

AI-voiced DJ commentary between tracks. Supports 10 languages: English, Korean, Japanese, French, German, Spanish, Chinese, Portuguese, Russian, Italian.

---

## Multilingual Search

Supports 50+ languages. Queries in any language are normalized to English station tags.

| Language | Example | Converts to |
|---|---|---|
| Korean | 재즈, 클래식, 뉴스 | jazz, classical, news |
| Japanese | ジャズ, クラシック | jazz, classical |
| Chinese | 爵士乐, 古典音乐 | jazz, classical |
| Russian | джаз, классика | jazz, classical |
| Arabic | موسيقى, أخبار | music, news |

## Quality Filters

| Keyword | Filter |
|---|---|
| `HQ`, `high quality` | 192k+ |
| `HD` | 256k+ |
| `LQ`, `low quality` | 96k or less |

Example: `jazz HQ`

---

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `RADIOCLI_LLM` | LLM provider (`claude`, `openai`, `ollama`, `none`) | `none` |
| `RADIOCLI_DJ` | DJ mode | `0` |
| `RADIOCLI_LANG` | UI language | auto |
| `RADIOCLI_VOICE` | TTS voice | `en-US-JennyNeural` |
| `OLLAMA_MODEL` | Ollama model | `llama3.2` |
| `OLLAMA_URL` | Ollama server | `http://localhost:11434` |
| `ANTHROPIC_API_KEY` | Claude API key | — |
| `OPENAI_API_KEY` | OpenAI API key | — |

---

## Data Storage

```
~/.radiocli/
├── favorites.json         # Saved stations
├── history.json           # Listening history
├── songs.json             # Song history (auto)
├── recognized_songs.json  # Song recognition results
├── playlists.json         # Playlists
└── mpv.sock               # mpv IPC socket
```

Station database (~55,000 stations) is bundled and stored in `~/.radiocli/` on first run. Keep it fresh:

```bash
radiomcp update
```

---

## Dependencies

- Python 3.9+
- mpv — required for CLI and TUI playback
- ffmpeg — optional, for song recording
- openai-whisper — optional, for DJ speech recognition
- edge-tts — optional, for DJ mode TTS

---

## License

- **Code**: MIT — [LICENSE](LICENSE)
- **Station Database**: ODbL 1.0 — [DATA_LICENSE.md](DATA_LICENSE.md)
- **Attribution**: [ATTRIBUTION.md](ATTRIBUTION.md)
