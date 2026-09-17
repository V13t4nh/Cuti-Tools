"""CLI utility to push local SQLite database to Cloudflare R2."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import sqlite3
from cuti.config import load_settings, parse_env_file
from cuti.r2 import download_from_r2, get_r2_config, upload_to_r2


def main() -> int:
    pull_mode = "--pull" in sys.argv or "--download" in sys.argv

    env_file = PROJECT_ROOT / ".env"
    env_vars = dict(os.environ)
    if env_file.is_file():
        # Load local .env without raising on unknown CUTI_* keys
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env_vars[k.strip()] = v.strip().strip("\"'")

    config = get_r2_config(env_vars)
    if not config:
        print("[ERROR] Missing R2 credentials in environment or .env file!", file=sys.stderr)
        print("Please configure in your .env:", file=sys.stderr)
        print("  R2_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com", file=sys.stderr)
        print("  R2_ACCESS_KEY_ID=<your_access_key>", file=sys.stderr)
        print("  R2_SECRET_ACCESS_KEY=<your_secret_key>", file=sys.stderr)
        print("  R2_BUCKET_NAME=cuti-data", file=sys.stderr)
        return 1

    settings = load_settings(env=env_vars, base_dir=PROJECT_ROOT)
    db_file = settings.db_path

    if pull_mode:
        print(f"[R2] Pulling latest database from R2 to {db_file}...")
        success = download_from_r2(db_file, config)
        return 0 if success else 1

    if not db_file.is_file():
        print(f"[ERROR] Database file not found at: {db_file}", file=sys.stderr)
        return 1

    # Checkpoint WAL before uploading to ensure all transactions are merged
    try:
        conn = sqlite3.connect(db_file)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
    except Exception as exc:
        print(f"[R2] WAL checkpoint notice: {exc}")

    success = upload_to_r2(db_file, config)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
