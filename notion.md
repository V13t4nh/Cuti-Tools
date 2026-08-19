# Bàn giao schema v4 / settle Catawiki

## 1. Commit hash + ngày đóng gói

- Source commit: `2e22736bd85c6384e73ff0474b6cff4edf359b76`
- Ngày đóng gói: 2026-08-19 (Asia/Bangkok)
- `NOTION_SANDBOX/PROVENANCE.json` cũng ghi đúng source commit trên.

## 2. Output verify thật, nguyên văn

```text
Ran 242 tests in 8.917s

OK

VERIFY OK — artifacts: D:\Projects\cuti-tools\var\verify\755c98042cd1
exit code: 0
```

Lệnh đã chạy offline, không cài package:

```text
PYTHONPATH=src;tests .\.venv\Scripts\python.exe scripts\verify.py
```

Kết quả: 242 passed, 0 failed, 0 skipped. Máy Windows này không có GNU `make`; thân lệnh của `make verify` ở trên đã chạy nguyên vẹn với Python trong workspace. Sandbox có GNU Make cần chạy lại literal `make verify`.

## 3. File thêm / sửa / xoá, kèm LOC sau khi sửa

Sửa:

- `config/rules.json` — 60 LOC
- `scripts/generate_sample_data.py` — 306 LOC
- `src/cuti/models.py` — 146 LOC
- `src/cuti/normalize.py` — 146 LOC
- `src/cuti/pipeline/settlement.py` — 157 LOC
- `src/cuti/scrapers/__init__.py` — 7 LOC
- `src/cuti/storage/lots.py` — 204 LOC
- `src/cuti/storage/schema.py` — 147 LOC
- `tests/test_end_to_end_v2.py` — 520 LOC

Thêm:

- `src/cuti/normalize_identity.py` — 88 LOC
- `src/cuti/normalize_rules.py` — 168 LOC
- `src/cuti/pipeline/settlement_resolver.py` — 248 LOC
- `src/cuti/scrapers/catawiki_lot_page.py` — 219 LOC
- `src/cuti/storage/schema_ddl.py` — 150 LOC
- `src/cuti/storage/schema_migration.py` — 49 LOC
- `tests/test_catawiki_lot_page.py` — 66 LOC
- `tests/test_t6_identity_resolver.py` — 137 LOC
- `tests/test_t6_storage_regressions.py` — 125 LOC

Xoá: không có.

Tất cả file `src/cuti` thêm hoặc sửa trong lượt này đều <= 250 LOC. Ba file cũ đã được nêu ngoài phạm vi vẫn vượt trần: `scrapers/catawiki_api.py` 362, `cli.py` 360, `config.py` 302 LOC.

Grep đã có kết quả cho toàn bộ token bắt buộc: `ref_number`, `caliber`, `case_code`, `movement`, `case_material`, `case_diameter_mm`, `specs_json`, `ai_json`, `needs_review`, `review_status`, `override_json`, `model_key_tier`, `lot_desc`, `desc_z`, `zlib`.

## 4. Từng task được giao

- T1: nâng schema lên v4; thêm typed/review columns, index `(brand, caliber, case_code)`, `lot_desc(desc_z)` zlib, FTS title/brand/model và migration v3 -> v4 bảo toàn dữ liệu.
- T2: thêm parser HTML thuần `catawiki_lot_page.py`, Details thô, description thô và chuẩn hoá movement/material/diameter.
- T3: đưa regex/brand identity rules vào `config/rules.json`; tách normalization để mọi file mới/sửa giữ dưới 250 LOC; resolver tạo đủ 5 tier `model_key` và lưu `model_key_tier` vào `specs_json`.
- T4: resolver precedence `override > Details > title/description parse > ai > None`; conflict cùng tầng trả typed `None`, conflict khác tầng giữ nguồn cao hơn và set review; buyer JSON vẫn là nguồn duy nhất của hammer/sold/date; `ai_json` persist `NULL`.
- T5: pool pricing trong `fetch_lots_for_model`, `fetch_sold_lots_since` và `search_sold_lots` loại lot `needs_review=1 AND review_status='pending'`; không đổi `pricing.py` và không nới `CUTI_MIN_COMPARABLES`.
- T6: thêm 4 fixture Details cố định cùng test parser, identity, 5 tier, conflict, migration v3, zlib và exclusion. Test cũ migration chỉ đổi assertion version literal `3` sang `SCHEMA_VERSION`, không nới điều kiện.

## 5. Phản biện spec, câu hỏi, thứ cần xin duyệt

- Spec định nghĩa input HTML cho parser, nhưng không định nghĩa contract để `settle` lấy hoặc truyền HTML Details vào (`CatawikiApi` hiện chỉ có buyer JSON). Đã dừng ở pure parser và injection vào `_settled_lot` cho test; không tự thêm HTTP client hay request mạng. Cần chốt callback/method hay payload injection trước khi nối production fetch.
- “Đúng một lệnh INSERT” mâu thuẫn với yêu cầu Description ở bảng `lot_desc` riêng. Hiện cả hai INSERT chạy cùng một transaction sau khi resolve hoàn tất, không có update hậu kỳ. Nếu yêu cầu là đúng một SQL statement cho toàn bộ hai bảng, SQLite không thể ghi hai bảng bằng một INSERT thường; cần chốt ý nghĩa chấp nhận được.
- “Mọi file `src/cuti` <= 250 LOC” mâu thuẫn với việc cùng spec nói không gọt ba file cũ vẫn vượt trần. Đã giữ ngoài phạm vi ba file đó; mọi file chạm trong lượt này đạt trần.
- Hash commit tự-tham-chiếu không thể vừa nằm trong nội dung `notion.md` vừa là hash của commit chứa chính file đó. Vì vậy `notion.md` và `NOTION_SANDBOX/PROVENANCE.json` cùng trỏ source commit `2e22736`; commit tài liệu/đóng gói sau đó không thay đổi source behavior. Cần chốt quy ước nếu yêu cầu là hash của commit tài liệu cuối cùng.
