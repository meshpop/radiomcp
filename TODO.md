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

### Infrastructure Architecture
- [x] g3 (home server): URL validation, health checks, DB maintenance
- [ ] VPS: Public API service with clean DB
- [ ] Periodic sync: g3 → VPS (validated stations only)

### g3 Cron Jobs (Completed)
- [x] 04:00 daily: `radio_revalidate_v2.py` - HLS + regular stream validation
- [x] 05:00 daily: `sync_radiobrowser.py` - Radio Browser new/updated stations
- [x] 05:30 daily: `auto_broadcaster.py` - Major broadcaster sync
- [x] 06:00 Sunday: `shoutcast_crawler.py` - Shoutcast crawling

### Data Sources (radio_unified.db)
- [x] Radio Browser API: 27,196 stations
- [x] Icecast directory: 14,253 stations
- [x] TuneIn: 10,042 stations
- [x] Shoutcast: crawled weekly

### Auto Broadcaster System (Completed)
- [x] broadcaster_registry.json - broadcaster definitions
- [x] auto_broadcaster.py - auto sync system
- [x] KBS resolver (6 channels)
- [x] MBC resolver (3 channels)
- [x] YTN resolver (2 channels)
- [x] BBC direct URLs (10 channels)
- [x] NPR direct URLs (1 channel)
- [ ] SBS resolver (API research needed)
- [ ] NHK (geo-restricted to Japan)

### Independent URL Discovery (Future)
- [ ] IPTV M3U parser (iptv-org/iptv)
- [ ] Radio Garden sync (30K+ stations)
- [ ] GitHub playlist search
- [ ] User submission endpoint
- [ ] Web scraper for major broadcasters

---

## Future Improvements

### Search & API
- [ ] Hybrid search: Local SQLite + API supplementary
- [ ] Periodic DB download for clients
- [ ] `radiocli --update-db` command
- [ ] API rate limiting

### Broadcaster Expansion
- [ ] Add more countries' major broadcasters
- [ ] Auto-detect when broadcaster needs resolver
- [ ] Resolver health monitoring & alerts
- [ ] Fallback URL system

### Stream Validation
- [ ] HLS segment quality check (bitrate verification)
- [ ] Geo-restriction detection
- [ ] Stream metadata extraction improvement
- [ ] Parallel validation for speed

### User Features
- [ ] User submission portal
- [ ] Station rating/voting
- [ ] Listening statistics dashboard
- [ ] Personalized recommendations improvement

### Release Automation
- [ ] GitHub Actions: weekly PyPI release
- [ ] Auto DB update before release
- [ ] Version bump automation (date-based)
- [ ] Release notes generation

### Monetization Ideas (Low Priority)
- [ ] GitHub Sponsors
- [ ] B2B: Station monitoring service
- [ ] Premium features (recording, analytics)

See: docs/ARCHITECTURE_IDEAS.md, docs/URL_DISCOVERY.md, docs/API_ARCHITECTURE.md, docs/RADIO_API_RESEARCH.md
