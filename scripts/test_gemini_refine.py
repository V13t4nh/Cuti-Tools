"""Test script to refine watch lot data using Google Gemini Web API.

Supports micro-batching (default: 3 lots per prompt) with explicit lot_id delimiters
to ensure fast, reliable, and context-isolated extraction.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import sqlite3
import sys
import zlib
from pathlib import Path
from typing import Any, Mapping

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


def load_cookies() -> tuple[str, str]:
    """Load __Secure-1PSID and __Secure-1PSIDTS from environment or file."""
    psid = os.getenv("GEMINI_SECURE_1PSID") or os.getenv("SECURE_1PSID") or ""
    psidts = os.getenv("GEMINI_SECURE_1PSIDTS") or os.getenv("SECURE_1PSIDTS") or ""

    if (not psid or not psidts) and COOKIE_FILE_PATH.is_file():
        try:
            data = json.loads(COOKIE_FILE_PATH.read_text(encoding="utf-8"))
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


def fetch_lots(
    conn: sqlite3.Connection,
    lot_ids: list[str] | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Fetch a batch of lots and decompress their descriptions."""
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
        rows = cur.fetchall()
    else:
        # Prioritize lots with needs_review = 1
        cur.execute(
            """
            SELECT l.lot_id, l.title, l.brand, l.model, l.ref_number, l.caliber,
                   l.case_code, l.movement, l.case_material, l.case_diameter_mm,
                   l.condition_tag, l.needs_review, l.review_status, l.specs_json,
                   d.desc_z
            FROM lots l
            JOIN lot_desc d ON l.lot_id = d.lot_id
            WHERE l.needs_review = 1
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()
        if not rows:
            cur.execute(
                """
                SELECT l.lot_id, l.title, l.brand, l.model, l.ref_number, l.caliber,
                       l.case_code, l.movement, l.case_material, l.case_diameter_mm,
                       l.condition_tag, l.needs_review, l.review_status, l.specs_json,
                       d.desc_z
                FROM lots l
                JOIN lot_desc d ON l.lot_id = d.lot_id
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
    """Build user prompt with clear boundaries and lot_id headers."""
    lot_blocks = []
    for lot in lots:
        lid = lot["lot_id"]
        specs_str = lot.get("specs_json") or "None"
        desc_str = lot.get("description") or "None"
        lot_blocks.append(
            f"=== LOT_START [ID: {lid}] ===\n"
            f"[LOT TITLE]\n{lot.get('title')}\n\n"
            f"[CURRENT PLATFORM SPECS]\n{specs_str}\n\n"
            f"[SELLER DESCRIPTION]\n{desc_str}\n"
            f"=== LOT_END [ID: {lid}] ==="
        )

    count_str = f"{len(lots)} watch auction lot(s)"
    prompt = (
        f"Analyze the following {count_str} and produce the structured JSON array with matching 'lot_id':\n\n"
        + "\n\n".join(lot_blocks)
    )
    return prompt


def extract_json_from_text(text: str) -> list[dict[str, Any]] | None:
    """Extract JSON array of objects from markdown codeblock or raw response text."""
    # Strategy 1: Find all opening ```json or ``` markers and test slices in reverse
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

    # Strategy 2: Bracket matching from every '[' to the last ']' from right to left
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

    # Strategy 3: Outermost braces { ... } if single object returned
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            p = json.loads(text[start : end + 1])
            if isinstance(p, dict):
                return [p]
        except Exception:
            pass

    # Strategy 4: Direct parse
    try:
        p = json.loads(text.strip())
        if isinstance(p, list):
            return p
        elif isinstance(p, dict):
            return [p]
    except Exception:
        pass

    return None


async def run_gemini_query(
    prompt: str,
    psid: str,
    psidts: str,
    model: str = "gemini-flash",
    max_retries: int = 2,
) -> tuple[str, str | None]:
    """Execute query using gemini_webapi with automatic backoff retry."""
    try:
        from gemini_webapi import GeminiClient
    except ImportError:
        raise RuntimeError(
            "Package 'gemini_webapi' is not installed. Run: pip install -U gemini_webapi"
        )

    client = GeminiClient(psid, psidts, proxy=None)
    await client.init(timeout=30, auto_close=False, auto_refresh=True)

    full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"
    for attempt in range(max_retries + 1):
        response = await client.generate_content(
            full_prompt,
            model=model,
            temporary=True,
        )
        text = response.text or ""
        if "having a hard time fulfilling your request" in text or "encountering an error" in text:
            if attempt < max_retries:
                print(f"[*] Temporary rate-limit response, backing off 4s (retry {attempt + 1}/{max_retries})...")
                await asyncio.sleep(4)
                continue
        thought = getattr(response, "thought", None)
        return text, thought

    return "", None


def apply_refinement_to_db(
    conn: sqlite3.Connection,
    lot_id: str,
    ai_data: dict[str, Any],
) -> None:
    """Save ai_json, override_json, and update columns in SQLite."""
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
    print(f"[+] Successfully updated lot {lot_id} in database (needs_review={'0' if should_resolve else '1'}).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gemini Web Watch Refinement Engine (Micro-Batching)")
    parser.add_argument("--lot-id", type=str, help="Specific lot ID(s) separated by comma")
    parser.add_argument("--batch-size", type=int, default=3, help="Number of lots per prompt (default: 3)")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to SQLite auctions.db")
    parser.add_argument("--model", type=str, default="gemini-flash", help="Gemini model (default: gemini-flash)")
    parser.add_argument("--dry-run", action="store_true", help="Print prompt without calling Gemini Web API")
    parser.add_argument("--update-db", action="store_true", help="Apply results to SQLite database")
    args = parser.parse_args()

    if not args.db.is_file():
        print(f"[-] Database file not found: {args.db}")
        sys.exit(1)

    target_ids = [s.strip() for s in args.lot_id.split(",")] if args.lot_id else None
    batch_size = len(target_ids) if target_ids else args.batch_size

    conn = sqlite3.connect(args.db)
    lots = fetch_lots(conn, lot_ids=target_ids, limit=batch_size)
    if not lots:
        print("[-] No matching lots found in database.")
        sys.exit(1)

    print("=" * 70)
    print(f"FETCHED BATCH OF {len(lots)} LOT(S):")
    print("=" * 70)
    for idx, lot in enumerate(lots, 1):
        print(f"[{idx}] LOT ID: {lot['lot_id']:<10} | Brand: {lot['brand']:<10} | Current Ref: {str(lot['ref_number']):<12} | Needs Review: {lot['needs_review']}")
        print(f"    Title: {lot['title'][:65]}...")
    print("=" * 70)

    user_prompt = build_batch_prompt(lots)

    if args.dry_run:
        print("\n[DRY RUN MODE] Prompt snippet:")
        print("-" * 70)
        print(user_prompt[:800] + "\n... [truncated for preview] ...")
        print("-" * 70)
        print("[*] Dry run completed. No API request was made.")
        return

    psid, psidts = load_cookies()
    if not psid or not psidts:
        print("\n[!] ERROR: Missing Gemini Web authentication cookies!")
        print("    Please set GEMINI_SECURE_1PSID and GEMINI_SECURE_1PSIDTS in .env")
        print(f"    Or create '{COOKIE_FILE_PATH}' with __Secure-1PSID and __Secure-1PSIDTS.")
        sys.exit(1)

    print(f"[*] Dispatching batch of {len(lots)} lots to Gemini Web ({args.model})...")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        raw_text, thought = loop.run_until_complete(
            run_gemini_query(user_prompt, psid, psidts, model=args.model)
        )
    except Exception as exc:
        print(f"\n[-] Gemini Query Failed: {exc}")
        sys.exit(1)

    extracted_items = extract_json_from_text(raw_text)
    if not extracted_items:
        print("\n[-] Could not parse JSON from model output.")
        print("Raw response:\n", raw_text)
        sys.exit(1)

    print(f"\n[+] Successfully received and parsed {len(extracted_items)} lot results!")

    # Index by lot_id
    lot_map = {str(l["lot_id"]): l for l in lots}

    for item in extracted_items:
        item_id = str(item.get("lot_id", ""))
        original_lot = lot_map.get(item_id)

        print("\n" + "=" * 70)
        print(f"RESULTS FOR LOT ID: {item_id}")
        print("=" * 70)

        ident = item.get("identity", {})
        acc = item.get("accessories", {})
        audit = item.get("audit", {})

        if original_lot:
            print("BEFORE vs AFTER COMPARISON:")
            print(f"  Brand        : {original_lot['brand']} -> {ident.get('brand')}")
            print(f"  Model        : {original_lot['model']} -> {ident.get('model')}")
            print(f"  Ref Number   : {original_lot['ref_number']} -> {ident.get('ref_number')}")
            print(f"  Caliber      : {original_lot['caliber']} -> {ident.get('caliber')}")
            print(f"  Condition Tag: {original_lot['condition_tag']} -> {acc.get('true_condition_tag')}")
        else:
            print(f"  Extracted Ref: {ident.get('ref_number')}")

        if acc.get("fake_fullset_detected"):
            print(f"  [!] FAKE FULLSET: {acc.get('fake_fullset_reason')}")

        contradictions = audit.get("contradictions", [])
        if contradictions:
            print("  Contradictions detected:")
            for c in contradictions:
                print(f"    - {c}")

        print(f"  Confidence   : {audit.get('confidence')}")
        print(f"  Reasoning    : {audit.get('reasoning_summary')}")

        if args.update_db and item_id:
            apply_refinement_to_db(conn, item_id, item)

    if not args.update_db:
        print("\n[i] Note: Database was NOT modified. Use '--update-db' to apply changes.")


if __name__ == "__main__":
    main()
