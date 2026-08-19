"""Typed configuration declarations shared by the environment loader."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

Parser = Callable[[str], object]
Validator = Callable[[str, object], object]
Normalizer = Callable[[Path, str, object], object]


@dataclass(frozen=True, slots=True)
class SettingSpec:
    name: str
    attr: str
    parser: Parser
    default: str
    validator: Validator
    normalizer: Normalizer | None = None


@dataclass(frozen=True, slots=True)
class Settings:
    base_dir: Path
    db_path: Path
    rules_path: Path
    lots_source_url: str
    deals_source_url: str
    source_max_pages: int
    catawiki_api_base: str
    catawiki_queries: tuple[str, ...]
    catawiki_search_max_pages: int
    catawiki_batch_size: int
    catawiki_pause_seconds: float
    details_request_delay_seconds: float
    details_max_retries: int
    details_enabled: bool
    settle_max_lots: int
    url_check_max_lots: int
    http_timeout_seconds: float
    response_max_bytes: int
    commission_rate: float
    vat_on_commission_rate: float
    shipping_eur: float
    eur_vnd_rate: float
    min_margin_rate: float
    min_profit_eur: float
    min_comparables: int
    match_threshold: float
    comparable_window_days: int
    liquidity_ref_days: int
    liquidity_hot_hearts: int
    liquidity_w_sell_through: float
    liquidity_w_speed: float
    liquidity_w_hearts: float
    liquidity_min_lots: int
    liquidity_decline_rate: float
    deal_max_age_days: int
    alert_max_attempts: int
    notifier: str
    notifier_file_path: Path
    telegram_api_base: str
    telegram_bot_token: str
    telegram_chat_id: str
    report_path: Path

    @property
    def total_fee_multiplier(self) -> float:
        return self.commission_rate * (1.0 + self.vat_on_commission_rate)
