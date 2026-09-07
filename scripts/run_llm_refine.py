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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "var" / "auctions.db"
COOKIE_FILE_PATH = PROJECT_ROOT / "var" / "gemini_cookie.json"
ENV_FILE_PATH = PROJECT_ROOT / ".env"

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


def load_cookies(cookie_path: Path | str | None = None) -> tuple[str, str]:
    """Load __Secure-1PSID and __Secure-1PSIDTS from environment or configuration file."""
    psid = os.getenv("GEMINI_SECURE_1PSID") or os.getenv("SECURE_1PSID") or ""
    psidts = os.getenv("GEMINI_SECURE_1PSIDTS") or os.getenv("SECURE_1PSIDTS") or ""

    target_file = Path(cookie_path) if cookie_path else COOKIE_FILE_PATH
    if (not psid or not psidts) and target_file.is_file():
        try:
            data = json.loads(target_file.read_text(encoding="utf-8"))
            psid = psid or data.get("__Secure-1PSID", "") or data.get("Secure_1PSID", "")
            psidts = psidts or data.get("__Secure-1PSIDTS", "") or data.get("Secure_1PSIDTS", "")
        except Exception:
            pass

    if (not psid or not psidts) and ENV_FILE_PATH.is_file():
        try:
            for line in ENV_FILE_PATH.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k in ("GEMINI_SECURE_1PSID", "SECURE_1PSID", "__Secure-1PSID"):
                    psid = psid or v
                elif k in ("GEMINI_SECURE_1PSIDTS", "SECURE_1PSIDTS", "__Secure-1PSIDTS"):
                    psidts = psidts or v
        except Exception:
            pass

    return psid.strip(), psidts.strip()


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
        filter_clause = "" if force else "WHERE l.ai_json IS NULL"
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
            (limit,),
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

    def __init__(self, psid: str, psidts: str, model: str = "gemini-flash"):
        self.psid = psid
        self.psidts = psidts
        self.model = model
        self.client = None

    async def init(self) -> None:
        from gemini_webapi import GeminiClient
        self.client = GeminiClient(self.psid, self.psidts, proxy=None)
        await self.client.init(timeout=30, auto_close=False, auto_refresh=True)

    async def appraise_batch(self, prompt: str, max_retries: int = 2) -> list[dict[str, Any]] | None:
        full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"
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
                        await asyncio.sleep(4)
                        continue

                parsed = extract_json_from_text(text)
                if parsed:
                    return parsed
            except Exception as exc:
                if attempt < max_retries:
                    await asyncio.sleep(3)
                    continue
                print(f"[-] API error on attempt {attempt + 1}: {exc}")
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
                reviewed_at = CASE WHEN ? = 1 THEN datetime('now') ELSE reviewed_at END,
                updated_at = datetime('now')
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
    delay: float = 1.5,
    model: str = "gemini-flash",
    force: bool = False,
    lot_ids: list[str] | None = None,
    should_update: bool = True,
    dry_run: bool = False,
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

    psid, psidts = load_cookies(cookie_path)
    if not psid or not psidts:
        err = "Missing Gemini Web cookies (__Secure-1PSID / __Secure-1PSIDTS)!"
        print(f"\n[!] ERROR: {err}", file=sys.stderr, flush=True)
        print(f"    Please create '{COOKIE_FILE_PATH}' or set GEMINI_SECURE_1PSID in .env.", file=sys.stderr, flush=True)
        return 0, 0, [err]

    print(f"[*] Initializing Gemini Web client ({model})...", flush=True)
    appraiser = GeminiAppraiser(psid, psidts, model=model)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(appraiser.init())
    except Exception as exc:
        err = f"Client initialization failed: {exc}"
        print(f"[-] {err}", file=sys.stderr, flush=True)
        return 0, 0, [err]
    print("[+] Connected to Gemini Web successfully.", flush=True)

    processed_count = 0
    success_count = 0
    batch_idx = 0
    total_batches = (session_limit + batch_size - 1) // batch_size if session_limit else 1
    errors: list[str] = []

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
        while processed_count < session_limit and not stop_requested:
            batch_idx += 1
            current_batch_limit = min(batch_size, session_limit - processed_count)
            lots = fetch_batch_lots(conn, lot_ids=lot_ids, limit=current_batch_limit, force=force)
            if not lots:
                break

            batch_ids = [l["lot_id"] for l in lots]
            print(f"\n[Batch {batch_idx}/{total_batches}] Processing {len(lots)} lots: {', '.join(batch_ids)}...", flush=True)

            prompt = build_batch_prompt(lots)
            t0 = time.time()
            results = loop.run_until_complete(appraiser.appraise_batch(prompt))
            elapsed = time.time() - t0

            if not results:
                print(f"  [-] Batch {batch_idx} extraction returned no valid JSON. Skipping to next batch.", flush=True)
                errors.append(f"Batch {batch_idx} extraction failed for lots {batch_ids}")
                processed_count += len(lots)
                continue

            result_map = {str(r.get("lot_id", "")): r for r in results}
            for lot in lots:
                lid = lot["lot_id"]
                ai_data = result_map.get(lid)
                if not ai_data:
                    print(f"  [?] Lot {lid}: missing in AI output.", flush=True)
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

            processed_count += len(lots)
            pct = (processed_count / session_limit * 100) if session_limit else 100.0
            print(f"  => Batch completed in {elapsed:.1f}s | Progress: {processed_count}/{session_limit} ({pct:.1f}%)", flush=True)

            if processed_count < session_limit and not stop_requested and delay > 0:
                time.sleep(delay)

            if lot_ids:
                break
    finally:
        if prev_sigint is not None:
            try:
                signal.signal(signal.SIGINT, prev_sigint)
            except (ValueError, AttributeError):
                pass

    total_time = time.time() - start_time
    print("\n" + "=" * 70, flush=True)
    print("REFINEMENT SESSION FINISHED", flush=True)
    print(f"Lots Processed: {processed_count:,} | Successfully Updated: {success_count:,}", flush=True)
    print(f"Elapsed Time: {total_time:.1f}s ({total_time / max(processed_count, 1):.2f}s/lot)", flush=True)
    print(f"Remaining in DB: {count_unrefined_lots(conn, force=False):,} lots", flush=True)
    print("=" * 70, flush=True)

    return processed_count, success_count, errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Continuous Watch Refinement Engine (Gemini Web)")
    parser.add_argument("--all", action="store_true", help="Process all unrefined lots continuously")
    parser.add_argument("--batch-size", type=int, default=3, help="Number of lots per prompt (default: 3)")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of lots to process in this session")
    parser.add_argument("--lot-id", type=str, help="Specific lot ID(s) to process, comma-separated")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to SQLite database")
    parser.add_argument("--model", type=str, default="gemini-flash", help="Model name (default: gemini-flash)")
    parser.add_argument("--delay", type=float, default=1.5, help="Pause in seconds between batches (default: 1.5)")
    parser.add_argument("--dry-run", action="store_true", help="Print prompt without making network calls")
    parser.add_argument("--force", action="store_true", help="Re-refine lots even if ai_json already exists")
    parser.add_argument("--update-db", action="store_true", help="Explicitly write changes (always on with --all)")
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
    )
    if errors:
        for err in errors:
            print(f"[ERROR] {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
