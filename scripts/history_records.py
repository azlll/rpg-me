#!/usr/bin/env python3
"""Persist RPG card generations and rebuild the local history viewer."""

import argparse
import base64
import json
import mimetypes
import os
import re
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "scripts" / "card-template.html"
VENDOR_ROOT = ROOT / "vendor"
VENDOR_FILES = ("html2canvas.min.js", "html2canvas.LICENSE.txt")
DEFAULT_HISTORY_ROOT = ROOT / "output" / "history"

ATTRIBUTE_KEYS = [
    "ATTR_WORK_SMELL",
    "ATTR_CHILL_BALANCE",
    "ATTR_STUBBORN_STAMINA",
    "ATTR_SOCIAL_BATTERY",
    "ATTR_MEME_BRAIN",
    "ATTR_LUCK_DROP",
]

TEXT_KEYS = [
    "CHAR_NAME",
    "CHAR_CLASS",
    "TITLE",
    "CHAR_LV",
    "TAGLINE",
    *ATTRIBUTE_KEYS,
    "STAT_HP",
    "STAT_MP",
    "STAT_EXP",
    "STAT_STRENGTH",
    "STAT_AGILITY",
    "STAT_INTELLIGENCE",
    "RACE",
    "TRAIT",
    "TALENT",
    "ACTIVE_NAME",
    "ACTIVE_DESC",
    "PASSIVE_NAME",
    "PASSIVE_DESC",
    "QUEST_LIST",
    "ANALYSIS",
]

LEGACY_ATTRIBUTE_MAP = {
    "STAT_HP": "ATTR_WORK_SMELL",
    "STAT_SLACK": "ATTR_CHILL_BALANCE",
    "STAT_EMO": "ATTR_STUBBORN_STAMINA",
    "STAT_SOCIAL": "ATTR_SOCIAL_BATTERY",
    "STAT_CREATIVITY": "ATTR_MEME_BRAIN",
    "STAT_LUCK": "ATTR_LUCK_DROP",
}

CORRUPTED_TEXT_RE = re.compile(r"\?{3,}|\ufffd|[\ue000-\uf8ff]")


def parse_now(now=None):
    if isinstance(now, datetime):
        return now
    if now:
        return datetime.fromisoformat(now)
    return datetime.now()


def serial_from_time(dt):
    return dt.strftime("RPG-%Y%m%d-%H%M%S")


def safe_slug(value):
    slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", str(value)).strip("-").lower()
    return slug[:28] or "card"


def html_escape(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def read_json(path, default):
    path = Path(path)
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path, payload):
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def copy_vendor_assets(output_root):
    vendor_output = Path(output_root) / "vendor"
    vendor_output.mkdir(parents=True, exist_ok=True)
    for filename in VENDOR_FILES:
        source = VENDOR_ROOT / filename
        if not source.is_file():
            raise FileNotFoundError(f"Missing vendor asset: {source}")
        shutil.copyfile(source, vendor_output / filename)
    return vendor_output


def html2canvas_src_for(html_dir, output_root):
    vendor_file = Path(output_root) / "vendor" / "html2canvas.min.js"
    return os.path.relpath(vendor_file, Path(html_dir)).replace(os.sep, "/")


def corrupted_text_fields(card_data, source_summary=""):
    fields = []
    candidates = {"sourceSummary": source_summary}
    candidates.update({key: card_data.get(key, "") for key in TEXT_KEYS})
    for key, value in candidates.items():
        if isinstance(value, str) and CORRUPTED_TEXT_RE.search(value):
            fields.append(key)
    return fields


def reject_corrupted_text(card_data, source_summary=""):
    fields = corrupted_text_fields(card_data, source_summary)
    if not fields:
        return
    preview = ", ".join(fields[:8])
    print(
        "ERROR: card data contains suspicious replacement text; "
        f"check the input file encoding before saving history. Fields: {preview}"
    )
    raise SystemExit(2)


def clamp_attr(value):
    try:
        number = round(float(value))
    except (TypeError, ValueError):
        number = 50
    return max(0, min(100, number))


