from __future__ import annotations
import difflib
import json
import re
import sqlite3

_VOCAB_CACHE: tuple[int, set[str], list[str]] = (0, set(), [])

ROMAN_TO_ARABIC = {
    "ii": "2", "iii": "3", "iv": "4", "v": "5",
    "vi": "6", "vii": "7", "viii": "8", "ix": "9",
    "xi": "11", "xii": "12", "xiii": "13", "xiv": "14", "xv": "15",
    "xvi": "16", "xvii": "17", "xviii": "18", "xix": "19", "xx": "20",
    "xxi": "21",
}
NUMERAL_MAP = {**ROMAN_TO_ARABIC, **{v: k for k, v in ROMAN_TO_ARABIC.items()}}

def normalize_search_query(q: str) -> str:
    return re.sub(r"\b(\d{2})\s*[-]?\s*mm\b", r"\1mm", q, flags=re.IGNORECASE)

def get_watch_vocab(conn: sqlite3.Connection) -> tuple[set[str], list[str]]:
    global _VOCAB_CACHE
    has_lots = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='lots'").fetchone()
    if not has_lots:
        return set(), []
    count = conn.execute("SELECT count(*) FROM lots").fetchone()[0]
    if _VOCAB_CACHE[0] == count and _VOCAB_CACHE[1]:
        return _VOCAB_CACHE[1], _VOCAB_CACHE[2]
    brands = {r[0].lower() for r in conn.execute("SELECT DISTINCT lower(brand) FROM lots WHERE brand IS NOT NULL").fetchall() if r[0]}
    models = {r[0].lower() for r in conn.execute("SELECT DISTINCT lower(model) FROM lots WHERE model IS NOT NULL").fetchall() if r[0]}
    vocab = set(brands)
    for m in models:
        for part in m.replace("-", " ").split():
            if len(part) >= 3 and part.isalpha():
                vocab.add(part)
    has_canon = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='canonical_products'").fetchone()
    if has_canon:
        for r in conn.execute("SELECT canonical_name, brand, aliases_json FROM canonical_products").fetchall():
            for text in (r[0], r[1]):
                if text:
                    for part in text.replace("-", " ").split():
                        if len(part) >= 3 and part.isalpha():
                            vocab.add(part.lower())
            if r[2]:
                try:
                    for a in json.loads(r[2]):
                        for part in str(a).replace("-", " ").split():
                            if len(part) >= 3 and part.isalpha():
                                vocab.add(part.lower())
                except Exception:
                    pass
    vocab_list = sorted(vocab)
    _VOCAB_CACHE = (count, vocab, vocab_list)
    return vocab, vocab_list

def split_compound(word: str, vocab: set[str]) -> list[str]:
    w_low = word.lower()
    if w_low in vocab:
        return [word]
    if len(word) >= 6 and word.isalpha():
        for i in range(3, len(word) - 2):
            w1, w2 = w_low[:i], w_low[i:]
            if w1 in vocab and w2 in vocab:
                return [w1, w2]
    return [word]

def build_search_conditions(words: list[str], table: str = "lots") -> tuple[list[str], list[str]]:
    where, args = [], []
    title_sp = "(' ' || replace(replace(replace(lower(coalesce(title, '')), '-', ' '), '/', ' '), '.', ' ') || ' ')"
    sub_sp = "(' ' || replace(replace(replace(lower(coalesce(subtitle, '')), '-', ' '), '/', ' '), '.', ' ') || ' ')"
    for raw_w in words:
        w = raw_w.lower()
        if w.endswith("mm") and w[:-2].isdigit() and (15 <= int(w[:-2]) <= 65):
            diam = int(w[:-2])
            conds = [
                f"{title_sp} LIKE ?", f"{title_sp} LIKE ?", f"{title_sp} LIKE ?",
                f"{sub_sp} LIKE ?", f"{sub_sp} LIKE ?", f"{sub_sp} LIKE ?",
            ]
            args.extend([f"% {diam}mm%", f"% {diam} mm%", f"% {diam} %", f"% {diam}mm%", f"% {diam} mm%", f"% {diam} %"])
            if table == "lots":
                conds.append("case_diameter_mm = ?")
                args.append(diam)
            where.append(f"({' OR '.join(conds)})")
            continue
        alt_num = NUMERAL_MAP.get(w)
        if alt_num or (w.isdigit() and len(w) <= 2):
            conds = [f"{title_sp} LIKE ?", f"{sub_sp} LIKE ?"]
            args.extend([f"% {w} %", f"% {w} %"])
            conds.append("lower(coalesce(lot_id, '')) = ?")
            args.append(w)
            if alt_num:
                conds.extend([f"{title_sp} LIKE ?", f"{sub_sp} LIKE ?"])
                args.extend([f"% {alt_num} %", f"% {alt_num} %"])
            where.append(f"({' OR '.join(conds)})")
            continue
        clean = w.replace("-", "").replace(" ", "")
        is_compound = (clean != w) or (len(clean) >= 5) or (any(c.isdigit() for c in clean) and any(c.isalpha() for c in clean))
        has_digits = any(c.isdigit() for c in w)
        conds = [f"{title_sp} LIKE ?", f"{sub_sp} LIKE ?"]
        args.extend([f"% {w}%", f"% {w}%"])
        if has_digits:
            conds.append("instr(lower(coalesce(lot_id, '')), ?) > 0")
            args.append(w)
        else:
            conds.append("lower(coalesce(lot_id, '')) = ?")
            args.append(w)
        if is_compound:
            conds.append("instr(replace(replace(lower(coalesce(title, '')), '-', ''), ' ', ''), ?) > 0")
            args.append(clean)
        elif has_digits:
            conds.append("instr(lower(coalesce(title, '')), ?) > 0")
            args.append(w)
        where.append(f"({' OR '.join(conds)})")
    return where, args


def typo_correct_words(words: list[str], vocab: set[str], vocab_list: list[str]) -> tuple[list[str], bool]:
    corrected = []
    any_diff = False
    for w in words:
        if w in vocab:
            corrected.append(w)
        else:
            matches = difflib.get_close_matches(w, vocab_list, n=1, cutoff=0.75)
            if matches:
                corrected.append(matches[0])
                any_diff = True
            else:
                corrected.append(w)
    return corrected, any_diff

def count_with_typo_fallback(
    conn: sqlite3.Connection,
    table: str,
    where: list[str],
    args: list[str],
    words: list[str],
    vocab: set[str],
    vocab_list: list[str],
    query_where: list[str],
    query_args: list[str],
) -> tuple[int, str, list[str]]:
    clause = f" WHERE {' AND '.join(where)}" if where else ""
    total = conn.execute(f"SELECT COUNT(*) FROM {table}{clause}", args).fetchone()[0]
    if total == 0 and words and vocab_list:
        corrected, any_diff = typo_correct_words(words, vocab, vocab_list)
        if any_diff:
            c_where, c_args = build_search_conditions(corrected, table)
            retry_where = [*c_where, *[c for c in where if c not in query_where]]
            retry_args = [*c_args, *args[len(query_args):]]
            retry_clause = f" WHERE {' AND '.join(retry_where)}" if retry_where else ""
            retry_total = conn.execute(f"SELECT COUNT(*) FROM {table}{retry_clause}", retry_args).fetchone()[0]
            if retry_total > 0:
                return retry_total, retry_clause, retry_args
    return total, clause, args
