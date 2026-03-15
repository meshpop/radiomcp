# RadioCli / radiomcp - Changelog

## v1.0.0 (2026-03-02)

### MCP Server (radiomcp)

#### Core Features
- **24,671stations** DB includes (197items across countries)
- **search**: keyword, country, genre, mood based
- **playback**: mpv based, URL auto update (token expiration handling)
- **song recognition**: ICY metadata + Whisper
- **AI 추천**: 시간대, 날씨, 청취 패턴 based

#### AI Helper Tools
- `get_radio_guide()` - AI용 사용 가이드
- `get_categories()` - 대분류 목rock (음악/news/sports)
- `get_listening_stats(period)` - 기간별 청취 통계
- `check_stream(url)` - stream 생존 확인
- `similar_stations()` - 유사 broadcast 추천
- `expand_search(query)` - search어 확장

#### search items선
- **country명 detect**: "korea news" → KR + news 필터
- **한글 태그 search**: "news" + "news" 둘 다 search
- **country 필터 강제**: API 결과도 country 필터 적용

#### 블rock리스트
- `blocklist.json`에서 동적 로드
- GitHub/Cloudflare 원격 업데이트 지원
- KBS/MBC/SBS 블rock (token based URL expiration)

#### auto 동기화
- MCP 시작 시 Radio Browser에서 popular broadcast 동기화
- URL 변경 시 auto update

### CLI (radio.py)

- 블rock리스트 `blocklist.json`에서 로드
- KBS/MBC/SBS 블rock 적용

---

## 설정

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

### PyPI 설치 (준rain됨)
```bash
pip install radiomcp
```

---

## 파일 구조

```
RadioCli/
├── radiomcp/
│   ├── __init__.py
│   ├── server.py          # MCP 서버 (103KB)
│   ├── blocklist.json     # 블rock리스트
│   └── radio_stations.db  # broadcast DB (12MB)
├── radio.py               # CLI 앱
├── blocklist.json         # 블rock리스트 (루트)
├── pyproject.toml         # PyPI 설정
├── LICENSE                # MIT
├── DISCLAIMER.md          # disclaimer
└── README.md
```

---

## 블rock리스트

### 현재 차단 패턴 (v1.0.1)
| 패턴 | 사유 |
|------|------|
| Pyongyang, pyongyang, north korea, dprk, Korean Central | blocked content |
| KBS, MBC, SBS | token based URL expiration |

### 블rock 요청 방법
GitHub Issues: https://github.com/meshpop/radiomcp/issues

---

## 테스트 결과 (2026-03-02)

### MCP
| 항목 | 결과 |
|------|------|
| DB 상태 | 24,671items broadcast, 197items across countries |
| jazz search | ✅ 101 Smooth Jazz 등 |
| korea search | ✅ CBS, Gugak FM, OBS 등 |
| 블rock리스트 | ✅ 8items 패턴 |
| KBS/MBC/SBS 블rock | ✅ |
| YTN/CBS 허용 | ✅ |

### CLI
| 항목 | 결과 |
|------|------|
| 블rock리스트 로드 | ✅ 8items 패턴 |
| jazz search | ✅ |
| korea search | ✅ |
| KBS/MBC 블rock | ✅ |
| CLI 실행 | ✅ |

---

## distribution 준rain

### 빌드 완료
- `dist/radiomcp-1.0.0-py3-none-any.whl` (3.8MB)
- `dist/radiomcp-1.0.0.tar.gz` (3.8MB)

### package 내용
| 파일 | 크기 |
|------|------|
| radio_stations.db | 11.5MB |
| server.py | 103KB |
| blocklist.json | 1KB |

### PyPI 업로드 명령
```bash
pip install twine
twine upload dist/*
```

---

## 다음 단계

- [ ] PyPI 계정 생성/로그인
- [ ] PyPI 업로드
- [ ] GitHub 레포 생성 (meshpop/radiomcp)
- [ ] Cloudflare Pages 설정 (blocklist 미러)
- [ ] MCP Registry 등rock
