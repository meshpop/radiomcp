# RadioCli / Radio MCP - TODO

## MCP 공개 배포

### 1. PyPI 패키지 등록
- [ ] `setup.py` 또는 `pyproject.toml` 작성
- [ ] 패키지 이름 결정 (예: `radiomcp`)
- [ ] PyPI 계정 준비
- [ ] `pip install radiomcp`로 설치 가능하게

### 2. MCP Registry 등록
- [ ] PyPI 등록 후 진행
- [ ] https://registry.modelcontextprotocol.io 에 메타데이터 등록
- [ ] 버전 관리 및 업데이트 알림

### 3. 자동 업데이트 체계
- [ ] GitHub Actions로 PyPI 자동 배포 (태그 푸시 시)
- [ ] 블록 리스트: GitHub raw JSON (이미 구현됨)
- [ ] DB 업데이트: 새 버전 배포 시 포함

### 4. 법적 대응
- [ ] 이용약관 / 면책 조항 작성
- [ ] 삭제 요청 채널 (이메일 등) 준비
- [ ] Radio Browser API 기반 명시

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