def parse_level(value):
    try:
        number = round(float(value))
    except (TypeError, ValueError):
        number = 18
    return max(1, number)


def calculate_stats(card_data):
    lv = parse_level(card_data.get("CHAR_LV"))
    work_smell = clamp_attr(card_data.get("ATTR_WORK_SMELL"))
    chill_balance = clamp_attr(card_data.get("ATTR_CHILL_BALANCE"))
    stubborn_stamina = clamp_attr(card_data.get("ATTR_STUBBORN_STAMINA"))
    social_battery = clamp_attr(card_data.get("ATTR_SOCIAL_BATTERY"))
    meme_brain = clamp_attr(card_data.get("ATTR_MEME_BRAIN"))
    luck_drop = clamp_attr(card_data.get("ATTR_LUCK_DROP"))

    return {
        "STAT_STRENGTH": round(lv * 8 + (100 - chill_balance) * 0.6 + stubborn_stamina * 0.4),
        "STAT_AGILITY": round(lv * 7 + social_battery * 0.4 + chill_balance * 0.5),
        "STAT_INTELLIGENCE": round(lv * 9 + meme_brain * 0.8),
        "STAT_HP": round(lv * 30 + (100 - work_smell) * 4 + stubborn_stamina * 3),
        "STAT_MP": round(lv * 24 + meme_brain * 4 + chill_balance * 2),
        "STAT_EXP": round(lv * lv * 42 + luck_drop * 13),
    }


def normalize_card_data(card_data, dt, serial):
    normalized = {}
    for key in TEXT_KEYS:
        if key in ATTRIBUTE_KEYS:
            value = card_data.get(key)
            if value is None:
                legacy_key = next((old for old, new in LEGACY_ATTRIBUTE_MAP.items() if new == key), None)
                value = card_data.get(legacy_key, 50)
            normalized[key] = str(clamp_attr(value))
        else:
            normalized[key] = str(card_data.get(key, ""))

    normalized["CHAR_LV"] = str(parse_level(normalized["CHAR_LV"]))
    normalized["DATE"] = str(card_data.get("DATE") or dt.strftime("%Y-%m-%d"))
    normalized["SERIAL"] = str(card_data.get("SERIAL") or serial)

    for key, value in calculate_stats(normalized).items():
        normalized[key] = str(value)

    return normalized


def make_record_id(dt, serial, card_data):
    base = dt.strftime("%Y%m%d-%H%M%S")
    title = safe_slug(card_data.get("CHAR_NAME") or serial)
    return f"{base}-{title}"


def portrait_filename(source_path):
    suffix = Path(source_path).suffix.lower() or ".png"
    if suffix == ".jpeg":
        suffix = ".jpg"
    return f"portrait{suffix}"


def copy_portrait(portrait_path, record_dir):
    source = Path(portrait_path)
    if not source.is_file():
        print(f"ERROR: portrait image not found: {source}")
        raise SystemExit(2)
    target_name = portrait_filename(source)
    target = Path(record_dir) / target_name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return target_name


def extension_from_mime(mime):
    if mime == "image/svg+xml":
        return ".svg"
    return mimetypes.guess_extension(mime) or ".png"


def migrate_legacy_portrait(record, record_dir):
    if record.get("portraitFile"):
        return record
    data_uri = record.get("portraitDataUri", "")
    if not data_uri.startswith("data:") or ";base64," not in data_uri:
        record["portraitFile"] = "portrait.svg"
        record.pop("portraitDataUri", None)
        return record

    header, encoded = data_uri.split(";base64,", 1)
    mime = header.removeprefix("data:")
    filename = "portrait" + extension_from_mime(mime)
    (Path(record_dir) / filename).write_bytes(base64.b64decode(encoded))
    record["portraitFile"] = filename
    record.pop("portraitDataUri", None)
    return record


