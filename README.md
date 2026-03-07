# RadioCli / radiomcp

Search and play 51,000+ internet radio stations from 200+ countries.

[한국어](README.ko.md)

## Components

| Component | Description |
|-----------|-------------|
| **radiomcp** | MCP Server - integrates with Claude Desktop |
| **radio.py** | CLI App - use directly in terminal |

## radiomcp (MCP Server)

### Installation

```bash
pip install radiomcp
```

### Player Installation (Optional)

Install one of the following for better playback quality. Falls back to browser if none installed.

| Player | macOS | Linux | Windows |
|--------|-------|-------|---------|
| **mpv** (recommended) | `brew install mpv` | `apt install mpv` | `winget install mpv` |
| **VLC** | `brew install vlc` | `apt install vlc` | [vlc.io](https://vlc.io) |
| **ffplay** | `brew install ffmpeg` | `apt install ffmpeg` | [ffmpeg.org](https://ffmpeg.org) |

**Auto-detection priority:** mpv > vlc > ffplay > browser

### Claude Desktop Configuration

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

### Usage

Ask Claude in natural language:
- "Play some jazz radio"
- "Find Korean news stations"
- "What's playing now?"
- "Stop the radio"

### Player Backends

| Backend | Description |
|---------|-------------|
| **mpv** | Best quality, auto-reconnect, ICY metadata |
| **vlc** | Widely installed, stable |
| **ffplay** | Included with ffmpeg, lightweight |
| **browser** | No installation needed, auto fallback |

See [radiomcp/README.md](radiomcp/README.md) for details.

---

## radio.py (CLI)

CLI app for searching and listening to internet radio worldwide.

### Installation

```bash
# Required
brew install mpv

# Optional (for song recognition)
brew install chromaprint ffmpeg
```

### Run

```bash
./radio.py
```

### Usage

#### Search

```
> jazz              # keyword search
> korea news        # combined search
> relaxing music    # mood search
> japan classical   # multilingual
```

| Key | Function |
|-----|----------|
| `g` | Genre selection |
| `c` | Country selection |
| `p` | Popular stations |
| `h` | High quality (256k+) |
| `/` | Search mode |
| `!` | Toggle search mode (DB only/DB+API) |

#### Search Modes

| Mode | Speed | Description |
|------|-------|-------------|
| DB only | 0.1s | Local DB (default) |
| DB+API | 1s+ | Includes Radio Browser API |

Toggle with `!` key

#### AI Recommendations

| Key | Function |
|-----|----------|
| `a` | Personalized recommendations |
| `t` | View taste analysis |
| `w` | Time-based mood recommendations |

#### Song Info

| Key | Function |
|-----|----------|
| `n` | Current song |
| `i` | Song recognition (Shazam-like) |
| `il` | Recognized songs list |

#### Song History (Auto)

Songs are automatically saved when track changes.

| Key | Function |
|-----|----------|
| `sl` | View song history |
| `st` | Toggle song history on/off |
| `sc` | Clear song history |

#### Favorites

| Key | Function |
|-----|----------|
| `f` | View favorites |
| `+` | Add to favorites |
| `-` | Remove from favorites |
| `<` | Previous favorite |
| `>` | Next favorite |
| `l` | Playlists |
| `pl name type` | Create playlist |

Playlist types: `favorites`, `history`, `mood`, `ai`, `tag:jazz`, `country:KR`

#### Playback

| Key | Function |
|-----|----------|
| `number` | Play station |
| `r` | Resume last station |
| `s` | Stop |
| `q` | Quit |

Auto-fetches latest URL on play (handles token expiration)

#### Volume Control

| Key | Function |
|-----|----------|
| `v` | Show volume |
| `v+` | Volume up |
| `v-` | Volume down |
| `v50` | Set volume to 50% |

#### DJ Mode

```bash
RADIOCLI_DJ=1 ./radio.py
```

| Key | Function |
|-----|----------|
| `d` | Toggle DJ mode |

Supports 10 languages: English, Korean, Japanese, French, German, Spanish, Chinese, Portuguese, Russian, Italian

### DB Management

```bash
./radio.py --db-stats    # DB statistics
./radio.py --cleanup     # Clean dead stations
```

## Multilingual Search

Supports 50+ languages including:

| Language | Example | Converts to |
|----------|---------|-------------|
| English | jazz, classical, news | jazz, classical, news |
| Korean | 재즈, 클래식, 뉴스 | jazz, classical, news |
| Japanese | ジャズ, クラシック | jazz, classical |
| Chinese | 爵士乐, 古典音乐 | jazz, classical |
| Russian | джаз, классика | jazz, classical |
| Arabic | موسيقى, أخبار | music, news |
| Hindi | संगीत, समाचार | music, news |

## Quality Filters

Include in search:

| Keyword | Filter |
|---------|--------|
| HQ, high quality | 192k+ |
| HD | 256k+ |
| LQ, low quality | 96k or less |

Example: `jazz HQ`

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `RADIOCLI_LLM` | LLM provider | `none` |
| `RADIOCLI_DJ` | DJ mode | `0` |
| `RADIOCLI_LANG` | UI language | auto |
| `RADIOCLI_VOICE` | TTS voice | `en-US-JennyNeural` |
| `OLLAMA_MODEL` | Ollama model | `llama3.2` |
| `OLLAMA_URL` | Ollama server | `http://localhost:11434` |
| `ANTHROPIC_API_KEY` | Claude API key | - |
| `OPENAI_API_KEY` | OpenAI API key | - |

## TTS Voices

| Voice | Language |
|-------|----------|
| `en-US-JennyNeural` | English (Female) |
| `ko-KR-SunHiNeural` | Korean (Female) |
| `ja-JP-NanamiNeural` | Japanese (Female) |
| `fr-FR-DeniseNeural` | French (Female) |
| `de-DE-KatjaNeural` | German (Female) |
| `zh-CN-XiaoxiaoNeural` | Chinese (Female) |

## Data Storage

```
~/.radiocli/
├── favorites.json        # Favorites
├── history.json          # Listening history (stations)
├── songs.json            # Song history (auto)
├── recognized_songs.json # Recognized songs
├── playlists.json        # Playlists
└── mpv.sock              # mpv socket

~/RadioCli/
└── radio_stations.db     # Station DB (51k+)
```

## Dependencies

- Python 3.10+
- mpv (required for CLI)
- ffmpeg (for song recording)
- chromaprint (for AcoustID)
- edge-tts (for DJ mode)
- ollama (for LLM, optional)

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for system architecture.

**Data Pipeline (g3 server):**
- Daily URL validation & new station sync
- Korean broadcaster URL resolvers (KBS, MBC, YTN)
- 51,000+ stations from Radio Browser, Icecast, TuneIn, Shoutcast

## License

MIT
