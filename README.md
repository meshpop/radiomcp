# RadioCli

터미널에서 전세계 인터넷 라디오를 검색하고 듣는 CLI 앱

## 설치

```bash
# 필수
brew install mpv

# 선택 (곡 인식용)
brew install chromaprint ffmpeg
```

## 실행

```bash
./radio.py
```

## 사용법

### 검색

```
> 한국 재즈          # 자연어 검색
> 한국 뉴스 고음질    # 복합 검색
> 신나는 음악        # 분위기로 검색
> japan classical   # 다국어 지원
```

| 키 | 기능 |
|---|------|
| `g` | 장르 선택 |
| `c` | 국가 선택 |
| `p` | 인기 방송국 |
| `h` | 고음질 (256k+) |
| `r` | 프리미엄 |
| `/` | 검색 모드 |
| `!` | 검색 모드 토글 (DB만/DB+API) |

### 검색 모드

| 모드 | 속도 | 설명 |
|------|------|------|
| DB만 | 0.1초 | 로컬 DB (기본값) |
| DB+API | 1초+ | Radio Browser API 포함 |

`!` 키로 토글

### AI 추천

| 키 | 기능 |
|---|------|
| `a` | 내 취향 기반 추천 |
| `t` | 취향 분석 보기 |
| `w` | 시간대별 분위기 추천 |

### 곡 정보

| 키 | 기능 |
|---|------|
| `n` | 현재 곡 보기 |
| `i` | 곡 인식 (Shazam-like) |
| `il` | 인식된 곡 목록 |

### 곡 기록 (자동)

재생 중 곡이 바뀌면 자동 저장됨

| 키 | 기능 |
|---|------|
| `sl` | 곡 기록 보기 |
| `st` | 곡 기록 온/오프 |
| `sc` | 곡 기록 삭제 |

### 저장

| 키 | 기능 |
|---|------|
| `f` | 즐겨찾기 |
| `+` | 즐겨찾기 추가 |
| `l` | 플레이리스트 |
| `pl 이름 타입` | 플레이리스트 생성 |

플레이리스트 타입: `favorites`, `history`, `mood`, `ai`, `tag:jazz`, `country:KR`

### 재생

| 키 | 기능 |
|---|------|
| `번호` | 재생 |
| `s` | 정지 |
| `q` | 종료 |

재생 시 자동으로 최신 URL 가져옴 (토큰 만료 대응)

### DJ 모드

```bash
RADIOCLI_DJ=1 ./radio.py
```

| 키 | 기능 |
|---|------|
| `d` | DJ 모드 토글 |

다국어 지원: 한국어, 영어, 일본어, 프랑스어, 독일어, 스페인어, 중국어, 포르투갈어, 러시아어, 이탈리아어

### DB 관리

```bash
./radio.py --db-stats    # DB 통계
./radio.py --cleanup     # 죽은 방송 정리
```

## 다국어 검색

| 언어 | 예시 | 변환 |
|------|------|------|
| 한국어 | 재즈, 클래식, 뉴스, 시사 | jazz, classical, news |
| 일본어 | ジャズ, クラシック | jazz, classical |
| 중국어 | 爵士乐, 古典音乐 | jazz, classical |
| 한국어 | 한국, 미국, 일본 | KR, US, JP |

## 품질 필터

검색어에 포함 가능:

| 키워드 | 필터 |
|--------|------|
| 고음질, HQ | 192k+ |
| 최고음질, HD | 256k+ |
| 저음질, LQ | 96k 이하 |

예: `한국 재즈 고음질`

## 자연어 검색 예시

```
출근길 신나는 음악
잠들기 전 편안한 클래식
운동할 때 들을 음악
미국 재즈
일본 클래식
france jazz
deutschland klassik
한국 뉴스
```

## LLM 설정

```bash
# 로컬 Ollama (기본)
./radio.py

# Claude API
ANTHROPIC_API_KEY=xxx ./radio.py

# OpenAI API
OPENAI_API_KEY=xxx ./radio.py

# LLM 없이 키워드만
RADIOCLI_LLM=none ./radio.py
```

## 환경변수

| 변수 | 설명 | 기본값 |
|-----|------|-------|
| `RADIOCLI_LLM` | LLM 제공자 | `auto` |
| `RADIOCLI_DJ` | DJ 모드 | `0` |
| `RADIOCLI_VOICE` | TTS 음성 | `ko-KR-SunHiNeural` |
| `OLLAMA_MODEL` | Ollama 모델 | `llama3.2` |
| `OLLAMA_URL` | Ollama 서버 | `http://localhost:11434` |
| `ANTHROPIC_API_KEY` | Claude API 키 | - |
| `OPENAI_API_KEY` | OpenAI API 키 | - |

## TTS 음성

| 음성 | 언어 |
|-----|-----|
| `ko-KR-SunHiNeural` | 한국어 여성 |
| `ko-KR-InJoonNeural` | 한국어 남성 |
| `en-US-JennyNeural` | 영어 여성 |
| `ja-JP-NanamiNeural` | 일본어 여성 |
| `fr-FR-DeniseNeural` | 프랑스어 여성 |
| `de-DE-KatjaNeural` | 독일어 여성 |
| `zh-CN-XiaoxiaoNeural` | 중국어 여성 |

## 데이터 저장 위치

```
~/.radiocli/
├── favorites.json        # 즐겨찾기
├── history.json          # 청취 기록 (방송국)
├── songs.json            # 곡 기록 (자동)
├── recognized_songs.json # 인식된 곡
├── playlists.json        # 플레이리스트
└── mpv.sock              # mpv 소켓

~/RadioCli/
└── radio_stations.db     # 방송국 DB (24k+)
```

## 의존성

- Python 3
- mpv (필수)
- ffmpeg (곡 녹음용)
- chromaprint (AcoustID용)
- edge-tts (DJ 모드용)
- ollama (LLM용, 선택)

## 라이선스

MIT
