# Radio API 아키텍처

## 개요

Radio API는 50,000개 이상의 라디오 방송국에 접근을 제공하며, 한국 방송사에 대해 실시간 URL 해석을 지원합니다.

## 아키텍처 다이어그램

```
┌─────────────────────────────────────────────────────────────────────┐
│                           클라이언트                                  │
│  (RadioCli, MCP 서버, 웹 앱, 모바일 앱)                              │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Radio API (g3:8092)                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │    검색     │  │   URL 해석  │  │   상태체크   │                 │
│  │  /search    │  │  /resolve   │  │  /stations  │                 │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │
│         │                │                │                         │
│         ▼                ▼                ▼                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    핵심 로직                                  │   │
│  │  - 쿼리 처리                                                  │   │
│  │  - URL 해석 (한국 방송)                                       │   │
│  │  - 건강 점수 계산                                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                    │                           │
        ┌───────────┴───────────┐               │
        ▼                       ▼               ▼
┌───────────────┐    ┌───────────────┐   ┌───────────────┐
│  SQLite DB    │    │   한국 방송    │   │   외부 API    │
│ radio_unified │    │   Resolvers   │   │               │
│    .db        │    │               │   │ - Radio       │
│               │    │ - KBS API     │   │   Browser     │
│ 50,000+       │    │ - MBC API     │   │ - Shoutcast   │
│ 방송국         │    │ - YTN API     │   │               │
│               │    │ - SBS (예정)   │   │               │
└───────────────┘    └───────────────┘   └───────────────┘
```

## 데이터 흐름

### 1. 일반 방송 검색

```
클라이언트 요청: GET /search?q=jazz
        │
        ▼
┌─────────────────────────────┐
│ 1. SQLite DB 쿼리           │
│    WHERE name LIKE '%jazz%' │
│    OR tags LIKE '%jazz%'    │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│ 2. 건강 점수 계산            │
│    - is_verified: +40       │
│    - bytes_received: +20    │
│    - bitrate >= 128: +20    │
│    - listeners > 0: +10     │
│    - votes > 0: +10         │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│ 3. JSON 응답 반환            │
│    {stations, total, ...}   │
└─────────────────────────────┘
```

### 2. 한국 방송 검색 (Resolver 사용)

```
클라이언트 요청: GET /search?q=KBS
        │
        ▼
┌─────────────────────────────┐
│ 1. SQLite DB 쿼리           │
│    resolver='kbs'인         │
│    방송국 찾기               │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│ 2. 한국 Resolver 호출        │
│    resolve_url('kbs',       │
│                'kbs1-radio')│
│                             │
│    KBS API 호출:             │
│    cfpwwwapi.kbs.co.kr      │
│    → 토큰 포함 새 URL 반환   │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│ 3. 응답에서 URL 교체         │
│    url = fresh_token_url    │
│    url_resolved = 동일      │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│ 4. JSON 응답 반환            │
│    {새 URL이 포함된          │
│     방송국 정보}             │
└─────────────────────────────┘
```

## API 엔드포인트

### 검색

```
GET /search?q={검색어}&limit={개수}&offset={오프셋}

응답:
{
  "total": 100,
  "limit": 30,
  "offset": 0,
  "data": [
    {
      "id": "station-uuid",
      "name": "방송국 이름",
      "url": "https://stream.url/...",
      "url_resolved": "https://actual.url/...",
      "country": "South Korea",
      "countrycode": "KR",
      "tags": "pop,music",
      "bitrate": 128,
      "health_score": 90,
      "health_grade": "A",
      "resolver": "kbs"  // 한국 방송인 경우
    }
  ]
}
```

### 국가별 방송

```
GET /stations?country={코드}&limit={개수}

예시: /stations?country=KR&limit=20
```

### 상태 체크

```
GET /health

응답:
{
  "status": "ok",
  "stations": 51614,
  "verified": 45000
}
```

## 데이터베이스 스키마

```sql
CREATE TABLE stations (
    id TEXT PRIMARY KEY,
    name TEXT,
    url TEXT,
    url_resolved TEXT,
    homepage TEXT,
    favicon TEXT,
    country TEXT,
    countrycode TEXT,
    language TEXT,
    tags TEXT,
    codec TEXT,
    bitrate INTEGER,
    votes INTEGER,
    clickcount INTEGER,
    listeners INTEGER,
    is_verified INTEGER,
    bytes_received INTEGER,
    source TEXT,
    resolver TEXT,        -- 'kbs', 'mbc', 'ytn' 등
    created_at TEXT,
    verified_at TEXT,
    is_blocked INTEGER
);
```

## 한국 방송 Resolvers

### 지원 방송사

| Resolver | 채널 | API 엔드포인트 |
|----------|------|--------------|
| `kbs` | 1라디오, 2라디오, 3라디오, 클래식FM, Cool FM, 한민족방송 | cfpwwwapi.kbs.co.kr |
| `mbc` | FM4U, 표준FM, 올댓뮤직 | sminiplay.imbc.com |
| `ytn` | 라디오, 사이언스 | 고정 URL |
| `sbs` | 파워FM, 러브FM | 예정 |

### Resolver 작동 방식

1. 방송국이 DB에 `resolver` 필드를 가짐 (예: `resolver='kbs'`)
2. 검색 결과에 방송국이 반환될 때:
   - `resolver` 필드 존재 확인
   - 해당 resolver 함수 호출
   - 유효한 토큰이 포함된 새 URL 획득
   - 응답의 `url`과 `url_resolved` 교체
3. 클라이언트는 즉시 작동하는 URL을 받음

### 토큰 만료 시간

- KBS: 약 5시간 유효 (CloudFront 서명 URL)
- MBC: 약 1시간 유효
- YTN: 고정 URL, 만료 없음

## 크론 작업

| 시간 | 작업 | 설명 |
|------|-----|-------------|
| 04:00 | radio_revalidate_v2.py | 모든 방송 URL 검증 |
| 05:00 | sync_radiobrowser.py | Radio Browser에서 신규 방송 동기화 |
| 06:00 일요일 | shoutcast_crawler.py | Shoutcast 디렉토리 크롤링 |

## 건강 점수 계산

```python
def calc_health(station):
    score = 0

    if station['is_verified']:
        score += 40

    if station['bytes_received'] > 4000:
        score += 20

    if station['bitrate'] >= 128:
        score += 20
    elif station['bitrate'] >= 64:
        score += 10

    if station['listeners'] > 0:
        score += 10

    if station['votes'] > 0:
        score += 10

    # 등급: A (80+), B (60+), C (40+), D (<40)
    return score
```

## 파일 구성

| 파일 | 위치 | 용도 |
|------|----------|---------|
| radio_api_v4.py | ~/radio_api_v4.py | 메인 API 서버 |
| korean_resolvers.py | ~/korean_resolvers.py | 한국 방송 URL 해석 |
| hls_validator.py | ~/hls_validator.py | HLS 스트림 검증 |
| radio_revalidate_v2.py | ~/radio_revalidate_v2.py | 매일 재검증 |
| radio_unified.db | ~/radio_unified.db | 메인 데이터베이스 |
| radio_blocklist.json | ~/radio_blocklist.json | 차단된 방송국 |
