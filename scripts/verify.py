"""Run the hermetic test and sample-data workflow with a raw audit log."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import traceback
import uuid
from datetime import date, datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_QUERY = "Omega Seamaster Diver 300M 210.30.42"
FROZEN_FILES = (
    "src/cuti/pricing.py",
    "src/cuti/storage/schema_ddl.py",
    "config/rules.json",
)


class FrozenFileError(FileNotFoundError):
    """A file required by the frozen-source integrity check is missing."""


def _frozen_sha256(path: Path) -> str:
    if not path.is_file():
        raise FrozenFileError(f"frozen file is missing: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _frozen_markers(root: Path | None = None) -> list[str]:
    root = PROJECT_ROOT if root is None else root
    return [
        f"FROZEN_SHA256 {relative} {_frozen_sha256(root / relative)}"
        for relative in FROZEN_FILES
    ]


class _Log:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.file = path.open("w", encoding="utf-8", newline="")

    def line(self, text: str = "") -> None:
        self.file.write(text + "\n")
        self.file.flush()

    def write(self, text: str) -> None:
        self.file.write(text)
        self.file.flush()

    def __enter__(self) -> "_Log":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.file.close()


def _environment_trace(log: _Log, env: dict[str, str]) -> None:
    log.line(f"PYTHON={sys.executable}")
    log.line(f"PYTHON_VERSION={sys.version.split()[0]}")
    packages = subprocess.run(
        [sys.executable, "-m", "pip", "list", "--format=freeze"],
        capture_output=True,
        text=True,
        check=False,
    )
    log.line("PACKAGES_BEGIN")
    log.write(packages.stdout)
    if packages.stdout and not packages.stdout.endswith("\n"):
        log.line()
    log.line("PACKAGES_END")
    names = sorted(name for name in env if name.startswith("CUTI_"))
    log.line("CUTI_ENV_NAMES=" + (",".join(names) if names else "(none)"))


def _alerts_sent(db_path: Path) -> int:
    """Read the number of sent alerts from this verification run's database."""
    if not db_path.is_file():
        return 0
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM alert_outbox WHERE status = 'sent'"
        ).fetchone()
    finally:
        conn.close()
    return int(row[0]) if row is not None else 0


def _source_loc_max() -> int:
    return max(
        len(path.read_text(encoding="utf-8").splitlines())
        for path in (PROJECT_ROOT / "src" / "cuti").rglob("*.py")
    )


def _live_fixture_count() -> int:
    fixture_dir = PROJECT_ROOT / "tests" / "fixtures" / "live"
    return sum(1 for path in fixture_dir.glob("*.html") if path.is_file())


def _logic_coverage_fixture_lots(fixture: Path) -> list[object]:
    from cuti.models import Condition, Lot, WatchForm

    lots: list[Lot] = []
    with fixture.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            title = " ".join(
                part for part in (row["brand"], row["model"], row["ref_number"], "watch only") if part
            )
            lots.append(
                Lot(
                    lot_id=row["lot_id"],
                    source="catawiki",
                    title=title,
                    brand=row["brand"].lower(),
                    model_key=(
                        "omega:210.30.42"
                        if row["brand"].lower() == "omega"
                        else f"{row['brand'].lower()}:{row['model'].lower()}"
                    ),
                    condition_tag=Condition.parse(row["condition_tag"]),
                    form=WatchForm.parse(row["form"]),
                    hearts=int(row["hearts"]),
                    sold=row["status"] == "sold",
                    hammer_eur=int(row["hammer_eur"]) if row["hammer_eur"] else None,
                    opened_at=date.fromisoformat(row["opened_at"]),
                    ended_at=date.fromisoformat(row["ended_at"]),
                    url=row["url"],
                    bids_count=int(row["bids_count"]),
                    description=row["description"],
                )
            )
    return lots


