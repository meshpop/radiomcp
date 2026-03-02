# Radio MCP Server

인터넷 라디오 검색 및 재생을 위한 MCP 서버

## 설치

```bash
cd radio-mcp
pip install -e .
```

## Claude Desktop 설정

`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "radio": {
      "command": "python",
      "args": ["/Users/dragon/RadioCli/radio-mcp/server.py"]
    }
  }
}
```

## 도구

| 도구 | 설명 |
|------|------|
| `search` | 라디오 검색 (장르, 이름 등) |
| `search_by_country` | 국가별 검색 |
| `get_popular` | 인기 방송국 |
| `play` | 라디오 재생 |
| `stop` | 정지 |
| `now_playing` | 현재 곡 정보 |
| `get_favorites` | 즐겨찾기 목록 |
| `add_favorite` | 즐겨찾기 추가 |
| `remove_favorite` | 즐겨찾기 삭제 |
| `get_history` | 청취 기록 |
| `recommend` | 분위기 기반 추천 |

## 사용 예시

Claude Desktop에서:
- "재즈 라디오 찾아줘"
- "한국 라디오 틀어줘"
- "지금 나오는 곡 뭐야?"
- "편안한 음악 추천해줘"
- "라디오 정지"

## 의존성

- Python 3.10+
- mpv (재생용)
- mcp[cli]
