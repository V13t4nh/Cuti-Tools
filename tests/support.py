"""Shared test helpers: an isolated project home with sane settings."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from cuti.config import Settings, load_settings
from cuti.models import Condition, Lot, WatchForm
from cuti.normalize import Rules, load_rules
from cuti.storage import connect, upsert_lots

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 8, 1)
NOW = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)


class ProjectTestCase(unittest.TestCase):
    """Base case giving each test its own project home and database."""

    env_overrides: dict[str, str] = {}

    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp(prefix="cuti-test-"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        (self.home / "config").mkdir(parents=True, exist_ok=True)
        shutil.copy(PROJECT_ROOT / "config" / "rules.json", self.home / "config" / "rules.json")
        shutil.copytree(
            PROJECT_ROOT / "data" / "sample", self.home / "data" / "sample", dirs_exist_ok=True
        )
        self.settings = self.make_settings(**self.env_overrides)
        self.rules: Rules = load_rules(self.settings.rules_path)
        self.conn = connect(self.settings.db_path)
        self.addCleanup(self.conn.close)

    def make_settings(self, **overrides: str) -> Settings:
        env = {
            "CUTI_LOTS_SOURCE_URL": str(self.home / "data" / "sample" / "catawiki" / "page-1.html"),
            "CUTI_DEALS_SOURCE_URL": str(self.home / "data" / "sample" / "deals" / "deals.json"),
            **overrides,
        }
        return load_settings(env=env, base_dir=self.home)

    def write_json(self, relative: str, payload: object) -> Path:
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def write_text(self, relative: str, content: str) -> Path:
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def seed_lots(self, lots: list[Lot]) -> None:
        upsert_lots(self.conn, lots, NOW)


def make_lot(
    lot_id: str,
    *,
    title: str = "Omega Seamaster Diver 300M 210.30.42 - watch only",
    brand: str = "omega",
    model_key: str = "omega:210.30.42",
    condition: Condition = Condition.NAKED,
    hearts: int = 10,
    sold: bool = True,
    hammer_eur: int | None = 3000,
    ended_at: date = date(2026, 7, 1),
    days_open: int = 10,
    source: str = "catawiki",
    form: WatchForm = WatchForm.ROUND,
) -> Lot:
    """Factory keeping tests short and intention-revealing."""
    return Lot(
        lot_id=lot_id,
        source=source,
        title=title,
        brand=brand,
        model_key=model_key,
        condition_tag=condition,
        hearts=hearts,
        sold=sold,
        hammer_eur=hammer_eur if sold else None,
        opened_at=date.fromordinal(ended_at.toordinal() - days_open),
        ended_at=ended_at,
        url=f"https://example.invalid/lots/{lot_id}",
        form=form,
    )
