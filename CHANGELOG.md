# RadioCli / radiomcp - Changelog

## v1.0.0 (2026-03-02)

### MCP Server (radiomcp)

#### Core Features
- **24,671stations** DB includes (197items across countries)
- **search**: keyword, country, genre, mood based
- **playback**: mpv based, URL auto update (token expiration handling)
- **song recognition**: ICY metadata + Whisper
- **AI recommendation**: time of day, weather, listening patterns based

#### AI Helper Tools
- `get_radio_guide()` - AI  
- `get_categories()` -  rock (/news/sports)
- `get_listening_stats(period)` -   
- `check_stream(url)` - stream  
- `similar_stations()` -  broadcast recommendation
- `expand_search(query)` - search 

#### search items
- **country detect**: "korea news" → KR + news 
- **  search**: "news" + "news"   search
- **country  **: API  country  

#### rock
- `blocklist.json`  
- GitHub/Cloudflare   
- KBS/MBC/SBS rock (token based URL expiration)

#### auto 
- MCP   Radio Browser popular broadcast 
- URL changed  auto update

### CLI (radio.py)

- rock `blocklist.json` 
- KBS/MBC/SBS rock 

---

## 

### Claude Desktop (`claude_desktop_config.json`)
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

### PyPI  (rain)
```bash
pip install radiomcp
```

---

##  

```
RadioCli/
├── radiomcp/
│   ├── __init__.py
│   ├── server.py          # MCP  (103KB)
│   ├── blocklist.json     # rock
│   └── radio_stations.db  # broadcast DB (12MB)
├── radio.py               # CLI 
├── blocklist.json         # rock ()
├── pyproject.toml         # PyPI 
├── LICENSE                # MIT
├── DISCLAIMER.md          # disclaimer
└── README.md
```

---

## rock

###    (v1.0.1)
|  |  |
|------|------|
| Pyongyang, pyongyang, north korea, dprk, Korean Central | blocked content |
| KBS, MBC, SBS | token based URL expiration |

### rock  
GitHub Issues: https://github.com/meshpop/radiomcp/issues

---

##   (2026-03-02)

### MCP
|  |  |
|------|------|
| DB  | 24,671items broadcast, 197items across countries |
| jazz search | ✅ 101 Smooth Jazz  |
| korea search | ✅ CBS, Gugak FM, OBS  |
| rock | ✅ 8items  |
| KBS/MBC/SBS rock | ✅ |
| YTN/CBS  | ✅ |

### CLI
|  |  |
|------|------|
| rock  | ✅ 8items  |
| jazz search | ✅ |
| korea search | ✅ |
| KBS/MBC rock | ✅ |
| CLI  | ✅ |

---

## distribution rain

###  
- `dist/radiomcp-1.0.0-py3-none-any.whl` (3.8MB)
- `dist/radiomcp-1.0.0.tar.gz` (3.8MB)

### package 
|  |  |
|------|------|
| radio_stations.db | 11.5MB |
| server.py | 103KB |
| blocklist.json | 1KB |

### PyPI  
```bash
pip install twine
twine upload dist/*
```

---

##  

- [ ] PyPI  /
- [ ] PyPI 
- [ ] GitHub   (meshpop/radiomcp)
- [ ] Cloudflare Pages  (blocklist )
- [ ] MCP Registry rock
