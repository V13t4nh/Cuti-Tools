"""SQLite DDL for the current storage schema.

Kept separate from migration control flow so the public schema facade stays
small enough to review alongside the version transition code.
"""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lots (
    lot_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    brand TEXT NOT NULL,
    model_key TEXT NOT NULL,
    condition_tag TEXT NOT NULL CHECK (condition_tag IN ('naked', 'box', 'papers', 'fullset')),
    form TEXT NOT NULL DEFAULT 'unknown' CHECK (form IN ('round', 'rectangular', 'square', 'tonneau', 'other', 'unknown')),
    hearts INTEGER NOT NULL,
    sold INTEGER NOT NULL,
    hammer_eur INTEGER,
    opened_at TEXT NOT NULL,
    ended_at TEXT NOT NULL,
    url TEXT NOT NULL,
    subtitle TEXT,
    bids_count INTEGER,
    source_available TEXT NOT NULL DEFAULT '__YES__',
    source_checked_at TEXT,
    model TEXT,
    ref_number TEXT,
    caliber TEXT,
    case_code TEXT,
    movement TEXT,
    case_material TEXT,
    case_diameter_mm INTEGER,
    specs_json TEXT,
    ai_json TEXT,
    needs_review INTEGER NOT NULL DEFAULT 0,
    review_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (review_status IN ('pending', 'resolved', 'ignored')),
    reviewed_at TEXT,
    override_json TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_lots_model ON lots(model_key, condition_tag, ended_at);
CREATE INDEX IF NOT EXISTS idx_lots_brand_form ON lots(brand, form, ended_at);
CREATE INDEX IF NOT EXISTS idx_lots_brand_caliber_case
    ON lots(brand, caliber, case_code);

CREATE TABLE IF NOT EXISTS lot_desc (
    lot_id TEXT PRIMARY KEY,
    desc_z BLOB NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS lots_fts USING fts5(
    title, brand, model, content='lots', content_rowid='rowid'
);
CREATE TRIGGER IF NOT EXISTS lots_ai AFTER INSERT ON lots BEGIN
    INSERT INTO lots_fts(rowid, title, brand, model)
    VALUES (new.rowid, new.title, new.brand, new.model);
END;
CREATE TRIGGER IF NOT EXISTS lots_ad AFTER DELETE ON lots BEGIN
    INSERT INTO lots_fts(lots_fts, rowid, title, brand, model)
    VALUES ('delete', old.rowid, old.title, old.brand, old.model);
END;
CREATE TRIGGER IF NOT EXISTS lots_au AFTER UPDATE ON lots BEGIN
    INSERT INTO lots_fts(lots_fts, rowid, title, brand, model)
    VALUES ('delete', old.rowid, old.title, old.brand, old.model);
    INSERT INTO lots_fts(rowid, title, brand, model)
    VALUES (new.rowid, new.title, new.brand, new.model);
END;

-- Lots that are still open. The source cannot be searched for closed lots, so
-- ids are captured while bidding runs and settled once bidding ends. Rows are
-- deleted on settle: this is a work queue, not history.
CREATE TABLE IF NOT EXISTS live_watch (
    lot_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    subtitle TEXT,
    url TEXT NOT NULL,
    bidding_end_at TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_live_watch_end ON live_watch(bidding_end_at);

CREATE TABLE IF NOT EXISTS deals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    raw_title TEXT NOT NULL,
    ask_vnd INTEGER NOT NULL,
    url TEXT NOT NULL,
    seen_at TEXT NOT NULL,
    model_key TEXT NOT NULL,
    condition_tag TEXT NOT NULL,
    form TEXT NOT NULL DEFAULT 'unknown',
    dedupe_hash TEXT NOT NULL UNIQUE,
    quoted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_deals_quoted ON deals(quoted, seen_at);

CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_id INTEGER REFERENCES deals(id),
    model_key TEXT NOT NULL,
    condition_tag TEXT NOT NULL,
    form TEXT NOT NULL DEFAULT 'unknown',
    title TEXT NOT NULL,
    cost_vnd INTEGER NOT NULL,
    sample_size INTEGER NOT NULL,
    attempt_count INTEGER NOT NULL,
    sell_through_rate REAL NOT NULL,
    net_min_eur REAL,
    net_avg_eur REAL,
    net_max_eur REAL,
    hammer_p25_eur REAL,
    hammer_median_eur REAL,
    hammer_p75_eur REAL,
    median_days_to_close REAL,
    threshold_eur REAL NOT NULL,
    verdict TEXT NOT NULL,
    assumptions TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_quotes_model ON quotes(model_key, created_at);

CREATE TABLE IF NOT EXISTS quote_comparables (
    quote_id INTEGER NOT NULL REFERENCES quotes(id),
    lot_id TEXT NOT NULL,
    score REAL NOT NULL,
    snapshot TEXT NOT NULL,
    PRIMARY KEY (quote_id, lot_id)
);

CREATE TABLE IF NOT EXISTS alert_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_id INTEGER NOT NULL REFERENCES quotes(id),
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TEXT NOT NULL,
    sent_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_outbox_status ON alert_outbox(status, created_at);
"""
