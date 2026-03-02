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
| `i` | 곡 인식 |
| `il` | 인식된 곡 목록 |

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

### DJ 모드

```bash
RADIOCLI_DJ=1 ./radio.py
```

| 키 | 기능 |
|---|------|
| `d` | DJ 모드 토글 |

다국어 지원: 한국어, 영어, 일본어, 프랑스어, 독일어, 스페인어, 중국어, 포르투갈어, 러시아어, 이탈리아어

## 자연어 검색 예시

```
출근길 신나는 음악
잠들기 전 편안한 클래식
운동할 때 들을 음악
미국 재즈
일본 클래식
france jazz
deutschland klassik
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
├── favorites.json      # 즐겨찾기
├── history.json        # 청취 기록
├── playlists.json      # 플레이리스트
├── recognized_songs.json # 인식된 곡
└── mpv.sock            # mpv 소켓
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
