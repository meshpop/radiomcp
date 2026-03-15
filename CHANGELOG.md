# RadioCli / radiomcp - Changelog

## v1.0.0 (2026-03-02)

### MCP Server (radiomcp)

#### 핵심 기능
- **24,671개 방송국** DB 포함 (197개국)
- **검색**: 키워드, 국가, 장르, 분위기 기반
- **재생**: mpv 기반, URL 자동 갱신 (토큰 만료 대응)
- **곡 인식**: ICY 메타데이터 + Whisper
- **AI 추천**: 시간대, 날씨, 청취 패턴 기반

#### AI Helper Tools
- `get_radio_guide()` - AI용 사용 가이드
- `get_categories()` - 대분류 목록 (음악/뉴스/스포츠)
- `get_listening_stats(period)` - 기간별 청취 통계
- `check_stream(url)` - 스트림 생존 확인
- `similar_stations()` - 유사 방송 추천
- `expand_search(query)` - 검색어 확장

#### 검색 개선
- **국가명 감지**: "한국 뉴스" → KR + news 필터
- **한글 태그 검색**: "뉴스" + "news" 둘 다 검색
- **국가 필터 강제**: API 결과도 국가 필터 적용

#### 블록리스트
- `blocklist.json`에서 동적 로드
- GitHub/Cloudflare 원격 업데이트 지원
- KBS/MBC/SBS 블록 (토큰 기반 URL 만료)

#### 자동 동기화
- MCP 시작 시 Radio Browser에서 인기 방송 동기화
- URL 변경 시 자동 갱신

### CLI (radio.py)

- 블록리스트 `blocklist.json`에서 로드
- KBS/MBC/SBS 블록 적용

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

### PyPI 설치 (준비됨)
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
│   ├── blocklist.json     # 블록리스트
│   └── radio_stations.db  # 방송 DB (12MB)
├── radio.py               # CLI 앱
├── blocklist.json         # 블록리스트 (루트)
├── pyproject.toml         # PyPI 설정
├── LICENSE                # MIT
├── DISCLAIMER.md          # 면책 조항
└── README.md
```

---

## 블록리스트

### 현재 차단 패턴 (v1.0.1)
| 패턴 | 사유 |
|------|------|
| 평양, pyongyang, north korea, dprk, 조선중앙 | blocked content |
| KBS, MBC, SBS | 토큰 기반 URL 만료 |

### 블록 요청 방법
GitHub Issues: https://github.com/meshpop/radiomcp/issues

---

## 테스트 결과 (2026-03-02)

### MCP
| 항목 | 결과 |
|------|------|
| DB 상태 | 24,671개 방송, 197개국 |
| jazz 검색 | ✅ 101 Smooth Jazz 등 |
| 한국 검색 | ✅ CBS, Gugak FM, OBS 등 |
| 블록리스트 | ✅ 8개 패턴 |
| KBS/MBC/SBS 블록 | ✅ |
| YTN/CBS 허용 | ✅ |

### CLI
| 항목 | 결과 |
|------|------|
| 블록리스트 로드 | ✅ 8개 패턴 |
| jazz 검색 | ✅ |
| 한국 검색 | ✅ |
| KBS/MBC 블록 | ✅ |
| CLI 실행 | ✅ |

---

## 배포 준비

### 빌드 완료
- `dist/radiomcp-1.0.0-py3-none-any.whl` (3.8MB)
- `dist/radiomcp-1.0.0.tar.gz` (3.8MB)

### 패키지 내용
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
- [ ] MCP Registry 등록
