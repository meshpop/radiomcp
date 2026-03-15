# Radio API Architecture

## Overview

The Radio API provides access to 50,000+ radio stations with real-time URL resolution for Korean broadcasters.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Clients                                    │
│  (RadioCli, MCP Server, Web App, Mobile App)                        │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Radio API (g3:8092)                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │   Search    │  │   Resolve   │  │   Health    │                 │
│  │  /search    │  │  /resolve   │  │  /stations  │                 │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │
│         │                │                │                         │
│         ▼                ▼                ▼                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Core Logic                                │   │
│  │  - Query Processing                                          │   │
│  │  - URL Resolution (Korean stations)                          │   │
│  │  - Health Scoring                                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                    │                           │
        ┌───────────┴───────────┐               │
        ▼                       ▼               ▼
┌───────────────┐    ┌───────────────┐   ┌───────────────┐
│  SQLite DB    │    │   Korean      │   │  External     │
│ radio_unified │    │   Resolvers   │   │  APIs         │
│    .db        │    │               │   │               │
│               │    │ - KBS API     │   │ - Radio       │
│ 50,000+       │    │ - MBC API     │   │   Browser     │
│ stations      │    │ - YTN API     │   │ - Shoutcast   │
│               │    │ - SBS (TODO)  │   │               │
└───────────────┘    └───────────────┘   └───────────────┘
```

## Data Flow

### 1. Regular Station Search

```
Client Request: GET /search?q=jazz
        │
        ▼
┌─────────────────────────────┐
│ 1. Query SQLite DB          │
│    WHERE name LIKE '%jazz%' │
│    OR tags LIKE '%jazz%'    │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│ 2. Calculate Health Score   │
│    - is_verified: +40       │
│    - bytes_received: +20    │
│    - bitrate >= 128: +20    │
│    - listeners > 0: +10     │
│    - votes > 0: +10         │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│ 3. Return JSON Response     │
│    {stations, total, ...}   │
└─────────────────────────────┘
```

### 2. Korean Station Search (with Resolver)

```
Client Request: GET /search?q=KBS
        │
        ▼
┌─────────────────────────────┐
│ 1. Query SQLite DB          │
│    Find stations with       │
│    resolver='kbs'           │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│ 2. Call Korean Resolver     │
│    resolve_url('kbs',       │
│                'kbs1-radio')│
│                             │
│    KBS API Call:            │
│    cfpwwwapi.kbs.co.kr      │
│    → Returns fresh URL      │
│      with token             │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│ 3. Replace URL in Response  │
│    url = fresh_token_url    │
│    url_resolved = same      │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│ 4. Return JSON Response     │
│    {stations with fresh     │
│     URLs}                   │
└─────────────────────────────┘
```

## API Endpoints

### Search

```
GET /search?q={query}&limit={n}&offset={n}

Response:
{
  "total": 100,
  "limit": 30,
  "offset": 0,
  "data": [
    {
      "id": "station-uuid",
      "name": "Station Name",
      "url": "https://stream.url/...",
      "url_resolved": "https://actual.url/...",
      "country": "South Korea",
      "countrycode": "KR",
      "tags": "pop,music",
      "bitrate": 128,
      "health_score": 90,
      "health_grade": "A",
      "resolver": "kbs"  // if Korean station
    }
  ]
}
```

### Stations by Country

```
GET /stations?country={code}&limit={n}

Example: /stations?country=KR&limit=20
```

### Health Check

```
GET /health

Response:
{
  "status": "ok",
  "stations": 51614,
  "verified": 45000
}
```

## Database Schema

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
    resolver TEXT,        -- 'kbs', 'mbc', 'ytn', etc.
    created_at TEXT,
    verified_at TEXT,
    is_blocked INTEGER
);
```

## Korean Resolvers

### Supported Broadcasters

| Resolver | Channels | API Endpoint |
|----------|----------|--------------|
| `kbs` | Radio 1, Radio 2, Radio 3, classicalFM, Cool FM, Korean Broadcasting System | cfpwwwapi.kbs.co.kr |
| `mbc` | FM4U, Standard FM, All That Music | sminiplay.imbc.com |
| `ytn` | radio, science | Static URLs |
| `sbs` | Power FM, Love FM | TODO |

### How Resolvers Work

1. Station has `resolver` field in DB (e.g., `resolver='kbs'`)
2. When station is returned in search results:
   - Check if `resolver` field exists
   - Call appropriate resolver function
   - Get fresh URL with valid token
   - Replace `url` and `url_resolved` in response
3. Client receives working URL immediately

### Token Expiration

- KBS: URLs valid for ~5 hours (CloudFront signed URL)
- MBC: URLs valid for ~1 hour
- YTN: Static URLs, no expiration

## Cron Jobs

| Time | Job | Description |
|------|-----|-------------|
| 04:00 | radio_revalidate_v2.py | Validate all station URLs |
| 05:00 | sync_radiobrowser.py | Sync new stations from Radio Browser |
| 06:00 Sun | shoutcast_crawler.py | Crawl Shoutcast directory |

## Health Scoring

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

    # Grade: A (80+), B (60+), C (40+), D (<40)
    return score
```

## Files

| File | Location | Purpose |
|------|----------|---------|
| radio_api_v4.py | ~/radio_api_v4.py | Main API server |
| korean_resolvers.py | ~/korean_resolvers.py | Korean URL resolvers |
| hls_validator.py | ~/hls_validator.py | HLS stream validation |
| radio_revalidate_v2.py | ~/radio_revalidate_v2.py | Daily revalidation |
| radio_unified.db | ~/radio_unified.db | Main database |
| radio_blocklist.json | ~/radio_blocklist.json | Blocked stations |
