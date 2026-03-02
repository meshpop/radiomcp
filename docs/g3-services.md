# g3 Server Services

g3 서버에서 운영 중인 검증/데이터 서비스 목록.

## URL Validator API

**위치**: `/home/dragon/url_validator_api.py`
**포트**: 8100
**상태**: 운영 중

### 기능
- URL 종합 검증 (HTTP 상태, 응답시간, TTFB)
- 미디어 스트림 감지 (bitrate, audio format, stream name)
- 서버 IP 및 위치 조회
- 다운로드 속도 측정 (deep scan)
- 리다이렉트 추적

### API Endpoints

```bash
# 단일 URL 검증
GET http://g3:8100/api/validate?url={url}&deep_scan=true

# POST 방식
POST http://g3:8100/api/validate
{"url": "https://...", "deep_scan": true}

# 배치 검증 (최대 100개)
POST http://g3:8100/api/validate/batch
{"urls": ["url1", "url2", ...], "timeout": 10}
```

### 응답 예시
```json
{
  "url": "https://stream.example.com/live",
  "valid": true,
  "status_code": 200,
  "content_type": "audio/mpeg",
  "response_time_ms": 234,
  "ttfb_ms": 89,
  "is_media_stream": true,
  "bitrate": "128kbps",
  "audio_format": "MP3",
  "stream_name": "Example Radio",
  "server_ip": "1.2.3.4",
  "server_location": "Seoul, South Korea",
  "download_speed_kbps": 156.3
}
```

---

## RSS Feed Directory

**위치**: `/home/dragon/rss-directory/`
**DB**: `global_feeds.db` (1,171 피드)

### 파일 구조
```
rss-directory/
├── api.py              # FastAPI 서버
├── global_feeds.db     # 피드 DB (1,171개)
├── trends.db           # 트렌드 DB
├── collect_feeds.py    # 피드 수집
├── feed_discovery.py   # 피드 발견
├── auto_expand.py      # 자동 확장
├── trend_detector.py   # 트렌드 감지
└── dashboard.html      # 대시보드 UI
```

### DB 스키마 (feeds)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| url | TEXT | RSS URL (유니크) |
| title | TEXT | 피드 제목 |
| site_url | TEXT | 사이트 URL |
| language | TEXT | 언어 코드 |
| country_code | TEXT | 국가 코드 |
| category | TEXT | 카테고리 |
| feed_type | TEXT | 타입 (newspaper 등) |
| is_active | INT | 활성 여부 |
| entry_count | INT | 글 수 |
| error_count | INT | 오류 횟수 |
| last_checked | TEXT | 마지막 체크 |

### API Endpoints
```bash
# 통계
GET http://g3:{port}/api/stats

# 국가별 피드
GET http://g3:{port}/api/feeds?country=KR&limit=100

# 언어별 피드
GET http://g3:{port}/api/feeds?language=ko&limit=100

# 신문사 목록
GET http://g3:{port}/api/newspapers?country=KR
```

---

## Radio Stations DB

**위치**: `/home/dragon/radio_stations.db`
**크기**: 9.5MB (27,196개 → 정리 후 24,414개)

로컬에 복사해서 사용 중 (`~/RadioCli/radio_stations.db`)

### 관련 파일
- `radio_health.db` - 헬스체크 결과 (17MB)

---

## 활용 방안

1. **Radio MCP 헬스체크 강화**
   - 로컬 HEAD 요청 대신 g3 URL Validator 사용
   - 미디어 스트림 상세 정보 (bitrate, format) 수집

2. **RSS 피드 + 라디오 통합**
   - 뉴스 라디오 + 해당 국가 뉴스 피드 연동
   - 트렌드 기반 추천

3. **중앙 검증 서버**
   - g3에서 주기적으로 전체 URL 검증
   - 결과를 로컬 DB에 동기화
