"""Send one test message to your Discord channel to confirm ALERT_WEBHOOK_URL works.
Run AFTER pasting the webhook URL into .env:  uv run python tools/test_alert.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from github_trending.alerts import notify
from github_trending.config import load_config, require

cfg = load_config()
url = require(cfg.alert_webhook_url, "ALERT_WEBHOOK_URL")
notify(url, "✅ github-trending: webhook connected. This is a test alert — daily-run "
            "failures will show up here.")
print("Sent. Check your Discord channel for the test message.")
