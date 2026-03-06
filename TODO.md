# RadioCli / Radio MCP - TODO

## Release

### 1. PyPI Package
- [x] `pyproject.toml` setup
- [x] Package name: `radiomcp`
- [ ] PyPI account setup
- [ ] Upload to PyPI (`pip install radiomcp`)

### 2. MCP Registry
- [ ] Register after PyPI upload
- [ ] https://registry.modelcontextprotocol.io metadata
- [ ] Version management

### 3. CI/CD
- [ ] GitHub Actions for PyPI auto-deploy (on tag push)
- [x] Blocklist: GitHub raw JSON
- [x] DB update: included in wheel

### 4. Legal
- [x] Disclaimer (DISCLAIMER.md)
- [x] Takedown request channel: GitHub Issues
- [x] Radio Browser API attribution

---

## Completed Features

### Player Support
- [x] Multi-player backend (mpv/vlc/ffplay/browser)
- [x] Auto-detection priority: mpv > vlc > ffplay > browser
- [x] Volume control (mpv IPC)
- [x] Claude Desktop watchdog (auto-stop when app closes)

### Search
- [x] Multilingual search (50+ languages)
- [x] Quality filters (HQ, HD, LQ)
- [x] Country + genre combined search
- [x] Tag expansion (related tags)

### MCP Tools
- [x] search, play, stop, get_current
- [x] get_favorites, add_favorite, remove_favorite, play_favorite
- [x] get_history, resume
- [x] set_volume, get_volume
- [x] check_station, share_station
- [x] set_sleep_timer, set_alarm
- [x] recommend (mood-based)

### CLI Features
- [x] Listening history display (`hl`)
- [x] Volume control (`v`, `v+`, `v-`, `v50`)
- [x] Station check (`check`)
- [x] Share station (`share`)
- [x] Search hint based on LLM availability
- [x] Sleep timer (`sleep N`)
- [x] Alarm (`alarm HH:MM genre`)

### Localization
- [x] UI: 100 languages
- [x] Search keywords: 50+ languages
- [x] Menu localization (ko, en, ja, zh)
- [x] README.md (English) + README.ko.md (Korean)

### Bug Fixes
- [x] mpv process not killed on stop() - fixed
- [x] Radio cuts off during conversation - fixed with process group separation
- [x] Shared PID file for MCP/CLI coordination

---

## Pending

### LLM Integration (CLI)
- [x] Default: keyword search only (`RADIOCLI_LLM=none`)
- [x] Optional: Ollama, Claude API, OpenAI API
- [x] Search hint changes based on LLM availability

### Documentation
- [x] README.md (English)
- [x] README.ko.md (Korean)
- [x] radiomcp/README.md (English)
- [x] radiomcp/HELP.md (English)
- [x] DISCLAIMER.md (Bilingual)

### Code Internationalization
- [x] Default language: English
- [x] All comments in English
- [x] All docstrings in English
- [ ] Korean UI only through language packs (languages.json)
- [x] Documentation in English (README.md, HELP.md)

---

## Future Ideas

- [ ] Equalizer presets
- [ ] Stream recording (legal concerns)
- [ ] Podcast support
- [ ] CarPlay / Android Auto integration
- [ ] Web UI

### Weather API Issue
- [x] `recommend_by_weather` - switched to Open-Meteo (stable) (timeout, connection reset)
- [x] Using: ip-api.com (location) + Open-Meteo (weather)
- [ ] Current fallback: time-based recommendation when weather API fails

### Infrastructure Architecture (Future)
- [ ] g3 (home server): URL validation, health checks, DB maintenance
- [ ] VPS: Public API service with clean DB
- [ ] Periodic sync: g3 → VPS (validated stations only)
- [ ] Batch jobs on g3: dead station cleanup, new station discovery
