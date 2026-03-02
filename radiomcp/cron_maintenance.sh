#!/bin/bash
# Radio DB Daily Maintenance
# 크론탭 등록: crontab -e
# 0 4 * * * /Users/dragon/RadioCli/radio-mcp/cron_maintenance.sh >> ~/.radiocli/maintenance.log 2>&1

cd /Users/dragon/RadioCli/radio-mcp
/Users/dragon/.pyenv/versions/3.11.9/bin/python3 daily_maintenance.py