def _logic_coverage_markers() -> list[str]:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    fixture = PROJECT_ROOT / "tests" / "fixtures" / "logic_coverage" / "logic_coverage.csv"
    rows = fixture.read_text(encoding="utf-8").splitlines() if fixture.is_file() else []
    count = max(0, len(rows) - 1)
    verdicts: set[str] = set()
    if fixture.is_file():
        from cuti.config import load_settings
        from cuti.evaluation import evaluate_deal
        from cuti.normalize import load_rules
        from cuti.storage import connect, upsert_lots

        with tempfile.TemporaryDirectory(prefix="cuti-logic-coverage-") as directory:
            db_path = Path(directory) / "logic-coverage.db"
            settings = load_settings(
                env={"CUTI_DB_PATH": str(db_path)}, base_dir=PROJECT_ROOT
            )
            rules = load_rules(settings.rules_path)
            conn = connect(db_path)
            try:
                upsert_lots(
                    conn,
                    _logic_coverage_fixture_lots(fixture),
                    datetime(2026, 8, 1, tzinfo=timezone.utc),
                )
                for cost in (1000, 1400, 1500):
                    verdicts.add(
                        evaluate_deal(
                            conn,
                            rules,
                            settings,
                            query=ACCEPTANCE_QUERY,
                            cost=cost,
                            currency="eur",
                            condition="naked",
                            today=date(2026, 8, 1),
                        ).verdict.value
                    )
                verdicts.add(
                    evaluate_deal(
                        conn,
                        rules,
                        settings,
                        query="Unknown Zenith El Primero 9999",
                        cost=1000,
                        currency="eur",
                        condition="naked",
                        today=date(2026, 8, 1),
                    ).verdict.value
                )
            finally:
                conn.close()
    return [
        f"LOGIC_COVERAGE_ROWS={count}",
        "LOGIC_COVERAGE_VERDICTS=" + ",".join(sorted(verdicts)),
    ]


def _run(arguments: list[str], env: dict[str, str], log: _Log) -> str:
    command = " ".join(arguments)
    print(f"\n> {command}", flush=True)
    log.line(f"> {command}")
    result = subprocess.run(
        arguments,
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if result.stdout:
        print(result.stdout, end="", flush=True)
        log.write(result.stdout)
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, arguments)
    return result.stdout


def _canonicalize_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def _chart_markers(db_path: Path, env: dict[str, str], today: date) -> list[str]:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    from cuti.config import load_settings
    from cuti.evaluation_chart import evaluate_deal_with_chart
    from cuti.liquidity_timeline import completed_quarters
    from cuti.normalize import load_rules
    from cuti.storage import connect

    settings = load_settings(env=env, base_dir=PROJECT_ROOT)
    rules = load_rules(settings.rules_path)
    with connect(db_path) as conn:
        bundle = evaluate_deal_with_chart(
            conn,
            rules,
            settings,
            query=ACCEPTANCE_QUERY,
            cost=1000,
            currency="eur",
            condition="naked",
            today=today,
        )
    decision = bundle.decision
    expected = {
        "net_p25_eur": 1382.0278125,
        "net_median_eur": 1522.28375,
        "net_p75_eur": 1827.6215625,
        "verdict": "green",
        "sample_size": 8,
        "heart_to_hammer_rate": 1.0,
        "median_days_to_close": 18.5,
        "max_buy_cost_vnd": 55925870,
    }
    actual = {name: getattr(decision, name) for name in expected}
    if actual != expected:
        raise AssertionError(f"evaluate contract mismatch: {actual!r}")
    series = bundle.chart.liquidity_series
    returned = len(series or ())
    total = len(completed_quarters(today, settings.comparable_window_days))
    return [
        f"LIQ_SERIES_SAMPLE=windows={returned} dropped={total - returned}",
        "EVALUATE_CONTRACT=" + json.dumps(actual, sort_keys=True, separators=(",", ":")),
    ]


