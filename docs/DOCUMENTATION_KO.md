# RadioCli & Radio MCP Server - 전체 문서

## 개요

RadioCli는 24,000개 이상의 검증된 방송국을 지원하는 터미널 기반 인터넷 라디오 플레이어입니다. 두 가지 구성 요소로 이루어져 있습니다:

1. **RadioCli (CLI)** - 터미널 애플리케이션으로 직접 라디오 재생
2. **Radio MCP Server** - AI 어시스턴트 연동을 위한 MCP 서버

두 구성 요소는 동일한 SQLite 데이터베이스를 공유하며, 다국어 검색, 곡 인식, 개인화 추천을 지원합니다.

---

## 아키텍처

```
+---------------------------+---------------------------+
|      CLI (radio.py)       |    MCP Server (server.py) |
|      - Terminal UI        |    - Claude Desktop       |
|      - Direct input       |    - Natural language     |
+-------------+-------------+-------------+-------------+
              |                           |
              v                           v
+-----------------------------------------------------------+
|                     Core Components                        |
+-----------------------------------------------------------+
|  SQLite DB        |  Radio Browser API  |  mpv Player     |
|  (24k+ stations)  |  (fallback search)  |  (IPC socket)   |
+-------------------+---------------------+-----------------+
|  Favorites/History (JSON)  |  Song Recognition (AcoustID) |
+----------------------------+------------------------------+
|  DJ Mode (edge-tts)        |  LLM Integration (optional)  |
+----------------------------+------------------------------+
```

---

## 파일 구조

```
RadioCli/
|-- radio.py                 # 메인 CLI 애플리케이션
|-- radio_stations.db        # SQLite 데이터베이스 (24k+ 방송)
|-- languages.json           # UI 번역 (ko, en, ja, zh)
|-- README.md                # 프로젝트 README
|
|-- radio-mcp/               # MCP 서버
|   |-- server.py            # MCP 서버 구현
|   |-- README.md            # MCP 설정 가이드
|   |-- HELP.md              # MCP 도구 레퍼런스
|   +-- daily_maintenance.py # DB 유지보수 스크립트
|
+-- docs/                    # 문서
    |-- DOCUMENTATION.md     # 영문 문서
    +-- DOCUMENTATION_KO.md  # 한글 문서

~/.radiocli/                 # 사용자 데이터 디렉토리
|-- favorites.json           # 즐겨찾기 방송
|-- history.json             # 청취 기록
|-- playlists.json           # 사용자 플레이리스트
|-- recognized_songs.json    # 곡 인식 기록
|-- songs.json               # 자동 추적 곡 (CLI)
|-- last_station.json        # 마지막 재생 (이어듣기용)
+-- mpv.sock                 # mpv IPC 소켓 (런타임)
```

---

## 데이터베이스 구조

### 위치
- **데이터베이스**: `~/RadioCli/radio_stations.db`
- **사용자 데이터**: `~/.radiocli/`

### 스키마

```sql
CREATE TABLE stations (
    stationuuid TEXT PRIMARY KEY,  -- 방송국 고유 ID
    name TEXT,                      -- 방송국 이름
    url TEXT,                       -- 스트림 URL
    url_resolved TEXT,              -- 리다이렉트된 실제 URL
    country TEXT,                   -- 국가명
    countrycode TEXT,               -- 국가 코드 (KR, US 등)
    tags TEXT,                      -- 장르 태그 (쉼표 구분)
    bitrate INTEGER,                -- 비트레이트 (kbps)
    votes INTEGER,                  -- 투표 수
    clickcount INTEGER,             -- 클릭 수 (인기도)
    is_alive INTEGER DEFAULT 1,     -- 생존 여부
    fail_count INTEGER DEFAULT 0,   -- 연속 실패 횟수
    last_checked TEXT               -- 마지막 체크 시간
);
```

### 데이터 파일

| 파일 | 설명 |
|------|------|
| `favorites.json` | 즐겨찾기 방송 |
| `history.json` | 방송 청취 기록 |
| `songs.json` | 자동 추적 곡 기록 (CLI) |
| `recognized_songs.json` | 인식된 곡 기록 |
| `playlists.json` | 사용자 플레이리스트 |
| `last_station.json` | 마지막 재생 방송 (이어듣기용) |

---

## 검색 시스템

### 검색 모드

| 모드 | 속도 | 설명 |
|------|------|------|
| DB만 | ~0.1초 | 로컬 SQLite 검색 (기본값) |
| DB+API | ~1.0초 | 로컬 + Radio Browser API |

CLI에서 `!` 키로 전환 가능.