def history_item(record, current_id):
    card_data = record["cardData"]
    is_current = record["id"] == current_id
    current_attr = ' aria-current="page"' if is_current else ""
    return (
        f'<a class="history-item{" is-active" if is_current else ""}" '
        f'href="../{html_escape(record["id"])}/index.html" data-history-id="{html_escape(record["id"])}"'
        f'{current_attr}>'
        f'<span class="history-title">{html_escape(card_data.get("CHAR_NAME", "未命名角色"))}</span>'
        f'<span class="history-meta">{html_escape(record.get("date", ""))} · {html_escape(record.get("serial", ""))}</span>'
        f'<span class="history-subtitle">{html_escape(card_data.get("TITLE") or card_data.get("CHAR_CLASS") or "")}</span>'
        "</a>"
    )


def load_records(history_root):
    history_root = Path(history_root)
    index_path = history_root / "index.json"
    index = read_json(index_path, {"records": []})
    records = []
    seen = set()
    for item in index.get("records", []):
        metadata_path = history_root / item["id"] / "metadata.json"
        if metadata_path.is_file():
            record = read_json(metadata_path, {})
            if record.get("id"):
                records.append(record)
                seen.add(record["id"])
    for metadata_path in history_root.glob("*/metadata.json"):
        record = read_json(metadata_path, {})
        if record.get("id") and record["id"] not in seen:
            records.append(record)
            seen.add(record["id"])
    return records


def build_history_items(records, current_id):
    if not records:
        return '<p class="history-empty">暂无生成记录</p>'
    return "\n        ".join(history_item(record, current_id) for record in records)


def render_template(card_data, portrait_file, history_items, html2canvas_src):
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    replacements = {
        **card_data,
        "PORTRAIT_FILE": portrait_file,
        "HISTORY_ITEMS": history_items,
        "HTML2CANVAS_SRC": html2canvas_src,
    }
    html = template
    for key, value in replacements.items():
        html = html.replace("{{" + key + "}}", str(value))
    return html


def write_history_index(history_root, records):
    rows = []
    for record in records:
        card_data = record["cardData"]
        rows.append(
            "      "
            f'<a class="history-index-item" href="{html_escape(record["id"])}/index.html">'
            f'<strong>{html_escape(card_data.get("CHAR_NAME", "未命名角色"))}</strong>'
            f'<span>{html_escape(record.get("date", ""))} · {html_escape(record.get("serial", ""))}</span>'
            f'<em>{html_escape(card_data.get("TITLE") or card_data.get("CHAR_CLASS") or "")}</em>'
            "</a>"
        )
    list_markup = "\n".join(rows) if rows else "      <p>暂无生成记录</p>"
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>人生游戏角色卡 - 生成历史</title>
  <style>
    body {{
      margin: 0;
      min-height: 100dvh;
      padding: 32px 18px;
      font-family: "Trebuchet MS", "PingFang SC", "Microsoft YaHei", sans-serif;
      color: #fffaf0;
      background: #181316;
    }}
    main {{ width: min(760px, 100%); margin: 0 auto; }}
    h1 {{ margin: 0 0 18px; font-size: 28px; letter-spacing: 0; }}
    .history-index-list {{ display: grid; gap: 10px; }}
    .history-index-item {{
      display: grid;
      gap: 5px;
      padding: 14px;
      border-radius: 8px;
      color: inherit;
      text-decoration: none;
      background: rgba(255, 250, 240, 0.1);
      border: 1px solid rgba(255, 250, 240, 0.16);
    }}
    .history-index-item strong {{ font-size: 16px; }}
    .history-index-item span {{ color: rgba(255, 250, 240, 0.72); font-size: 12px; }}
    .history-index-item em {{ color: rgba(255, 250, 240, 0.86); font-style: normal; font-size: 13px; }}
  </style>
</head>
<body>
  <main>
    <h1>生成历史</h1>
    <div class="history-index-list">
{list_markup}
    </div>
  </main>
