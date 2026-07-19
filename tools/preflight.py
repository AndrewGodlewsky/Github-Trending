"""Preflight: confirm the required secrets are PRESENT — prints booleans only,
never the values. Run before the live phases."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from github_trending.config import load_config

cfg = load_config()
print("GITHUB_TOKEN present:     ", bool(cfg.github_token))
print("GOOGLE_API_KEY present:   ", bool(cfg.google_api_key))
print("ALERT_WEBHOOK_URL present:", bool(cfg.alert_webhook_url))
print("DATA_DIR:                 ", cfg.data_dir, "(exists:", cfg.data_dir.exists(), ")")
print("DB_PATH:                  ", cfg.db_path, "(exists:", cfg.db_path.exists(), ")")
