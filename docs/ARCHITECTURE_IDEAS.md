# RadioCli Architecture Ideas

## Data Pipeline

### Current (g3)
```
04:00 radio_revalidate.py    - Existing station revalidation
05:00 sync_radiobrowser.py   - Radio Browser new/updated stations
```

### Data Sources
- Radio Browser API: 27K stations
- Icecast directory: 14K stations

---

## Search Architecture (Hybrid)

```
Search Request
    |
    +-> Local SQLite (primary, fast, 5ms)
    |   +-> N results
    |
    +-> API (supplementary, latest, 100ms)
        +-> M additional results

    v Merge (dedupe by UUID)

Final Results
```

### Implementation
```python
def search(query: str, limit: int = 10) -> list:
    # 1. Local first (always)
    local_results = search_local_db(query, limit=limit)

    # 2. Supplement with API if needed
    if len(local_results) < limit and API_ENABLED:
        api_results = search_api(query, limit=limit - len(local_results))

        # Dedupe by UUID
        seen = {r["id"] for r in local_results}
        for r in api_results:
            if r["id"] not in seen:
                local_results.append(r)

    return local_results
```

---

## DB Update Strategy

### Option A: Release-time update
- Update DB before each PyPI release
- Simple, no runtime complexity

### Option B: Manual update command
```bash
radiocli --update-db
```

### Option C: Auto-check on startup
```python
# Async, non-blocking
manifest = fetch("https://cdn/radio_db_version.json")
if manifest.version > local_version:
    print("New DB available. Run `radiocli --update-db`")
```

---

## Release Automation

### g3 (Daily)
```bash
# /opt/radiomcp/export_radio_db.sh
#!/bin/bash
sqlite3 radio_unified.db ".dump" | gzip > /var/www/radio_db.sql.gz
echo $(date +%Y%m%d) > /var/www/radio_db_version.txt
```

### GitHub Actions (Weekly)
```yaml
name: Release
on:
  schedule:
    - cron: '0 12 * * 0'  # Every Sunday
  workflow_dispatch:       # Manual trigger

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Download latest DB from g3
        run: |
          curl -o radio_db.sql.gz ${{ secrets.G3_DB_URL }}
          gunzip radio_db.sql.gz
          sqlite3 radiomcp/data/radio_stations.db < radio_db.sql

      - name: Bump version
        run: echo "VERSION=$(date +%Y.%-m.%-d)" >> $GITHUB_ENV

      - name: Build & Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
        run: |
          pip install build twine
          python -m build
          twine upload dist/*
```

### Version Naming
- Date-based: `2026.3.6`
- Or: `1.0.20260306`

---

## Environment Variables

```bash
# API integration (optional, disabled by default)
RADIOCLI_USE_API=true
RADIOCLI_API_URL=http://g3:8090

# G3 validator (personal use only)
G3_VALIDATOR_ENABLED=true
G3_VALIDATOR_URL=http://g3:8100/api/validate
```

---

## Future: Independent URL Discovery

See: URL_DISCOVERY.md