### 검색 흐름

```
사용자 쿼리: "한국 재즈 고음질"
         │
         ▼
┌─────────────────────────────┐
│  1. 쿼리 파싱               │
│  - "한국" → country: KR     │
│  - "재즈" → tag: jazz       │
│  - "고음질" → min_bitrate:192│
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│  2. 검색 실행               │
│  - DB 검색 (즉시)           │
│  - API 검색 (활성화 시)     │
│  - 병합 & 중복 제거         │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│  3. 필터 & 정렬             │
│  - 비트레이트 필터 적용     │
│  - 차단 방송 제거           │
│  - 품질/투표순 정렬         │
└─────────────────────────────┘
```

### 다국어 지원

| 언어 | 국가 예시 | 장르 예시 |
|------|-----------|-----------|
| 한국어 | 한국, 미국, 일본, 영국 | 재즈, 클래식, 뉴스, 팝 |
| 일본어 | 日本, アメリカ, 韓国 | ジャズ, クラシック |
| 중국어 | 中国, 美国, 韩国 | 爵士乐, 古典音乐 |
| 독일어 | Deutschland, Amerika | Jazz, Klassik |
| 프랑스어 | France, Allemagne | Jazz, Classique |

### 연관 용어 확장

```python
TAG_EXPAND = {
    "news": ["news", "talk", "information"],  # 뉴스 검색 시 talk, information도 포함
    "jazz": ["jazz", "smooth jazz", "bebop", "swing"],
    "classical": ["classical", "orchestra", "symphony"],
    "electronic": ["electronic", "edm", "techno", "house"],
}
```

추가 한국어 매핑:
- "시사", "교양", "보도" → news
- "토크쇼", "라디오쇼" → talk

### 품질 필터

| 키워드 | 필터 |
|--------|------|
| 고음질, HQ, high quality | min_bitrate: 192 |
| 최고음질, HD | min_bitrate: 256 |
| 저음질, LQ | max_bitrate: 96 |

---

## 재생 시스템

### 자동 URL 갱신

토큰 기반 스트림(KBS, MBC 등)은 자주 만료됩니다. 시스템이 자동으로:

1. 재생 전 Radio Browser API에서 최신 URL 조회
2. 새 URL로 로컬 DB 업데이트
3. API 실패 시 캐시된 URL 사용

### 곡 추적

재생 중 곡이 자동으로 기록됩니다:

```json
{
  "artist": "Norah Jones",
  "title": "Come Away With Me",
  "station": "Smooth Jazz FM",
  "timestamp": "2024-03-02T14:30:00"
}
```

스트림의 `icy-title`에서 메타데이터 파싱 (형식: "아티스트 - 제목").

### 곡 인식

여러 인식 방법 지원:

1. **스트림 메타데이터** - `icy-title`에서 아티스트/제목 파싱
2. **AcoustID** - 오디오 핑거프린팅 (chromaprint 필요)
3. **Whisper** - DJ 멘트에서 음성-텍스트 변환

---

## 차단 목록

영구 차단된 방송:

```python
BLOCK_LIST = ["평양", "pyongyang", "north korea", "dprk", "조선중앙"]
```

차단된 방송은:
- DB에 저장되지 않음
- 검색 결과에서 필터링
- 재생 불가

---

## CLI 명령어

### 메인 메뉴

```
RadioCli (DB)

a AI추천   t 취향   p 인기   h 고음질
g 장르     c 국가   f 즐찾(2)  l 리스트
w 분위기   i 인식   n 현재곡  sl 곡(0)
r 이어듣기 s 정지   < 이전   > 다음
q 종료     ! 모드   d DJ
```

### 명령어 참조

| 키 | 기능 |
|----|------|
| `a` | 청취 기록 기반 AI 추천 |
| `t` | 취향 분석 보기 |
| `w` | 시간대별 분위기 추천 |
| `i` | 현재 곡 인식 (Shazam처럼) |
| `p` | 인기 방송 |
| `h` | 고음질 방송 (256k+) |
| `g` | 장르 선택 |
| `c` | 국가 선택 |
| `f` | 즐겨찾기 |
| `+` | 즐겨찾기 추가 |
| `-` | 즐겨찾기 제거 |
| `<` | 이전 즐겨찾기 |
| `>` | 다음 즐겨찾기 |
| `l` | 플레이리스트 |
| `n` | 현재 곡 보기 |
| `sl` | 곡 기록 보기 |
| `st` | 곡 추적 온/오프 |
| `sc` | 곡 기록 삭제 |
| `r` | 이어듣기 (마지막 방송) |
| `s` | 정지 |
| `q` | 종료 |
| `!` | 검색 모드 전환 (DB/API) |
| `d` | DJ 모드 전환 |
| `lang` | 언어 변경 |

