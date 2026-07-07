#!/usr/bin/env python3
"""Persist RPG card generations and rebuild the local history viewer."""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_portrait import to_data_uri


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "assets" / "card-template.html"
DEFAULT_HISTORY_ROOT = ROOT / "output" / "history"

CARD_KEYS = [
    "CHAR_NAME",
    "CHAR_CLASS",
    "TITLE",
    "CHAR_LV",
    "TAGLINE",
    "STAT_HP",
    "STAT_MP",
    "STAT_EXP",
    "STAT_STRENGTH",
    "STAT_AGILITY",
    "STAT_INTELLIGENCE",
    "STAT_SOCIAL",
    "STAT_CREATIVITY",
    "STAT_SLACK",
    "STAT_EMO",
    "STAT_LUCK",
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


def parse_now(now=None):
    if isinstance(now, datetime):
        return now
    if now:
        return datetime.fromisoformat(now)
    return datetime.now()


def serial_from_time(dt):
    return dt.strftime("RPG-%Y%m%d-%H%M%S")


def safe_slug(value):
    slug = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", value).strip("-").lower()
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
    if not Path(path).is_file():
        return default
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, payload):
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def normalize_card_data(card_data, dt, serial):
    normalized = {key: str(card_data.get(key, "")) for key in CARD_KEYS}
    normalized["DATE"] = str(card_data.get("DATE") or dt.strftime("%Y-%m-%d"))
    normalized["SERIAL"] = str(card_data.get("SERIAL") or serial)
    return normalized


def make_record_id(dt, serial, card_data):
    base = dt.strftime("%Y%m%d-%H%M%S")
    title = safe_slug(card_data.get("CHAR_NAME") or serial)
    return f"{base}-{title}"


def history_item(record, current_id):
    card_data = record["cardData"]
    is_current = record["id"] == current_id
    current_attr = ' aria-current="page"' if is_current else ""
    client_record = {
        "id": record["id"],
        "portraitDataUri": record["portraitDataUri"],
        "cardData": card_data,
    }
    card_json = html_escape(json.dumps(client_record, ensure_ascii=False))
    return (
        f'<a class="history-item{" is-active" if is_current else ""}" '
        f'href="../{record["id"]}/index.html" data-history-id="{html_escape(record["id"])}"'
        f' data-card-json="{card_json}"'
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


def render_template(card_data, portrait_data_uri, history_items):
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    replacements = {
        **card_data,
        "PORTRAIT_DATA_URI": portrait_data_uri,
        "HISTORY_ITEMS": history_items,
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
            f'<a class="history-index-item" href="{record["id"]}/index.html">'
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
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      color: #fff8f2;
      background: #151116;
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
      background: rgba(255, 248, 242, 0.1);
      border: 1px solid rgba(255, 248, 242, 0.16);
    }}
    .history-index-item strong {{ font-size: 16px; }}
    .history-index-item span {{ color: rgba(255, 248, 242, 0.72); font-size: 12px; }}
    .history-index-item em {{ color: rgba(255, 248, 242, 0.86); font-style: normal; font-size: 13px; }}
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
    records = load_records(history_root)
    records.sort(key=lambda item: item.get("createdAt", ""), reverse=True)

    index_records = [
        {
            "id": record["id"],
            "serial": record["serial"],
            "date": record["date"],
            "createdAt": record["createdAt"],
            "charName": record["cardData"].get("CHAR_NAME", ""),
            "title": record["cardData"].get("TITLE", ""),
            "sourceSummary": record.get("sourceSummary", ""),
            "htmlPath": f"{record['id']}/index.html",
        }
        for record in records
    ]
    write_json(history_root / "index.json", {"records": index_records})

    for record in records:
        record_dir = history_root / record["id"]
        history_items = build_history_items(records, record["id"])
        html = render_template(record["cardData"], record["portraitDataUri"], history_items)
        record_dir.mkdir(parents=True, exist_ok=True)
        (record_dir / "index.html").write_text(html, encoding="utf-8")

    write_history_index(history_root, records)


def save_history_record(history_root, card_data, portrait_path, source_summary="", now=None):
    history_root = Path(history_root)
    dt = parse_now(now)
    serial = str(card_data.get("SERIAL") or serial_from_time(dt))
    normalized = normalize_card_data(card_data, dt, serial)
    record_id = make_record_id(dt, serial, normalized)
    record_dir = history_root / record_id

    suffix = 2
    while record_dir.exists():
        record_id = f"{make_record_id(dt, serial, normalized)}-{suffix}"
        record_dir = history_root / record_id
        suffix += 1

    portrait_data_uri = to_data_uri(portrait_path)
    record = {
        "id": record_id,
        "serial": serial,
        "date": normalized["DATE"],
        "createdAt": dt.isoformat(timespec="seconds"),
        "sourceSummary": source_summary,
        "cardData": normalized,
        "portraitDataUri": portrait_data_uri,
    }

    record_dir.mkdir(parents=True, exist_ok=True)
    write_json(record_dir / "metadata.json", record)
    rebuild_history_pages(history_root)

    return {
        "id": record_id,
        "serial": serial,
        "htmlPath": str(record_dir / "index.html"),
        "historyIndexPath": str(history_root / "index.html"),
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


if __name__ == "__main__":
    main()
