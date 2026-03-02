#!/usr/bin/env python3
"""
Radio DB Daily Maintenance Script
크론잡으로 실행: 0 4 * * * /path/to/daily_maintenance.py

2주 사이클로 전체 DB 헬스체크
"""

import sys
import os

# 같은 디렉토리의 server 모듈 import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server

def log(msg):
    from datetime import datetime
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def main():
    log("=== Radio DB Daily Maintenance ===")

    # 1. DB 상태 확인
    stats = server.get_db_stats()
    log(f"현재 DB: {stats.get('total', 0)}개 (alive: {stats.get('alive', 0)}, dead: {stats.get('dead', 0)})")

    # 2. 신규 방송 동기화 (주요 국가)
    log("--- 신규 방송 동기화 ---")
    countries = ["KR", "US", "JP", "GB", "DE", "FR"]
    total_new = 0

    for code in countries:
        result = server.sync_with_api(country_code=code, limit=50)
        new = result.get("new", 0)
        total_new += new
        if new > 0:
            log(f"  {code}: +{new}개")

    # 3. 인기 장르 동기화
    tags = ["jazz", "classical", "pop", "rock", "electronic", "lounge"]
    for tag in tags:
        result = server.sync_with_api(tag=tag, limit=30)
        new = result.get("new", 0)
        total_new += new
        if new > 0:
            log(f"  {tag}: +{new}개")

    log(f"총 {total_new}개 신규 추가")

    # 4. 헬스체크 (500개 배치 - 부하 분산)
    log("--- 헬스체크 (500개) ---")
    health = server.health_check(limit=500)
    log(f"  checked: {health.get('checked', 0)}, alive: {health.get('alive', 0)}, dead: {health.get('dead', 0)}")

    # 5. 죽은 방송 정리
    dead_count = server.get_db_stats().get("dead", 0)
    if dead_count > 0:
        log(f"--- 죽은 방송 정리: {dead_count}개 ---")
        server.purge_dead()

    # 6. 최종 상태
    final = server.get_db_stats()
    log(f"=== 완료: {final.get('total', 0)}개 (alive: {final.get('alive', 0)}) ===")

if __name__ == "__main__":
    main()