### 자연어 검색

```
> 한국 재즈
> 신나는 음악
> japan classical
> relaxing lounge
> 미국 뉴스 고음질
```

---

## MCP 서버 도구

### 검색 도구

| 도구 | 매개변수 | 설명 |
|------|----------|------|
| `search` | query, limit | 키워드 검색 |
| `search_by_country` | country_code, limit | 국가별 검색 |
| `advanced_search` | country, tag, min_bitrate, max_bitrate | 복합 필터 |
| `get_popular` | limit | 인기순 방송 |
| `recommend` | mood | 분위기별 검색 |

### 재생 도구

| 도구 | 매개변수 | 설명 |
|------|----------|------|
| `play` | url, name | 방송 재생 |
| `stop` | - | 정지 |
| `resume` | - | 마지막 방송 이어듣기 |
| `now_playing` | - | 현재 곡 정보 |
| `set_volume` | volume (0-100) | 볼륨 조절 |

### 인식 도구

| 도구 | 매개변수 | 설명 |
|------|----------|------|
| `recognize_song` | duration | 현재 곡 인식 |
| `get_recognized_songs` | limit | 인식 기록 |

### 즐겨찾기 & 기록

| 도구 | 매개변수 | 설명 |
|------|----------|------|
| `get_favorites` | - | 즐겨찾기 목록 |
| `add_favorite` | station | 즐겨찾기 추가 |
| `remove_favorite` | index | 즐겨찾기 삭제 |
| `get_history` | limit | 청취 기록 |

### 개인화

| 도구 | 매개변수 | 설명 |
|------|----------|------|
| `get_user_profile` | - | 청취 패턴 분석 |
| `personalized_recommend` | limit | AI 추천 |
| `recommend_by_weather` | city | 날씨 기반 추천 |
| `get_similar` | station_name | 유사 방송 찾기 |

### 유틸리티

| 도구 | 매개변수 | 설명 |
|------|----------|------|
| `sleep_timer` | minutes | 자동 정지 타이머 |
| `set_alarm` | time, genre | 알람 설정 |

### 데이터베이스 관리

| 도구 | 매개변수 | 설명 |
|------|----------|------|
| `get_db_stats` | - | DB 통계 |
| `health_check` | limit | 방송 URL 확인 |
| `purge_dead` | - | 죽은 방송 삭제 |
| `sync_with_api` | country_code, tag | Radio Browser에서 동기화 |

---

## 세션 생명주기

### MCP 서버

```
Claude Code 시작
       │
       ▼
┌─────────────────┐
│ MCP 서버 초기화 │
│ - DB 로드       │
│ - 인덱스 구축   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 사용자 명령     │◄──┐
│ - search()      │   │
│ - play()        │   │
│ - now_playing() │───┘
└────────┬────────┘
         │
         ▼ (종료)
┌─────────────────┐
│ 정리            │
│ - 마지막 저장   │
│ - mpv 종료      │
│ - 소켓 삭제     │
└─────────────────┘
```

### 이어듣기 기능

마지막 재생 방송이 종료 시 `last_station.json`에 저장됩니다.
다음 세션에서 `resume()`으로 이어서 재생할 수 있습니다.

---

## 요구사항

### 필수

- Python 3.8+
- mpv (`brew install mpv`)

### 선택

- chromaprint (`brew install chromaprint`) - AcoustID 인식
- ffmpeg (`brew install ffmpeg`) - 오디오 녹음
- edge-tts (`pip install edge-tts`) - DJ 모드 TTS
- ollama - 로컬 LLM (고급 파싱용)

---

## 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `RADIOCLI_LLM` | LLM 제공자 (auto/ollama/claude/none) | auto |
| `RADIOCLI_DJ` | DJ 모드 활성화 | 0 |
| `RADIOCLI_LANG` | UI 언어 | ko |
| `OLLAMA_MODEL` | Ollama 모델명 | llama3.2 |
| `ANTHROPIC_API_KEY` | Claude API 키 | - |
| `OPENAI_API_KEY` | OpenAI API 키 | - |

---

## 성능

| 작업 | DB만 | DB+API |
|------|------|--------|
| 검색 | ~0.1초 | ~1.0초 |
| 재생 | ~2.0초 | ~2.0초 |
| 곡 정보 | <0.1초 | <0.1초 |

DB만 모드가 10배 빠르며 일반 사용에 권장됩니다.

---

## 라이선스

MIT
