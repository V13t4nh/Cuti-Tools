"""Cloudflare R2 (S3-compatible) storage sync helper.

Implements lightweight AWS SigV4 in pure Python standard library so no external
dependencies (like boto3) are strictly required.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import os
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Mapping


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _get_signature_key(secret_key: str, date_stamp: str, region: str = "auto", service: str = "s3") -> bytes:
    k_date = _sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    return _sign(k_service, "aws4_request")


def get_r2_config(env: Mapping[str, str] | None = None) -> dict[str, str] | None:
    """Read R2 configuration from environment or .env file."""
    source = os.environ if env is None else env
    endpoint = source.get("R2_ENDPOINT_URL", "").strip().rstrip("/")
    access_key = source.get("R2_ACCESS_KEY_ID", "").strip()
    secret_key = source.get("R2_SECRET_ACCESS_KEY", "").strip()
    bucket = source.get("R2_BUCKET_NAME", "cuti-data").strip()
    key = source.get("R2_OBJECT_KEY", "auctions.db").strip()

    if not (endpoint and access_key and secret_key):
        return None

    return {
        "endpoint": endpoint,
        "access_key": access_key,
        "secret_key": secret_key,
        "bucket": bucket,
        "key": key,
    }


def _build_sigv4_request(
    method: str,
    endpoint: str,
    bucket: str,
    key: str,
    access_key: str,
    secret_key: str,
    body: bytes = b"",
    region: str = "auto",
) -> urllib.request.Request:
    parsed_endpoint = urllib.parse.urlparse(endpoint)
    host = parsed_endpoint.netloc
    canonical_uri = f"/{bucket}/{key}"
    url = f"{endpoint}{canonical_uri}"

    now = datetime.datetime.now(datetime.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    payload_hash = hashlib.sha256(body).hexdigest()

    canonical_headers = (
        f"host:{host}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amz_date}\n"
    )
    signed_headers = "host;x-amz-content-sha256;x-amz-date"

    canonical_request = (
        f"{method}\n"
        f"{canonical_uri}\n"
        f"\n"
        f"{canonical_headers}\n"
        f"{signed_headers}\n"
        f"{payload_hash}"
    )

    algorithm = "AWS4-HMAC-SHA256"
    credential_scope = f"{date_stamp}/{region}/s3/aws4_request"
    string_to_sign = (
        f"{algorithm}\n"
        f"{amz_date}\n"
        f"{credential_scope}\n"
        f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
    )

    signing_key = _get_signature_key(secret_key, date_stamp, region)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    auth_header = (
        f"{algorithm} Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    headers = {
        "x-amz-date": amz_date,
        "x-amz-content-sha256": payload_hash,
        "Authorization": auth_header,
    }
    if method == "PUT":
        headers["Content-Type"] = "application/octet-stream"

    return urllib.request.Request(url, data=body if method == "PUT" else None, headers=headers, method=method)


def upload_to_r2(source_file: Path, config: dict[str, str] | None = None) -> bool:
    """Upload a local database file to Cloudflare R2."""
    cfg = config or get_r2_config()
    if not cfg:
        print("[R2] Missing R2 credentials (R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY)", file=sys.stderr)
        return False

    if not source_file.is_file():
        print(f"[R2] File not found: {source_file}", file=sys.stderr)
        return False

    file_size_mb = source_file.stat().st_size / (1024 * 1024)
    print(f"[R2] Uploading {source_file.name} ({file_size_mb:.1f} MB) to s3://{cfg['bucket']}/{cfg['key']}...", flush=True)

    data = source_file.read_bytes()
    req = _build_sigv4_request(
        "PUT",
        endpoint=cfg["endpoint"],
        bucket=cfg["bucket"],
        key=cfg["key"],
        access_key=cfg["access_key"],
        secret_key=cfg["secret_key"],
        body=data,
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            if 200 <= resp.status < 300:
                print(f"[R2] Successfully uploaded to s3://{cfg['bucket']}/{cfg['key']}!", flush=True)
                return True
            print(f"[R2] Upload failed with status {resp.status}", file=sys.stderr)
            return False
    except urllib.error.HTTPError as exc:
        print(f"[R2] HTTP Error {exc.code}: {exc.read().decode('utf-8', errors='ignore')}", file=sys.stderr)
        return False
    except Exception as exc:
        print(f"[R2] Upload error: {exc}", file=sys.stderr)
        return False


def download_from_r2(target_file: Path, config: dict[str, str] | None = None) -> bool:
    """Download database file from Cloudflare R2 to target local path."""
    cfg = config or get_r2_config()
    if not cfg:
        return False

    req = _build_sigv4_request(
        "GET",
        endpoint=cfg["endpoint"],
        bucket=cfg["bucket"],
        key=cfg["key"],
        access_key=cfg["access_key"],
        secret_key=cfg["secret_key"],
    )

    tmp_target = target_file.with_suffix(".tmp")
    target_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        print(f"[R2] Downloading s3://{cfg['bucket']}/{cfg['key']} to {target_file}...", flush=True)
        with urllib.request.urlopen(req, timeout=120) as resp:
            if resp.status == 200:
                with open(tmp_target, "wb") as out_f:
                    shutil.copyfileobj(resp, out_f)
                if tmp_target.is_file() and tmp_target.stat().st_size > 0:
                    tmp_target.replace(target_file)
                    print(f"[R2] Download complete ({target_file.stat().st_size / (1024*1024):.1f} MB)", flush=True)
                    return True
        return False
    except Exception as exc:
        print(f"[R2] Download error: {exc}", file=sys.stderr)
        if tmp_target.is_file():
            tmp_target.unlink(missing_ok=True)
        return False


def ensure_database_synced(target_path: Path | None = None) -> bool:
    """In serverless environment, ensure database exists in /tmp by downloading if needed."""
    cfg = get_r2_config()
    if not cfg:
        return False

    target = target_path or Path(os.environ.get("CUTI_DB_PATH", "/tmp/auctions.db"))
    if not target.is_file() or target.stat().st_size == 0:
        return download_from_r2(target, cfg)
    return True