</body>
</html>
"""
    (Path(history_root) / "index.html").write_text(html, encoding="utf-8")


def rebuild_history_pages(history_root):
    history_root = Path(history_root)
    output_root = history_root.parent
    copy_vendor_assets(output_root)
    records = load_records(history_root)

    normalized_records = []
    for record in records:
        record_dir = history_root / record["id"]
        record = migrate_legacy_portrait(record, record_dir)
        record["cardData"] = normalize_card_data(
            record.get("cardData", {}),
            parse_now(record.get("createdAt")),
            record.get("serial") or serial_from_time(parse_now(record.get("createdAt"))),
        )
        record["serial"] = record["cardData"]["SERIAL"]
        record["date"] = record["cardData"]["DATE"]
        record_dir.mkdir(parents=True, exist_ok=True)
        write_json(record_dir / "metadata.json", record)
        normalized_records.append(record)

    normalized_records.sort(key=lambda item: item.get("createdAt", ""), reverse=True)

    index_records = [
        {
            "id": record["id"],
            "serial": record["serial"],
            "date": record["date"],
            "createdAt": record["createdAt"],
            "charName": record["cardData"].get("CHAR_NAME", ""),
            "title": record["cardData"].get("TITLE", ""),
            "sourceSummary": record.get("sourceSummary", ""),
            "portraitFile": record.get("portraitFile", ""),
            "htmlPath": f"{record['id']}/index.html",
        }
        for record in normalized_records
    ]
    write_json(history_root / "index.json", {"records": index_records})

    for record in normalized_records:
        record_dir = history_root / record["id"]
        history_items = build_history_items(normalized_records, record["id"])
        html = render_template(
            record["cardData"],
            record.get("portraitFile", ""),
            history_items,
            html2canvas_src_for(record_dir, output_root),
        )
        (record_dir / "index.html").write_text(html, encoding="utf-8")

    write_history_index(history_root, normalized_records)


def save_history_record(history_root, card_data, portrait_path, source_summary="", now=None):
    history_root = Path(history_root)
    dt = parse_now(now)
    reject_corrupted_text(card_data, source_summary)
    serial = str(card_data.get("SERIAL") or serial_from_time(dt))
    normalized = normalize_card_data(card_data, dt, serial)
    record_id = make_record_id(dt, serial, normalized)
    record_dir = history_root / record_id

    suffix = 2
    while record_dir.exists():
        record_id = f"{make_record_id(dt, serial, normalized)}-{suffix}"
        record_dir = history_root / record_id
        suffix += 1

    record_dir.mkdir(parents=True, exist_ok=True)
    portrait_file = copy_portrait(portrait_path, record_dir)
    record = {
        "id": record_id,
        "serial": serial,
        "date": normalized["DATE"],
        "createdAt": dt.isoformat(timespec="seconds"),
        "sourceSummary": source_summary,
        "cardData": normalized,
        "portraitFile": portrait_file,
    }

    write_json(record_dir / "metadata.json", record)
    rebuild_history_pages(history_root)

    return {
        "id": record_id,
        "serial": serial,
        "htmlPath": str(record_dir / "index.html"),
        "historyIndexPath": str(history_root / "index.html"),
        "portraitPath": str(record_dir / portrait_file),
    }


def main():
    parser = argparse.ArgumentParser(description="Save one RPG card generation into output/history.")
    parser.add_argument("--data", required=True, help="JSON file containing template replacement fields")
    parser.add_argument("--portrait", required=True, help="Portrait image path")
    parser.add_argument("--history-root", default=str(DEFAULT_HISTORY_ROOT), help="History output directory")
    parser.add_argument("--source-summary", default="", help="Short summary of the user input")
    parser.add_argument("--now", default="", help="ISO datetime override, useful for tests")
    args = parser.parse_args()

    card_data = read_json(args.data, {})
    result = save_history_record(
        args.history_root,
        card_data,
        args.portrait,
        source_summary=args.source_summary,
        now=args.now or None,
    )
    print(f"SAVED: {result['htmlPath']}")
    print(f"HISTORY: {result['historyIndexPath']}")
    print(f"PORTRAIT: {result['portraitPath']}")


if __name__ == "__main__":
    main()
