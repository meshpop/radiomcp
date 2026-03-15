#!/bin/bash
# Radio DB Daily Maintenance
# Add to crontab: crontab -e
# 0 4 * * * /path/to/radiomcp/cron_maintenance.sh >> ~/.radiocli/maintenance.log 2>&1

cd "$(dirname "$0")"
python3 daily_maintenance.py
