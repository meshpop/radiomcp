# RadioCli / Radio MCP - TODO

## MCP 공개 배포

### 1. PyPI 패키지 등록
- [x] `pyproject.toml` 작성
- [x] 패키지 이름: `radiomcp`
- [ ] PyPI 계정 준비
- [ ] `pip install radiomcp`로 설치 가능하게 (테스트 완료, 업로드 필요)

### 2. MCP Registry 등록
- [ ] PyPI 등록 후 진행
- [ ] https://registry.modelcontextprotocol.io 에 메타데이터 등록
- [ ] 버전 관리 및 업데이트 알림

### 3. 자동 업데이트 체계
- [ ] GitHub Actions로 PyPI 자동 배포 (태그 푸시 시)
- [x] 블록 리스트: GitHub raw JSON (구현됨)
- [x] DB 업데이트: 새 버전 배포 시 포함 (wheel에 포함)

### 4. 법적 대응
- [x] 이용약관 / 면책 조항 작성 (DISCLAIMER.md)
- [x] 삭제 요청 채널: GitHub Issues
- [x] Radio Browser API 기반 명시

## 블록 리스트 관리

### 구현 완료
- [x] GitHub 원격 블록 리스트 (`blocklist.json`)
- [x] MCP 시작 시 자동 fetch
- [x] DB에서 블록된 방송 자동 삭제
- [x] `get_blocklist()` - 현재 블록 상태 조회
- [x] `refresh_blocklist()` - 수동 갱신

### 블록 유형
- 패턴 (이름 매칭): `평양`, `pyongyang` 등
- URL: 특정 스트림 URL
- UUID: Radio Browser API의 방송국 ID

---

## LLM 기능 정리 (배포 전 검토)

### 현재 LLM이 하는 일 (CLI)

| 기능 | 위치 | 설명 | MCP에서 필요? |
|------|------|------|---------------|
| `llm_parse_query()` | radio.py:570 | 자연어 → 구조화 (country, tags, mood) | ❌ Claude가 처리 |
| `llm_search()` | radio.py:703 | LLM 파싱 후 검색 | ❌ Claude가 처리 |
| AI 추천 (`a`) | 메인 루프 | 청취 기록 기반 추천 | ⚠️ 로직만 필요 |
| 취향 분석 (`t`) | 메인 루프 | 청취 패턴 분석 | ⚠️ 로직만 필요 |
| 곡 정보 추출 | radio.py:1932 | Whisper 텍스트에서 곡 파싱 | ❓ 검토 필요 |
| DJ 멘트 생성 | TTS 관련 | 방송/곡 소개 멘트 | ❌ CLI 전용 |

### LLM 제공자 (현재)
- `RADIOCLI_LLM` 환경변수: auto, ollama, claude, openai, none
- Ollama: 로컬 LLM (llama3.2 등)
- Claude API: Anthropic API 직접 호출
- OpenAI API: GPT 호출

### 배포 시 결정 필요
- [ ] MCP 버전: LLM 호출 전부 제거 (Claude가 처리)
- [ ] CLI 버전: Ollama 지원 유지? 아니면 단순화?
- [ ] 공통 로직 분리: 검색, 필터링, 재생 등
- [ ] `llm_parse_query()` 제거 또는 fallback으로만 유지

### MCP에서 Claude가 대체하는 것
- 자연어 이해 → Claude가 직접 파싱
- 추천 로직 → Claude가 history 보고 판단
- 분위기/시간대 추천 → Claude가 컨텍스트 파악
- 곡 정보 파싱 → Claude가 텍스트 분석

### CLI에서만 필요한 것
- DJ 모드 (TTS)
- 터미널 UI
- 로컬 LLM 연동 (오프라인 사용)