def _verify_sample_contract(
    base: list[str], env: dict[str, str], run_dir: Path, day_dir: Path, log: _Log
) -> None:
    before_path = day_dir / "liquidity-before.json"
    after_path = day_dir / "liquidity-after.json"
    initial_commands = (
        ["--json", "init-db"],
        ["--json", "ingest"],
        [
            "--json",
            "quote",
            "--title",
            "Omega Speedmaster Professional 311.30.42 full set",
            "--cost-vnd",
            "30000000",
            "--condition",
            "fullset",
            "--form",
            "round",
        ],
        ["--json", "watch"],
    )
    for command in initial_commands:
        _run([*base, *command], env, log)
    before_path.write_text(
        _run([*base, "--json", "liquidity"], env, log), encoding="utf-8"
    )
    after_output = _run([*base, "--json", "liquidity"], env, log)
    after_path.write_text(after_output, encoding="utf-8")
    _canonicalize_json(before_path)
    _canonicalize_json(after_path)
    table_diff = "clean" if before_path.read_bytes() == after_path.read_bytes() else "dirty"
    table_marker = f"LIQ_TABLE_DIFF={table_diff}"
    chart_markers = _chart_markers(run_dir / "auctions.db", env, date(2026, 8, 1))
    for marker in chart_markers:
        print(marker, flush=True)
        log.line(marker)
    print(table_marker, flush=True)
    log.line(table_marker)
    if table_diff != "clean":
        raise AssertionError("liquidity-before.json and liquidity-after.json differ")
    _run([*base, "--json", "report"], env, log)
    _run([*base, "--json", "status"], env, log)
    eur_json = _run(
        [
            *base,
            "--json",
            "evaluate",
            "--query",
            ACCEPTANCE_QUERY,
            "--cost",
            "1000",
            "--currency",
            "eur",
            "--condition",
            "naked",
        ],
        env,
        log,
    ).strip()
    vnd_json = _run(
        [
            *base,
            "--json",
            "evaluate",
            "--query",
            ACCEPTANCE_QUERY,
            "--cost",
            "27000000",
            "--currency",
            "vnd",
            "--condition",
            "naked",
        ],
        env,
        log,
    ).strip()
    eur_payload = json.loads(eur_json)
    if len(eur_payload) != 16:
        raise AssertionError(f"evaluate JSON has {len(eur_payload)} keys")
    currency_marker = (
        "EVALUATE_CURRENCY_DIFF=clean" if eur_json == vnd_json else "EVALUATE_CURRENCY_DIFF=dirty"
    )
    print(currency_marker, flush=True)
    log.line(currency_marker)
    if currency_marker != "EVALUATE_CURRENCY_DIFF=clean":
        raise AssertionError("eur and vnd evaluate JSON differ")


def main() -> int:
    day_dir = PROJECT_ROOT / "var" / "verify" / date.today().isoformat()
    run_dir = day_dir / f"run-{uuid.uuid4().hex[:12]}"
    run_dir.mkdir(parents=True, exist_ok=False)
    log_path = day_dir / "verify.log"
    test_env = {key: value for key, value in os.environ.items() if not key.startswith("CUTI_")}
    python = sys.executable
    with _Log(log_path) as log:
        log.line("COMMAND=" + " ".join([python, "scripts/verify.py"]))
        _environment_trace(log, os.environ)
        query_marker = f"ACCEPTANCE_QUERY={ACCEPTANCE_QUERY}"
        print(query_marker, flush=True)
        log.line(query_marker)
        fixture_marker = f"LIVE_FIXTURES={_live_fixture_count()}"
        print(fixture_marker, flush=True)
        log.line(fixture_marker)
        for logic_marker in _logic_coverage_markers():
            print(logic_marker, flush=True)
            log.line(logic_marker)
        code = 0
        try:
            _run([python, "-m", "unittest", "discover", "-s", "tests", "-v"], test_env, log)
            env = dict(test_env)
            env.update(
                {
                    "CUTI_HOME": str(PROJECT_ROOT),
                    "CUTI_DB_PATH": str(run_dir / "auctions.db"),
                    "CUTI_NOTIFIER_FILE_PATH": str(run_dir / "alerts.jsonl"),
                    "CUTI_REPORT_PATH": str(run_dir / "report.html"),
                    "CUTI_LOTS_SOURCE_URL": str(
                        PROJECT_ROOT / "data" / "sample" / "catawiki" / "page-1.html"
                    ),
                    "CUTI_DEALS_SOURCE_URL": str(
                        PROJECT_ROOT / "data" / "sample" / "deals" / "deals.json"
                    ),
                }
            )
            base = [python, "-m", "cuti.cli", "--home", str(PROJECT_ROOT), "--today", "2026-08-01"]
            marker = f"SRC_LOC_MAX={_source_loc_max()}"
            print(marker, flush=True)
            log.line(marker)
            for frozen_marker in _frozen_markers():
                print(frozen_marker, flush=True)
                log.line(frozen_marker)
            if (PROJECT_ROOT / "data" / "sample").is_dir():
                _verify_sample_contract(base, env, run_dir, day_dir, log)
            success = f"VERIFY OK — artifacts: {run_dir}"
            print(f"\n{success}")
            log.line(success)
        except BaseException:
            code = 1
            traceback.print_exc()
            traceback.print_exc(file=log.file)
        alerts_marker = f"ALERTS_SENT={_alerts_sent(run_dir / 'auctions.db')}"
        print(alerts_marker, flush=True)
        log.line(alerts_marker)
        log.line(f"EXIT={code}")
        return code


if __name__ == "__main__":
    raise SystemExit(main())
