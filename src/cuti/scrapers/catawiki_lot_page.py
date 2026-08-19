"""Pure parser for Catawiki lot-page Details and description fields."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser

from ..normalize import Rules


@dataclass(frozen=True, slots=True)
class LotDetails:
    """Typed Details fields plus source text retained for later resolution."""

    brand: str | None
    model: str | None
    ref_number: str | None
    caliber: str | None
    case_code: str | None
    movement: str | None
    case_material: str | None
    case_diameter_mm: int | None
    details: dict[str, str]
    description: str | None

    @property
    def specs(self) -> dict[str, str]:
        return self.details


_LABELS = {
    "brand": "brand",
    "model": "model",
    "reference": "ref_number",
    "reference number": "ref_number",
    "ref number": "ref_number",
    "ref": "ref_number",
    "caliber": "caliber",
    "calibre": "caliber",
    "case code": "case_code",
    "movement": "movement",
    "case material": "case_material",
    "case diameter": "case_diameter_mm",
    "diameter": "case_diameter_mm",
}
_DIAMETER_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*mm\b", re.IGNORECASE)


def _label(value: str) -> str:
    return " ".join(value.lower().replace(":", " ").split())


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = " ".join(value.split())
    return value or None


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[tuple[str, str]] = []
        self._row: list[str] = []
        self._cell: list[str] | None = None
        self._cell_tag: str | None = None
        self._definition_label: str | None = None
        self._description_depth = 0
        self._description: list[str] = []
        self.items: list[str] = []
        self._item_depth = 0
        self._item: list[str] = []

    @staticmethod
    def _attrs(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {key.lower(): (value or "") for key, value in attrs}

    @staticmethod
    def _is_description(attrs: dict[str, str]) -> bool:
        marker = " ".join(attrs.get(key, "") for key in ("class", "id", "data-testid", "itemprop")).lower()
        return "description" in marker or marker.strip() == "desc"

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = self._attrs(attrs)
        marker = " ".join(attributes.get(key, "") for key in ("class", "id", "data-testid")).lower()
        if self._item_depth:
            self._item_depth += 1
        elif any(token in marker for token in ("detail-item", "details-item", "specification-item", "lot-details__item")):
            self._item_depth = 1
            self._item = []
        if self._description_depth:
            self._description_depth += 1
        elif self._is_description(attributes):
            self._description_depth += 1
        if tag.lower() == "tr":
            self._row = []
        elif tag.lower() in {"td", "th", "dt", "dd"} and self._row is not None:
            self._cell = []
            self._cell_tag = tag.lower()

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)
        if self._description_depth:
            self._description.append(data)
        if self._item_depth:
            self._item.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th", "dt", "dd"} and self._cell is not None:
            value = _clean("".join(self._cell)) or ""
            if tag == "dt":
                self._definition_label = value
            elif tag == "dd" and self._definition_label is not None:
                self.rows.append((self._definition_label, value))
                self._definition_label = None
            else:
                self._row.append(value)
            self._cell = None
            self._cell_tag = None
        elif tag == "tr" and len(self._row) >= 2:
            self.rows.append((self._row[0], " ".join(self._row[1:])))
            self._row = []
        if self._description_depth:
            self._description_depth -= 1
        if self._item_depth:
            self._item_depth -= 1
            if not self._item_depth:
                value = _clean(" ".join(self._item))
                if value:
                    self.items.append(value)


def _movement(value: str | None) -> str | None:
    text = (value or "").lower()
    if any(token in text for token in ("quartz",)):
        return "quartz"
    if any(token in text for token in ("manual", "hand-wound", "hand wound", "handwound")):
        return "manual"
    if any(token in text for token in ("automatic", "auto", "self-winding", "self winding")):
        return "auto"
    return None


def _material(value: str | None) -> str | None:
    text = (value or "").lower()
    if not text:
        return None
    if "titanium" in text:
        return "titanium"
    if any(token in text for token in ("gold plated", "gold-plated", "goldplated", "plated gold", "rolled gold")):
        return "gold_plated"
    if "gold" in text or re.search(r"\b\d{2}\s*k\b", text):
        return "gold"
    if any(token in text for token in ("steel", "stainless")):
        return "steel"
    return "other"


def _diameter(value: str | None) -> int | None:
    match = _DIAMETER_RE.search(value or "")
    if match is None:
        return None
    number = match.group(1).replace(",", ".")
    try:
        result = float(number)
    except ValueError:
        return None
    if not result.is_integer() or not 15 <= result <= 60:
        return None
    return int(result)


def parse_lot_page(html: str, *, rules: Rules | None = None) -> LotDetails:
    """Parse one lot page; absent or unrecognised fields remain ``None``."""
    parser = _PageParser()
    parser.feed(html)
    parser.close()
    specs: dict[str, str] = {}
    for key, value in parser.rows:
        key = _clean(key)
        value = _clean(value)
        if key and value:
            specs[key] = value
    for item in parser.items:
        normalized = _label(item)
        for name in sorted(_LABELS, key=len, reverse=True):
            if normalized.startswith(name + " "):
                raw_value = _clean(item[len(name):])
                if raw_value:
                    specs.setdefault(name.title(), raw_value)
                break
    typed: dict[str, str | int | None] = {name: None for name in _LABELS.values()}
    for key, value in specs.items():
        field = _LABELS.get(_label(key))
        if field is not None:
            typed[field] = value
    description = _clean(" ".join(parser._description))
    caliber = typed["caliber"]
    case_code = typed["case_code"]
    if rules is not None:
        from ..normalize_identity import split_identity

        identity = split_identity(str(typed["brand"] or ""), typed["ref_number"],
                                  title=str(typed["model"] or ""), description=description or "", rules=rules)
        caliber = caliber or identity.caliber
        case_code = case_code or identity.case_code
    return LotDetails(
        brand=typed["brand"], model=typed["model"], ref_number=typed["ref_number"],
        caliber=caliber, case_code=case_code, movement=_movement(typed["movement"]),
        case_material=_material(typed["case_material"]), case_diameter_mm=_diameter(typed["case_diameter_mm"]),
        details=specs, description=description,
    )
