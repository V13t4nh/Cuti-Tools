"""Continuous & batch Watch Refinement Engine using Google Gemini Web API.

This standalone worker reads watch auction lots from SQLite (var/auctions.db),
decompresses seller descriptions from lot_desc, and leverages Gemini Web
(via gemini_webapi) in micro-batches (default: 3 lots/prompt) to extract
accurate, standardized technical watch profiles and activate Tier 4 overrides.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import signal
import sqlite3
import sys
import time
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "var" / "auctions.db"
DEFAULT_LOCK_PATH = DEFAULT_DB_PATH.with_suffix(DEFAULT_DB_PATH.suffix + ".refine.lock")
COOKIE_FILE_PATH = PROJECT_ROOT / "var" / "gemini_cookie.json"
ENV_FILE_PATH = PROJECT_ROOT / ".env"

try:
    from process_lock import ProcessLockBusy, process_lock
except ImportError:
    from scripts.process_lock import ProcessLockBusy, process_lock

SYSTEM_PROMPT = """You are an expert luxury and vintage watch appraiser and technical cataloger.
Your task is to analyze watch auction listings (Title, Platform Specs, and Seller's Full Description) and extract an authoritative, standardized technical profile for each watch.

Input contains one or more watch lots demarcated by:
=== LOT_START [ID: <lot_id>] ===
...
=== LOT_END [ID: <lot_id>] ===

For EACH lot in the input, you must solve common auction listing issues:
1. Reference vs Serial Number: Sellers frequently confuse case serial numbers (usually 6-8 digits, e.g. "80123456", "24779325") with Reference numbers (e.g. "2531.80.00", "SBTR019", "16610"). Never accept a case serial as a reference number.
2. Caliber vs Reference: In Japanese watches (Seiko, Citizen) or vintage watches, movements like "8T63", "7S26", "ETA 2824-2" are calibers, NOT reference numbers. If the text says "Seiko Spirit SBTR019 powered by 8T63", ref_number is "SBTR019" and caliber is "8T63".
3. Negation & Corrections: Beware of sentences like "Not an ETA 2824, this model uses Sellita SW200". Extract the true movement (Sellita SW200).
4. Full Set vs Fake Full Set: Many sellers label their lot "Full Set" in the title, but in the description state:
   - Box is "generic travel pouch", "aftermarket box", or "replacement box".
   - Papers are "store invoice", "in-house shop certificate", or "lost".
   RULE: condition_tag can ONLY be "fullset" if BOTH the box is original manufacturer box AND papers are original manufacturer warranty card/papers. Otherwise, downgrade condition_tag to "box", "papers", or "naked", and set "fake_fullset_detected": true.
5. Material Classification:
   - "solid gold" (18k / 750 / 14k / 585 gold case) -> "gold"
   - "gold plated", "gold electroplated", "plaque or", "verguld", "gilded", "rolled gold" -> "gold_plated"
   - "stainless steel", "edelstaal", "acier" -> "steel"
   - "titanium" -> "titanium"
   - others / bi-color / bronze -> "other"
6. Movement Classification: Must be strictly one of: "auto", "manual", "quartz".
7. Multilingual Handling: Understand seller descriptions written in English, Dutch (Nederlands), French, German, Italian, or Spanish.

Output strictly valid JSON as a JSON ARRAY inside a ```json ... ``` codeblock adhering to this schema:
[
  {
    "lot_id": "<exact lot_id from input, e.g. '106178252'>",
    "identity": {
      "brand": "<Canonical Brand name, e.g. Rolex, Omega, Seiko>",
      "model": "<Model line name, e.g. Seamaster Professional 300M, Spirit Chronograph>",
      "ref_number": "<Authoritative reference number, or null if genuinely unknown>",
      "caliber": "<Movement caliber name, or null>",
      "case_code": "<Case code if applicable, or null>",
      "is_serial_discarded": <true/false>,
      "discarded_serial_candidate": "<serial string discarded, or null>"
    },
    "specs": {
      "movement": "<auto | manual | quartz | null>",
      "case_material": "<steel | gold | gold_plated | titanium | other | null>",
      "case_diameter_mm": <Integer diameter in mm excluding crown, or null>
    },
    "condition": {
      "dial_originality": "<original | repainted | aftermarket | unknown>",
      "case_condition": "<unpolished | polished | scratched | dented | good>",
      "strap_status": "<original_bracelet | original_strap | aftermarket_leather | aftermarket_bracelet | generic_strap>",
      "movement_status": "<working_accurate | working_needs_service | not_working | unknown>"
    },
    "accessories": {
      "box_type": "<original_box | generic_box | no_box>",
      "papers_type": "<original_papers | store_invoice | no_papers>",
      "true_condition_tag": "<fullset | box | papers | naked>",
      "fake_fullset_detected": <true/false>,
      "fake_fullset_reason": "<Brief explanation if downgraded from fullset, or null>"
    },
    "audit": {
      "seller_language": "<en | nl | fr | de | it | other>",
      "contradictions": [
        "<List any contradictions between seller description and title/specs table>"
      ],
      "confidence": "<high | medium | low>",
      "reasoning_summary": "<1-2 sentence concise summary of key findings>"
    }
  }
]
"""


def _clean_psid(psid: str) -> str:
    psid = psid.strip()
    if psid.startswith("g.g."):
        psid = "g." + psid[4:]
    return psid


def load_cookie_accounts(cookie_path: Path | str | None = None) -> list[dict[str, str]]:
    """Load all valid Gemini Web cookie accounts from file and environment.

    Returns a list of dicts: [{'account': 'acc_1', 'name': 'acc_1', 'psid': '...', 'psidts': '...'}, ...]
    Supports:
      - JSON list of account dicts: [{'account': 'acc_1', '__Secure-1PSID': '...', '__Secure-1PSIDTS': '...'}, ...]
      - JSON dict with 'accounts' or 'cookies' list
      - Single-account JSON dict: {'__Secure-1PSID': '...', '__Secure-1PSIDTS': '...'}
      - Environment variables fallback: GEMINI_SECURE_1PSID and GEMINI_SECURE_1PSIDTS
    """
    accounts: list[dict[str, str]] = []
    target_file = Path(cookie_path) if cookie_path else COOKIE_FILE_PATH

    if target_file.is_file():
        try:
            raw_data = json.loads(target_file.read_text(encoding="utf-8"))
            items: list[dict[str, Any]] = []
            if isinstance(raw_data, list):
                items = [item for item in raw_data if isinstance(item, dict)]
            elif isinstance(raw_data, dict):
                nested = raw_data.get("accounts") or raw_data.get("cookies")
                if isinstance(nested, list):
                    items = [item for item in nested if isinstance(item, dict)]
                else:
                    items = [raw_data]

            for idx, item in enumerate(items, 1):
                p = (
                    item.get("__Secure-1PSID")
                    or item.get("Secure_1PSID")
                    or item.get("psid")
                    or ""
                )
                pts = (
                    item.get("__Secure-1PSIDTS")
                    or item.get("Secure_1PSIDTS")
                    or item.get("psidts")
                    or ""
                )
                name = (
                    item.get("account")
                    or item.get("name")
                    or f"acc_{idx}"
                )
                if p and pts:
                    accounts.append({
                        "account": str(name),
                        "name": str(name),
                        "psid": _clean_psid(str(p)),
                        "psidts": str(pts).strip(),
                    })
        except Exception:
            pass

    if not accounts:
        env_psid = os.getenv("GEMINI_SECURE_1PSID") or os.getenv("SECURE_1PSID") or ""
        env_psidts = os.getenv("GEMINI_SECURE_1PSIDTS") or os.getenv("SECURE_1PSIDTS") or ""

        if (not env_psid or not env_psidts) and ENV_FILE_PATH.is_file():
            try:
                for line in ENV_FILE_PATH.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k in ("GEMINI_SECURE_1PSID", "SECURE_1PSID", "__Secure-1PSID"):
                        env_psid = env_psid or v
                    elif k in ("GEMINI_SECURE_1PSIDTS", "SECURE_1PSIDTS", "__Secure-1PSIDTS"):
                        env_psidts = env_psidts or v
            except Exception:
                pass

        if env_psid and env_psidts:
            accounts.append({
                "account": "env",
                "name": "env",
                "psid": _clean_psid(env_psid),
                "psidts": env_psidts.strip(),
            })

    return accounts


def load_cookies(cookie_path: Path | str | None = None) -> tuple[str, str]:
    """Load primary __Secure-1PSID and __Secure-1PSIDTS (backward compatibility)."""
    accounts = load_cookie_accounts(cookie_path)
    if accounts:
        return accounts[0]["psid"], accounts[0]["psidts"]
    return "", ""


def count_unrefined_lots(conn: sqlite3.Connection, force: bool = False) -> int:
    """Return count of lots needing refinement."""
    cur = conn.cursor()
    if force:
        cur.execute("SELECT count(*) FROM lots l JOIN lot_desc d ON l.lot_id = d.lot_id")
    else:
        cur.execute("SELECT count(*) FROM lots l JOIN lot_desc d ON l.lot_id = d.lot_id WHERE l.ai_json IS NULL")
    row = cur.fetchone()
    return int(row[0]) if row else 0


def fetch_batch_lots(
    conn: sqlite3.Connection,
    lot_ids: list[str] | None = None,
    limit: int = 3,
    force: bool = False,
    exclude_ids: set[str] | list[str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch next batch of lots with seller descriptions."""
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if lot_ids:
        placeholders = ",".join("?" for _ in lot_ids)
        cur.execute(
            f"""
            SELECT l.lot_id, l.title, l.brand, l.model, l.ref_number, l.caliber,
                   l.case_code, l.movement, l.case_material, l.case_diameter_mm,
                   l.condition_tag, l.needs_review, l.review_status, l.specs_json,
                   d.desc_z
            FROM lots l
            JOIN lot_desc d ON l.lot_id = d.lot_id
            WHERE l.lot_id IN ({placeholders})
            """,
            lot_ids,
        )
    else:
        clauses = []
        params: list[Any] = []
        if not force:
            clauses.append("l.ai_json IS NULL")
        if exclude_ids:
            ex_ph = ",".join("?" for _ in exclude_ids)
            clauses.append(f"l.lot_id NOT IN ({ex_ph})")
            params.extend(list(exclude_ids))
        filter_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        cur.execute(
            f"""
            SELECT l.lot_id, l.title, l.brand, l.model, l.ref_number, l.caliber,
                   l.case_code, l.movement, l.case_material, l.case_diameter_mm,
                   l.condition_tag, l.needs_review, l.review_status, l.specs_json,
                   d.desc_z
            FROM lots l
            JOIN lot_desc d ON l.lot_id = d.lot_id
            {filter_clause}
            ORDER BY l.needs_review DESC, l.ended_at DESC
            LIMIT ?
            """,
            params,
        )

    rows = cur.fetchall()
    results = []
    for row in rows:
        raw_desc = ""
        if row["desc_z"]:
            try:
                raw_desc = zlib.decompress(row["desc_z"]).decode("utf-8", errors="replace")
            except Exception as exc:
                raw_desc = f"[Decompress error: {exc}]"

        results.append({
            "lot_id": str(row["lot_id"]),
            "title": row["title"],
            "brand": row["brand"],
            "model": row["model"],
            "ref_number": row["ref_number"],
            "caliber": row["caliber"],
            "case_code": row["case_code"],
            "movement": row["movement"],
            "case_material": row["case_material"],
            "case_diameter_mm": row["case_diameter_mm"],
            "condition_tag": row["condition_tag"],
            "needs_review": row["needs_review"],
            "review_status": row["review_status"],
            "specs_json": row["specs_json"],
            "description": raw_desc,
        })
    return results


def build_batch_prompt(lots: list[dict[str, Any]]) -> str:
    """Format batch of lots into structured appraisal prompt."""
    blocks = []
    for lot in lots:
        lid = lot["lot_id"]
        specs_str = lot.get("specs_json") or "None"
        desc_str = lot.get("description") or "None"
        blocks.append(
            f"=== LOT_START [ID: {lid}] ===\n"
            f"[LOT TITLE]\n{lot.get('title')}\n\n"
            f"[CURRENT PLATFORM SPECS]\n{specs_str}\n\n"
            f"[SELLER DESCRIPTION]\n{desc_str}\n"
            f"=== LOT_END [ID: {lid}] ==="
        )
    return (
        f"Analyze the following {len(lots)} watch auction lot(s) and produce the structured JSON array with matching 'lot_id':\n\n"
        + "\n\n".join(blocks)
    )


def extract_json_from_text(text: str) -> list[dict[str, Any]] | None:
    """Multi-strategy extractor to reliably parse JSON array from model output."""
    # Strategy 1: Find all opening ```json markers and test slices in reverse
    markers = [m.start() for m in re.finditer(r"```(?:json)?", text)]
    for start_pos in reversed(markers):
        after = text[start_pos:]
        after = re.sub(r"^```(?:json)?\s*", "", after)
        close_pos = after.rfind("```")
        candidate = after[:close_pos].strip() if close_pos != -1 else after.strip()
        try:
            p = json.loads(candidate)
            if isinstance(p, list):
                return p
            elif isinstance(p, dict):
                return [p]
        except Exception:
            pass

    # Strategy 2: Bracket matching from rightmost '[' to last ']'
    bracket_end = text.rfind("]")
    if bracket_end != -1:
        for m in reversed(list(re.finditer(r"\[", text))):
            s = m.start()
            if s >= bracket_end:
                continue
            candidate = text[s : bracket_end + 1]
            try:
                p = json.loads(candidate)
                if isinstance(p, list):
                    return p
            except Exception:
                pass

    # Strategy 3: Outermost braces if single dict returned
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            p = json.loads(text[start : end + 1])
            if isinstance(p, dict):
                return [p]
        except Exception:
            pass

    # Strategy 4: Direct raw parse
    try:
        p = json.loads(text.strip())
        if isinstance(p, list):
            return p
        elif isinstance(p, dict):
            return [p]
    except Exception:
        pass

    return None


class GeminiAppraiser:
    """Manages connection and interaction with Google Gemini Web API."""

    def __init__(self, psid: str, psidts: str, model: str = "gemini-flash", name: str = "default"):
        self.name = name
        self.psid = psid
        self.psidts = psidts
        self.model = model
        self.client = None
        self.reconnect_count = 0
        self.is_unauthenticated = False
        self.last_batch_meta: dict[str, Any] = {}


    def get_quota_summary(self) -> str:
        """Extract and format quota info (remaining credits / total, reset time)."""
        prefix = f"[{self.name}] " if self.name else ""
        if not self.client or not hasattr(self.client, "_quotas"):
            return f"{prefix}N/A"
        quotas = self.client._quotas
        target = quotas.get("None-11") or quotas.get("None-4")
        if target:
            rem = target.get("remaining")
            tot = target.get("total", 2400)
            usage_pct = target.get("usage_percentage")
            reset_ts = target.get("reset_time")
            reset_str = ""
            if reset_ts:
                try:
                    dt = datetime.fromtimestamp(reset_ts, tz=timezone.utc).astimezone()
                    reset_str = f" | Reset: {dt.strftime('%H:%M:%S')}"
                except Exception:
                    pass
            if rem is not None:
                pct_str = f" ({usage_pct}% used)" if usage_pct is not None else ""
                return f"{prefix}{rem}/{tot} credits{pct_str}{reset_str}"

        usage_info = quotas.get("usage_info", {})
        c5h = usage_info.get("current_5h", {})
        if c5h:
            rem = c5h.get("remaining_credits")
            pct = c5h.get("usage_percentage")
            reset_at = c5h.get("reset_at", "")
            reset_str = ""
            if "T" in reset_at:
                try:
                    reset_str = f" | Reset: {reset_at.split('T')[1].split('+')[0]}"
                except Exception:
                    pass
            pct_str = f" ({pct}% used)" if pct is not None else ""
            return f"{prefix}{rem}/2400 credits{pct_str}{reset_str}"

        return f"{prefix}Active"

    async def refresh_quota(self) -> None:
        """Silently refresh quota cache from Gemini server."""
        if self.client and hasattr(self.client, "_fetch_quota"):
            try:
                await self.client._fetch_quota(flash=True, advanced=False)
            except Exception:
                pass

    async def init(self) -> None:
        from gemini_webapi import GeminiClient, set_log_level

        # Silence verbose loguru output (quota dump, token rotation logs, abuse tier)
        set_log_level("ERROR")

        self.client = GeminiClient(self.psid, self.psidts, proxy=None)
        await self.client.init(timeout=90, auto_close=False, auto_refresh=True)
        acc_status = getattr(self.client, "account_status", None)
        status_name = getattr(acc_status, "name", str(acc_status))
        if "UNAUTHENTICATED" in status_name:
            raise RuntimeError(f"Account status for [{self.name}]: UNAUTHENTICATED - Session is not authenticated or cookies have expired.")

        orig_init = self.client.init

        async def monitored_init(*args: Any, **kwargs: Any) -> Any:
            self.reconnect_count += 1
            print(f"  [~] Session dropped for [{self.name}]. Reconnecting Gemini client (reconnect #{self.reconnect_count})...", flush=True)
            res = await orig_init(*args, **kwargs)
            print(f"  [~] Reconnected [{self.name}] successfully. Quota: {self.get_quota_summary()}", flush=True)
            return res

        self.client.init = monitored_init

    async def appraise_batch(self, prompt: str, max_retries: int = 2) -> list[dict[str, Any]] | None:
        full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"
        retries = 0
        total_wait = 0.0

        for attempt in range(max_retries + 1):
            try:
                response = await self.client.generate_content(
                    full_prompt,
                    model=self.model,
                    temporary=True,
                )
                text = response.text or ""
                if "having a hard time fulfilling your request" in text or "encountering an error" in text:
                    if attempt < max_retries:
                        retries += 1
                        wait_s = 4.0
                        total_wait += wait_s
                        print(f"  [!] Retry {retries}/{max_retries} [{self.name}]: Server busy message. Waiting {wait_s:.1f}s before retry...", flush=True)
                        await asyncio.sleep(wait_s)
                        continue

                parsed = extract_json_from_text(text)
                if parsed:
                    await self.refresh_quota()
                    self.last_batch_meta = {
                        "retries": retries,
                        "wait_seconds": total_wait,
                    }
                    return parsed

                if attempt < max_retries:
                    retries += 1
                    wait_s = 2.0
                    total_wait += wait_s
                    print(f"  [!] Retry {retries}/{max_retries} [{self.name}]: Model returned non-JSON. Waiting {wait_s:.1f}s before retry...", flush=True)
                    await asyncio.sleep(wait_s)
                    continue
            except Exception as exc:
                err_text = str(exc)
                if "UNAUTHENTICATED" in err_text or "cookies have expired" in err_text or "not authenticated" in err_text.lower():
                    self.is_unauthenticated = True
                    print(f"  [-] Fatal auth error on [{self.name}]: {exc}", file=sys.stderr, flush=True)
                    break
                if attempt < max_retries:
                    retries += 1
                    wait_s = 3.0
                    total_wait += wait_s
                    err_msg = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
                    if len(err_msg) > 75:
                        err_msg = err_msg[:72] + "..."
                    print(f"  [!] Retry {retries}/{max_retries} [{self.name}]: {type(exc).__name__} ({err_msg}). Waiting {wait_s:.1f}s before retry...", flush=True)
                    await asyncio.sleep(wait_s)
                    continue
                print(f"[-] API error on [{self.name}] after {attempt + 1} attempts: {exc}", file=sys.stderr, flush=True)


        await self.refresh_quota()
        self.last_batch_meta = {
            "retries": retries,
            "wait_seconds": total_wait,
        }
        return None


def apply_refinement(conn: sqlite3.Connection, lot_id: str, ai_data: dict[str, Any]) -> None:
    """Save ai_json, generate Tier 4 override_json, and update columns in SQLite."""
    identity = ai_data.get("identity") or {}
    specs = ai_data.get("specs") or {}
    accessories = ai_data.get("accessories") or {}
    audit = ai_data.get("audit") or {}

    override: dict[str, Any] = {}
    new_ref = identity.get("ref_number")
    new_cal = identity.get("caliber")
    new_model = identity.get("model")
    new_case_code = identity.get("case_code")
    new_mov = specs.get("movement")
    new_mat = specs.get("case_material")
    new_dia = specs.get("case_diameter_mm")

    if new_ref:
        override["ref_number"] = new_ref
    if new_cal:
        override["caliber"] = new_cal
    if new_case_code:
        override["case_code"] = new_case_code
    if new_mov:
        override["movement"] = new_mov
    if new_mat:
        override["case_material"] = new_mat
    if new_dia:
        override["case_diameter_mm"] = new_dia

    true_tag = accessories.get("true_condition_tag")
    confidence = audit.get("confidence", "medium")
    should_resolve = confidence == "high"
    now_iso = datetime.now(timezone.utc).isoformat()

    with conn:
        conn.execute(
            """
            UPDATE lots
            SET ai_json = ?,
                override_json = CASE WHEN ? != '{}' THEN ? ELSE override_json END,
                ref_number = COALESCE(?, ref_number),
                caliber = COALESCE(?, caliber),
                model = COALESCE(?, model),
                movement = COALESCE(?, movement),
                case_material = COALESCE(?, case_material),
                case_diameter_mm = COALESCE(?, case_diameter_mm),
                condition_tag = CASE WHEN ? IS NOT NULL AND ? IN ('naked', 'box', 'papers', 'fullset') THEN ? ELSE condition_tag END,
                needs_review = CASE WHEN ? = 1 THEN 0 ELSE needs_review END,
                review_status = CASE WHEN ? = 1 THEN 'resolved' ELSE review_status END,
                reviewed_at = CASE WHEN ? = 1 THEN ? ELSE reviewed_at END,
                updated_at = ?
            WHERE lot_id = ?
            """,
            (
                json.dumps(ai_data, ensure_ascii=False),
                json.dumps(override),
                json.dumps(override),
                new_ref,
                new_cal,
                new_model,
                new_mov,
                new_mat,
                new_dia,
                true_tag,
                true_tag,
                true_tag,
                1 if should_resolve else 0,
                1 if should_resolve else 0,
                1 if should_resolve else 0,
                now_iso,
                now_iso,
                str(lot_id),
            ),
        )
        conn.commit()


def run_refinement(
    conn: sqlite3.Connection,
    *,
    cookie_path: Path | str | None = None,
    batch_size: int = 3,
    limit: int | None = None,
    delay: float = 2.0,
    model: str = "gemini-flash",
    force: bool = False,
    lot_ids: list[str] | None = None,
    should_update: bool = True,
    dry_run: bool = False,
    lock_path: Path | str | None = None,
) -> tuple[int, int, list[str]]:
    """Run batch refinement using Google Gemini Web.

    Returns:
        (processed_count, success_count, errors)
    """
    total_unrefined = count_unrefined_lots(conn, force=force)
    session_limit = min(limit, total_unrefined) if limit else total_unrefined
    if lot_ids:
        session_limit = len(lot_ids)

    print("=" * 70)
    print(f"CUTI WATCH REFINEMENT ENGINE (Model: {model})")
    print(f"Batch Size: {batch_size} | Pacing: {delay}s")
    print(f"Remaining unrefined lots: {total_unrefined:,} | Target for this run: {session_limit:,}")
    print(f"Database Updates: {'ENABLED' if should_update else 'DISABLED (view only)'}")
    print("=" * 70, flush=True)

    if total_unrefined == 0 and not lot_ids:
        print("[+] All lots in the database have already been refined. Nothing to do!", flush=True)
        return 0, 0, []

    if dry_run:
        sample_lots = fetch_batch_lots(conn, lot_ids=lot_ids, limit=batch_size, force=force)
        if sample_lots:
            prompt = build_batch_prompt(sample_lots)
            print("\n[DRY RUN MODE] Sample prompt preview:")
            print("-" * 70)
            print(prompt[:1000] + "\n... [truncated] ...")
            print("-" * 70, flush=True)
        return 0, 0, []

    actual_lock_path = Path(lock_path) if lock_path else DEFAULT_LOCK_PATH
    try:
        with process_lock(actual_lock_path, "LLM refinement worker is already running"):
            return _execute_refinement(
                conn,
                cookie_path=cookie_path,
                batch_size=batch_size,
                limit=limit,
                delay=delay,
                model=model,
                force=force,
                lot_ids=lot_ids,
                should_update=should_update,
                session_limit=session_limit,
                total_unrefined=total_unrefined,
            )
    except ProcessLockBusy as exc:
        err = f"Lock conflict: {exc}. Another refinement process is currently active."
        print(f"\n[!] LOCK ERROR: {err}", file=sys.stderr, flush=True)
        return 0, 0, [err]


def _wait_for_cookie_update(cookie_path: Path | str | None) -> list[dict[str, str]] | None:
    """Prompt user to update expired/missing Gemini cookies and press Enter to reload."""
    target_file = Path(cookie_path) if cookie_path else COOKIE_FILE_PATH
    if not sys.stdin or not sys.stdin.isatty():
        print("[-] Non-interactive session: cannot wait for cookie input. Exiting refine.", file=sys.stderr, flush=True)
        return None

    while True:
        print("\n" + "=" * 70, flush=True)
        print("[!] [IDLE] GEMINI COOKIES EXPIRED OR UNAUTHENTICATED", flush=True)
        print(f"    Target file: {target_file}", flush=True)
        print("    Vui lòng cập nhật cookie mới vào file trên (hỗ trợ 1 hoặc nhiều tài khoản dạng JSON array),", flush=True)
        print("    sau đó quay lại terminal và nhấn [ENTER] để hệ thống tải lại cookie và tiếp tục chạy.", flush=True)
        print("    (Hoặc gõ 'q' / 'skip' rồi nhấn [ENTER] để bỏ qua bước refine lần này)", flush=True)
        print("=" * 70, flush=True)
        try:
            choice = input(">>> Nhấn [ENTER] sau khi đã cập nhật cookie (hoặc 'q' để thoát): ").strip().lower()
            if choice in ("q", "quit", "exit", "skip"):
                print("[!] Bỏ qua bước LLM refine theo yêu cầu người dùng.", flush=True)
                return None
            accounts = load_cookie_accounts(cookie_path)
            if not accounts:
                print(f"[!] Cookie vẫn trống hoặc thiếu __Secure-1PSID / __Secure-1PSIDTS! Vui lòng kiểm tra lại file {target_file}.", file=sys.stderr, flush=True)
                continue
            print(f"[+] Đã tải {len(accounts)} tài khoản cookie mới từ file, đang thử kết nối lại Gemini...", flush=True)
            return accounts
        except (KeyboardInterrupt, EOFError):
            print("\n[!] Bỏ qua bước LLM refine.", flush=True)
            return None


def _init_appraiser_pool(
    loop: asyncio.AbstractEventLoop,
    accounts: list[dict[str, str]],
    *,
    model: str,
    cookie_path: Path | str | None,
) -> list[GeminiAppraiser]:
    """Initialize GeminiAppraiser pool for available accounts.

    Retries with user prompt if all accounts fail authentication.
    """
    current_accounts = accounts
    while True:
        appraisers: list[GeminiAppraiser] = []
        for acc in current_accounts:
            name = acc["name"]
            print(f"[*] Initializing Gemini Web client: account '{name}' ({model})...", flush=True)
            appraiser = GeminiAppraiser(acc["psid"], acc["psidts"], model=model, name=name)
            try:
                loop.run_until_complete(appraiser.init())
                print(f"[+] Connected account '{name}' successfully. (Quota: {appraiser.get_quota_summary()})", flush=True)
                appraisers.append(appraiser)
            except Exception as exc:
                print(f"[-] Account '{name}' initialization failed: {exc}", file=sys.stderr, flush=True)

        if appraisers:
            return appraisers

        print("[-] All configured Gemini cookie accounts failed authentication.", file=sys.stderr, flush=True)
        updated = _wait_for_cookie_update(cookie_path)
        if not updated:
            return []
        current_accounts = updated


def _execute_refinement(
    conn: sqlite3.Connection,
    *,
    cookie_path: Path | str | None,
    batch_size: int,
    limit: int | None,
    delay: float,
    model: str,
    force: bool,
    lot_ids: list[str] | None,
    should_update: bool,
    session_limit: int,
    total_unrefined: int,
) -> tuple[int, int, list[str]]:
    accounts = load_cookie_accounts(cookie_path)
    while not accounts:
        updated = _wait_for_cookie_update(cookie_path)
        if not updated:
            err = "Missing Gemini Web cookies (__Secure-1PSID / __Secure-1PSIDTS)!"
            return 0, 0, [err]
        accounts = updated

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    active_pool = _init_appraiser_pool(loop, accounts, model=model, cookie_path=cookie_path)
    if not active_pool:
        return 0, 0, ["Client initialization failed: No valid Gemini accounts available."]

    pool_names = ", ".join(a.name for a in active_pool)
    print(f"[+] Active Gemini Web accounts in pool ({len(active_pool)}): {pool_names}", flush=True)

    pool_index = 0
    processed_count = 0
    success_count = 0
    batch_idx = 0
    errors: list[str] = []
    failed_lots: set[str] = set()

    stop_requested = False

    def handle_sigint(_signum, _frame):
        nonlocal stop_requested
        print("\n\n[!] Interrupt received. Completing current batch and stopping gracefully...", flush=True)
        stop_requested = True

    try:
        prev_sigint = signal.signal(signal.SIGINT, handle_sigint)
    except (ValueError, AttributeError):
        prev_sigint = None

    start_time = time.time()

    try:
        while not stop_requested:
            effective_count = success_count if should_update else processed_count
            if limit and effective_count >= limit:
                break

            current_limit = min(batch_size, limit - effective_count) if limit else batch_size
            lots = fetch_batch_lots(conn, lot_ids=lot_ids, limit=current_limit, force=force, exclude_ids=failed_lots)
            if not lots:
                break

            if not active_pool:
                print("  [!] All accounts in pool expired! Waiting for cookie update...", file=sys.stderr, flush=True)
                updated = _wait_for_cookie_update(cookie_path)
                if updated:
                    active_pool = _init_appraiser_pool(loop, updated, model=model, cookie_path=cookie_path)
                    if not active_pool:
                        errors.append("All Gemini accounts are unauthenticated. Aborting refinement.")
                        break
                    pool_index = 0
                else:
                    errors.append("Gemini session is unauthenticated (cookies expired). Aborting refinement.")
                    break

            appraiser = active_pool[pool_index % len(active_pool)]
            pool_index += 1

            batch_idx += 1
            batch_ids = [l["lot_id"] for l in lots]
            target_str = f"Target: {session_limit}" if session_limit else f"Remaining: {total_unrefined}"
            pool_status_str = f"[{appraiser.name} | pool: {len(active_pool)}]"
            print(f"\n[Batch {batch_idx}] Processing {len(lots)} lots via {pool_status_str}: {', '.join(batch_ids)} (Success: {success_count} | {target_str})...", flush=True)

            prompt = build_batch_prompt(lots)
            t0 = time.time()
            results = loop.run_until_complete(appraiser.appraise_batch(prompt))
            elapsed = time.time() - t0

            meta = getattr(appraiser, "last_batch_meta", {})
            retries = meta.get("retries", 0)
            wait_s = meta.get("wait_seconds", 0.0)
            retry_str = f" (retries: {retries}, waited: {wait_s:.1f}s)" if retries > 0 else ""
            quota_str = appraiser.get_quota_summary()

            if not results:
                if getattr(appraiser, "is_unauthenticated", False):
                    print(f"  [!] Session unauthenticated for account '{appraiser.name}'. Removing from active pool.", file=sys.stderr, flush=True)
                    if appraiser in active_pool:
                        active_pool.remove(appraiser)

                    while active_pool:
                        alt_appraiser = active_pool[pool_index % len(active_pool)]
                        pool_index += 1
                        print(f"  [~] Retrying batch {batch_idx} using alternative account '{alt_appraiser.name}'...", flush=True)
                        results = loop.run_until_complete(alt_appraiser.appraise_batch(prompt))
                        if results:
                            appraiser = alt_appraiser
                            quota_str = appraiser.get_quota_summary()
                            break
                        if getattr(alt_appraiser, "is_unauthenticated", False):
                            print(f"  [!] Account '{alt_appraiser.name}' also expired. Removing from active pool.", file=sys.stderr, flush=True)
                            if alt_appraiser in active_pool:
                                active_pool.remove(alt_appraiser)

                    if not active_pool and not results:
                        print("  [!] All accounts in pool expired during batch! Waiting for cookie update...", file=sys.stderr, flush=True)
                        updated = _wait_for_cookie_update(cookie_path)
                        if updated:
                            active_pool = _init_appraiser_pool(loop, updated, model=model, cookie_path=cookie_path)
                            if active_pool:
                                pool_index = 0
                                continue
                        err_msg = "Gemini session is unauthenticated (all cookies expired). Aborting refinement."
                        errors.append(err_msg)
                        break

                elif len(active_pool) > 1:
                    alt_appraiser = active_pool[pool_index % len(active_pool)]
                    pool_index += 1
                    print(f"  [~] Batch failed on [{appraiser.name}]. Retrying with backup account [{alt_appraiser.name}]...", flush=True)
                    alt_results = loop.run_until_complete(alt_appraiser.appraise_batch(prompt))
                    if alt_results:
                        results = alt_results
                        appraiser = alt_appraiser
                        quota_str = appraiser.get_quota_summary()

                if not results:
                    print(f"  [-] [REFINE] Batch {batch_idx} extraction failed after {elapsed:.1f}s{retry_str}. Queuing {len(lots)} lots for individual fallback. | Quota: {quota_str}", flush=True)
                    errors.append(f"Batch {batch_idx} extraction failed for lots {batch_ids}")
                    failed_lots.update(batch_ids)
                    processed_count += len(lots)
                    continue

            result_map = {str(r.get("lot_id", "")): r for r in results}
            batch_saved = 0
            for lot in lots:
                lid = lot["lot_id"]
                ai_data = result_map.get(lid)
                if not ai_data:
                    print(f"  [?] Lot {lid}: missing in AI output. Adding to fallback.", flush=True)
                    failed_lots.add(lid)
                    continue

                ident = ai_data.get("identity", {})
                acc = ai_data.get("accessories", {})
                audit = ai_data.get("audit", {})

                ref_display = f"{lot['ref_number']} -> {ident.get('ref_number')}" if ident.get('ref_number') != lot['ref_number'] else f"{ident.get('ref_number')}"
                tag_display = acc.get("true_condition_tag")

                note = ""
                if acc.get("fake_fullset_detected"):
                    note = " [FAKE FULLSET DOWNGRADED]"
                elif ident.get("is_serial_discarded"):
                    note = f" [SERIAL DISCARDED: {ident.get('discarded_serial_candidate')}]"

                print(f"  * Lot {lid} ({ident.get('brand')} {ident.get('model')}): Ref: {ref_display} | Tag: {tag_display}{note} (Conf: {audit.get('confidence')})", flush=True)

                if should_update:
                    apply_refinement(conn, lid, ai_data)
                    success_count += 1
                    batch_saved += 1

            processed_count += len(lots)
            pct = (success_count / session_limit * 100) if session_limit else 100.0
            print(f"  => Batch completed in {elapsed:.1f}s{retry_str} | Saved: {batch_saved}/{len(lots)} | Total: {success_count}/{session_limit} ({pct:.1f}%) | Quota: {quota_str}", flush=True)

            if delay > 0 and not stop_requested:
                time.sleep(delay)

            if lot_ids:
                break

        # Single-lot fallback pass for any failed batches
        if failed_lots and not stop_requested and not lot_ids and active_pool:
            print(f"\n[*] Running single-lot fallback on {len(failed_lots)} previously failed lot(s)...", flush=True)
            fallback_ids = list(failed_lots)
            failed_lots.clear()
            for fid in fallback_ids:
                if stop_requested or not active_pool:
                    break
                single_lot = fetch_batch_lots(conn, lot_ids=[fid])
                if not single_lot:
                    continue
                app = active_pool[pool_index % len(active_pool)]
                pool_index += 1
                prompt = build_batch_prompt(single_lot)
                results = loop.run_until_complete(app.appraise_batch(prompt, max_retries=1))
                quota_str = app.get_quota_summary()
                if results and str(results[0].get("lot_id")) == fid:
                    ai_data = results[0]
                    ident = ai_data.get("identity", {})
                    print(f"  [+] Fallback SUCCEEDED for {fid} ({ident.get('brand')} {ident.get('model')}) via [{app.name}] | Quota: {quota_str}", flush=True)
                    if should_update:
                        apply_refinement(conn, fid, ai_data)
                        success_count += 1
                else:
                    print(f"  [-] Fallback FAILED for {fid} via [{app.name}] | Quota: {quota_str}", flush=True)
                    failed_lots.add(fid)
                if delay > 0:
                    time.sleep(delay)
    finally:
        if prev_sigint is not None:
            try:
                signal.signal(signal.SIGINT, prev_sigint)
            except (ValueError, AttributeError):
                pass

    total_time = time.time() - start_time
    print("\n" + "=" * 70, flush=True)
    print("REFINEMENT SESSION FINISHED", flush=True)
    print(f"Lots Attempted: {processed_count:,} | Successfully Updated: {success_count:,}", flush=True)
    if active_pool:
        quotas_summary = " | ".join(a.get_quota_summary() for a in active_pool)
        print(f"Remaining Quotas: {quotas_summary}", flush=True)
    if failed_lots:
        print(f"Permanently Failed ({len(failed_lots)} lots): {', '.join(sorted(failed_lots))}", flush=True)
    print(f"Elapsed Time: {total_time:.1f}s ({total_time / max(success_count, 1):.2f}s/lot)", flush=True)
    print(f"Remaining in DB: {count_unrefined_lots(conn, force=False):,} lots", flush=True)
    unrecovered_errors = [f"Lot {fid} failed refinement after single-lot fallback" for fid in sorted(failed_lots)]
    return processed_count, success_count, unrecovered_errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Continuous Watch Refinement Engine (Gemini Web)")
    parser.add_argument("--all", action="store_true", help="Process all unrefined lots continuously")
    parser.add_argument("--batch-size", type=int, default=3, help="Number of lots per prompt (default: 3)")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of lots to process in this session")
    parser.add_argument("--lot-id", type=str, help="Specific lot ID(s) to process, comma-separated")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to SQLite database")
    parser.add_argument("--model", type=str, default="gemini-flash", help="Model name (default: gemini-flash)")
    parser.add_argument("--delay", type=float, default=2.0, help="Pause in seconds between batches (default: 2.0)")
    parser.add_argument("--dry-run", action="store_true", help="Print prompt without making network calls")
    parser.add_argument("--force", action="store_true", help="Re-refine lots even if ai_json already exists")
    parser.add_argument("--update-db", action="store_true", help="Explicitly write changes (always on with --all)")
    parser.add_argument("--lock-path", type=Path, default=None, help="Custom path for single-instance lock file")
    args = parser.parse_args()

    if not args.db.is_file():
        print(f"[-] Database file not found: {args.db}", file=sys.stderr)
        sys.exit(1)

    should_update = args.update_db or args.all
    conn = sqlite3.connect(args.db)

    target_ids = [s.strip() for s in args.lot_id.split(",")] if args.lot_id else None

    processed, success, errors = run_refinement(
        conn,
        batch_size=args.batch_size,
        limit=args.limit,
        delay=args.delay,
        model=args.model,
        force=args.force,
        lot_ids=target_ids,
        should_update=should_update,
        dry_run=args.dry_run,
        lock_path=args.lock_path or args.db.with_suffix(args.db.suffix + ".refine.lock"),
    )
    if errors:
        for err in errors:
            print(f"[ERROR] {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
