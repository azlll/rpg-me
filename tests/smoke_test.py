import importlib.util
import io
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, rel_path):
    module_path = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_generate_portrait():
    return load_module("generate_portrait", "scripts/generate_portrait.py")


def load_history_records():
    return load_module("history_records", "scripts/history_records.py")


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class SmokeTests(unittest.TestCase):
    def test_generate_portrait_can_convert_placeholder_to_data_uri(self):
        module = load_generate_portrait()

        data_uri = module.to_data_uri(ROOT / "assets" / "placeholder-portrait.svg")

        self.assertTrue(data_uri.startswith("data:image/svg+xml;base64,"))
        self.assertIn("PHN2Zy", data_uri)

    def test_generate_portrait_requires_api_configuration_when_generating(self):
        module = load_generate_portrait()
        originals = {
            name: os.environ.get(name)
            for name in (
                "IMAGE_API_BASE",
                "IMAGE_API_KEY",
                "DASHSCOPE_API_KEY",
                "DASHSCOPE_WORKSPACE_ID",
                "RPG_ME_LOCAL_CONFIG",
            )
        }

        try:
            with tempfile.TemporaryDirectory() as tmp:
                out_path = Path(tmp) / "portrait.png"
                os.environ.pop("IMAGE_API_BASE", None)
                os.environ.pop("IMAGE_API_KEY", None)
                os.environ.pop("DASHSCOPE_API_KEY", None)
                os.environ.pop("DASHSCOPE_WORKSPACE_ID", None)
                os.environ["RPG_ME_LOCAL_CONFIG"] = str(Path(tmp) / "missing-local-image-api.md")

                with mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
                    with self.assertRaises(SystemExit) as raised:
                        module.generate("cyber worker portrait", out_path)

                self.assertEqual(2, raised.exception.code)
                self.assertFalse(out_path.exists())
                output = stdout.getvalue()
                self.assertIn("local-image-api.md", output)
                self.assertIn("DASHSCOPE_API_KEY", output)
                self.assertIn("DASHSCOPE_WORKSPACE_ID", output)
                self.assertIn("DASHSCOPE_REGION=cn-beijing", output)
                self.assertIn("DASHSCOPE_IMAGE_MODEL=wan2.7-image-pro", output)
                self.assertIn("DASHSCOPE_IMAGE_SIZE=1080*1080", output)
                self.assertNotIn("IMAGE_API_BASE", output)
                self.assertNotIn("placeholder", output.lower())
        finally:
            for name, value in originals.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_generate_portrait_prefers_dashscope_over_generic_api(self):
        module = load_generate_portrait()
        originals = {
            name: os.environ.get(name)
            for name in (
                "DASHSCOPE_API_KEY",
                "DASHSCOPE_WORKSPACE_ID",
                "DASHSCOPE_REGION",
                "DASHSCOPE_IMAGE_MODEL",
                "DASHSCOPE_IMAGE_SIZE",
                "IMAGE_API_BASE",
                "IMAGE_API_KEY",
                "RPG_ME_LOCAL_CONFIG",
            )
        }
        calls = []

        class FakeResponse:
            def __init__(self, body):
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return self.body

        def fake_urlopen(req, timeout=0):
            calls.append(req)
            if isinstance(req, urllib.request.Request):
                payload = json.loads(req.data.decode("utf-8"))
                self.assertEqual("wan2.7-image-pro", payload["model"])
                self.assertEqual("worker hero", payload["input"]["messages"][0]["content"][0]["text"])
                self.assertEqual("1080*1080", payload["parameters"]["size"])
                body = json.dumps({
                    "output": {
                        "choices": [{
                            "message": {
                                "content": [{
                                    "type": "image",
                                    "image": "https://example.test/portrait.png",
                                }]
                            }
                        }],
                        "finished": True,
                    }
                }).encode("utf-8")
                return FakeResponse(body)
            self.assertEqual("https://example.test/portrait.png", req)
            return FakeResponse(b"png-bytes")

        try:
            with tempfile.TemporaryDirectory() as tmp:
                config_path = Path(tmp) / "local-image-api.md"
                config_path.write_text(
                    "\n".join([
                        "DASHSCOPE_API_KEY=local-key",
                        "DASHSCOPE_WORKSPACE_ID=local-workspace",
                    ]),
                    encoding="utf-8",
                )
                out_path = Path(tmp) / "portrait.png"
                os.environ["IMAGE_API_BASE"] = "https://generic.example/images"
                os.environ["IMAGE_API_KEY"] = "generic-key"
                os.environ["RPG_ME_LOCAL_CONFIG"] = str(config_path)
                os.environ.pop("DASHSCOPE_API_KEY", None)
                os.environ.pop("DASHSCOPE_WORKSPACE_ID", None)
                os.environ.pop("DASHSCOPE_REGION", None)
                os.environ.pop("DASHSCOPE_IMAGE_MODEL", None)
                os.environ.pop("DASHSCOPE_IMAGE_SIZE", None)

                with mock.patch.object(module.urllib.request, "urlopen", side_effect=fake_urlopen):
                    module.generate("worker hero", out_path)

                self.assertEqual(b"png-bytes", out_path.read_bytes())
                self.assertEqual(2, len(calls))
                first_request = calls[0]
                self.assertIn(
                    "https://local-workspace.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
                    first_request.full_url,
                )
                self.assertEqual("Bearer local-key", first_request.headers["Authorization"])
        finally:
            for name, value in originals.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_generate_portrait_blocks_placeholder_dashscope_workspace_even_with_generic_api(self):
        module = load_generate_portrait()
        originals = {
            name: os.environ.get(name)
            for name in (
                "IMAGE_API_BASE",
                "IMAGE_API_KEY",
                "IMAGE_API_FORMAT",
                "RPG_ME_LOCAL_CONFIG",
                "DASHSCOPE_API_KEY",
                "DASHSCOPE_WORKSPACE_ID",
            )
        }
        try:
            with tempfile.TemporaryDirectory() as tmp:
                config_path = Path(tmp) / "local-image-api.md"
                config_path.write_text(
                    "\n".join([
                        "DASHSCOPE_API_KEY=local-key",
                        "DASHSCOPE_WORKSPACE_ID=TODO_FILL_WORKSPACE_ID",
                    ]),
                    encoding="utf-8",
                )
                out_path = Path(tmp) / "portrait.png"
                os.environ["RPG_ME_LOCAL_CONFIG"] = str(config_path)
                os.environ["IMAGE_API_BASE"] = "https://generic.example/images"
                os.environ["IMAGE_API_KEY"] = "generic-key"
                os.environ["IMAGE_API_FORMAT"] = "zhipu"
                os.environ.pop("DASHSCOPE_API_KEY", None)
                os.environ.pop("DASHSCOPE_WORKSPACE_ID", None)

                with mock.patch.object(module.urllib.request, "urlopen") as urlopen:
                    with mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
                        with self.assertRaises(SystemExit) as raised:
                            module.generate("fallback hero", out_path)

                self.assertEqual(2, raised.exception.code)
                self.assertFalse(out_path.exists())
                urlopen.assert_not_called()
                output = stdout.getvalue()
                self.assertIn("DASHSCOPE_WORKSPACE_ID", output)
                self.assertIn("local-image-api.md", output)
                self.assertNotIn("IMAGE_API_BASE", output)
        finally:
            for name, value in originals.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_generate_portrait_can_read_dashscope_local_markdown_config(self):
        module = load_generate_portrait()

        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "local-image-api.md"
            config_path.write_text(
                "\n".join([
                    "# local image API",
                    "DASHSCOPE_API_KEY=local-key",
                    "DASHSCOPE_WORKSPACE_ID=local-workspace",
                    "DASHSCOPE_REGION=cn-beijing",
                ]),
                encoding="utf-8",
            )

            config = module.load_local_config(config_path)

        self.assertEqual("local-key", config["DASHSCOPE_API_KEY"])
        self.assertEqual("local-workspace", config["DASHSCOPE_WORKSPACE_ID"])
        self.assertEqual("cn-beijing", config["DASHSCOPE_REGION"])

    def test_card_template_placeholders_stay_complete(self):
        template = (ROOT / "scripts" / "card-template.html").read_text(encoding="utf-8")

        placeholders = set(re.findall(r"{{([A-Z_]+)}}", template))

        self.assertEqual(
            {
                "CHAR_NAME",
                "CHAR_CLASS",
                "CHAR_LV",
                "TAGLINE",
                "PORTRAIT_FILE",
                "STAT_HP",
                "STAT_MP",
                "STAT_EXP",
                "STAT_STRENGTH",
                "STAT_AGILITY",
                "STAT_INTELLIGENCE",
                "ATTR_WORK_SMELL",
                "ATTR_CHILL_BALANCE",
                "ATTR_STUBBORN_STAMINA",
                "ATTR_SOCIAL_BATTERY",
                "ATTR_MEME_BRAIN",
                "ATTR_LUCK_DROP",
                "RACE",
                "TRAIT",
                "TALENT",
                "ACTIVE_NAME",
                "ACTIVE_DESC",
                "PASSIVE_NAME",
                "PASSIVE_DESC",
                "QUEST_LIST",
                "ANALYSIS",
                "TITLE",
                "DATE",
                "SERIAL",
                "HISTORY_ITEMS",
            },
            placeholders,
        )
        self.assertNotIn("PORTRAIT_DATA_URI", template)
        self.assertNotIn("data-card-json", template)
        self.assertNotIn("data:image", template)

    def test_card_template_declares_utf8_before_non_ascii_content(self):
        template = (ROOT / "scripts" / "card-template.html").read_text(encoding="utf-8")
        prefix = '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n  <meta charset="UTF-8" />'

        self.assertTrue(template.startswith(prefix))
        self.assertLess(template.index('<meta charset="UTF-8"'), template.index("人生游戏角色卡"))

    def test_card_template_uses_progress_bars_for_new_attributes(self):
        template = (ROOT / "scripts" / "card-template.html").read_text(encoding="utf-8")

        for label in ("班味浓度", "松弛余额", "嘴硬续航", "社交电量", "整活脑洞", "玄学掉落"):
            self.assertIn(label, template)
        for field in (
            "ATTR_WORK_SMELL",
            "ATTR_CHILL_BALANCE",
            "ATTR_STUBBORN_STAMINA",
            "ATTR_SOCIAL_BATTERY",
            "ATTR_MEME_BRAIN",
            "ATTR_LUCK_DROP",
        ):
            self.assertIn(f'data-progress-field="{field}"', template)
            self.assertIn(f'--value: {{{{{field}}}}}%;', template)
        self.assertIn("ui-ux-pro-max: Arcade Storybook / Purple JRPG", template)
        self.assertIn("--page-bg: #1a1028;", template)
        self.assertIn("--purple-veil: #2d1b4e;", template)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr));", template)
        self.assertIn("grid-template-rows: repeat(3, minmax(0, 1fr));", template)
        for field, start, end in (
            ("ATTR_WORK_SMELL", "#fb923c", "#b45309"),
            ("ATTR_CHILL_BALANCE", "#5eead4", "#0f766e"),
            ("ATTR_STUBBORN_STAMINA", "#fb7185", "#be123c"),
            ("ATTR_SOCIAL_BATTERY", "#7dd3fc", "#2563eb"),
            ("ATTR_MEME_BRAIN", "#c084fc", "#db2777"),
            ("ATTR_LUCK_DROP", "#fde047", "#65a30d"),
        ):
            self.assertIn(f'[data-progress-field="{field}"]', template)
            self.assertIn(f"--bar-start: {start};", template)
            self.assertIn(f"--bar-end: {end};", template)
        for old_label in ("体力值", "社交力", "创造力", "摸鱼值", "emo 抗性", "运气值"):
            self.assertNotIn(old_label, template)

    def test_history_records_create_relative_image_output_without_base64(self):
        module = load_history_records()
        first_data = {
            "CHAR_NAME": "夜班咖啡骑士",
            "CHAR_CLASS": "低电量策士",
            "TITLE": "把困意炼成魔法的人",
            "CHAR_LV": "18",
            "TAGLINE": "先续杯，再通关",
            "ATTR_WORK_SMELL": "72",
            "ATTR_CHILL_BALANCE": "31",
            "ATTR_STUBBORN_STAMINA": "86",
            "ATTR_SOCIAL_BATTERY": "39",
            "ATTR_MEME_BRAIN": "78",
            "ATTR_LUCK_DROP": "57",
            "RACE": "夜行人类",
            "TRAIT": "咖啡续航",
            "TALENT": "临门一脑",
            "ACTIVE_NAME": "浓缩咒语",
            "ACTIVE_DESC": "用一杯咖啡把脑内标签页重新排序。",
            "PASSIVE_NAME": "低电量不掉线",
            "PASSIVE_DESC": "就算电量见底，也能给今天留一个保存点。",
            "QUEST_LIST": "<li>把最难的任务切成一小块</li>",
            "ANALYSIS": "你不是没精神，只是在用省电模式推进主线。",
        }
        second_data = {**first_data, "CHAR_NAME": "周末地图师", "SERIAL": "RPG-20260707-153100"}

        with tempfile.TemporaryDirectory() as tmp:
            history_root = Path(tmp) / "history"
            portrait_path = ROOT / "assets" / "placeholder-portrait.svg"

            first = module.save_history_record(
                history_root,
                first_data,
                portrait_path,
                source_summary="最近熬夜赶项目，但想周末去看海",
                now="2026-07-07T15:30:00",
            )
            second = module.save_history_record(
                history_root,
                second_data,
                portrait_path,
                source_summary="想把周末安排成一张藏宝图",
                now="2026-07-07T15:31:00",
            )

            self.assertNotEqual(first["id"], second["id"])
            self.assertEqual("RPG-20260707-153000", first["serial"])
            self.assertEqual("RPG-20260707-153100", second["serial"])

            index_text = (history_root / "index.json").read_text(encoding="utf-8")
            self.assertNotIn("data:image", index_text)
            self.assertNotIn("base64", index_text)
            self.assertNotIn("portraitDataUri", index_text)
            index = json.loads(index_text)
            self.assertEqual([second["id"], first["id"]], [item["id"] for item in index["records"]])
            self.assertEqual("周末地图师", index["records"][0]["charName"])
            self.assertEqual("最近熬夜赶项目，但想周末去看海", index["records"][1]["sourceSummary"])

            first_metadata_path = history_root / first["id"] / "metadata.json"
            first_metadata_text = first_metadata_path.read_text(encoding="utf-8")
            self.assertNotIn("data:image", first_metadata_text)
            self.assertNotIn("base64", first_metadata_text)
            self.assertNotIn("portraitDataUri", first_metadata_text)
            first_metadata = json.loads(first_metadata_text)
            self.assertEqual("夜班咖啡骑士", first_metadata["cardData"]["CHAR_NAME"])
            self.assertEqual("portrait.svg", first_metadata["portraitFile"])
            self.assertTrue((history_root / first["id"] / "portrait.svg").is_file())

            first_html = (history_root / first["id"] / "index.html").read_text(encoding="utf-8")
            second_html = (history_root / second["id"] / "index.html").read_text(encoding="utf-8")
            self.assertIn('src="portrait.svg"', first_html)
            self.assertIn("夜班咖啡骑士", first_html)
            self.assertIn("周末地图师", first_html)
            self.assertIn('aria-current="page"', first_html)
            self.assertIn("../" + second["id"] + "/index.html", first_html)
            self.assertIn("../" + first["id"] + "/index.html", second_html)
            self.assertNotRegex(second_html, r"{{[A-Z_]+}}")
            self.assertNotIn("data:image", first_html)
            self.assertNotIn("base64", first_html)
            self.assertNotIn("data-card-json", first_html)

    def test_history_records_rejects_question_mark_corrupted_card_data(self):
        module = load_history_records()

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as raised:
                module.save_history_record(
                    Path(tmp) / "history",
                    {
                        "CHAR_NAME": "????????",
                        "CHAR_CLASS": "?????",
                        "TITLE": "???????????",
                        "CHAR_LV": "27",
                        "TAGLINE": "???????????????",
                    },
                    ROOT / "assets" / "placeholder-portrait.svg",
                    source_summary="????????? D3 ???????? A3",
                    now="2026-07-07T15:30:00",
                )

        self.assertEqual(2, raised.exception.code)

    def test_history_records_migrates_legacy_portrait_data_uri(self):
        module = load_history_records()

        with tempfile.TemporaryDirectory() as tmp:
            history_root = Path(tmp) / "history"
            record_dir = history_root / "20260707-153000-legacy"
            record_dir.mkdir(parents=True)
            legacy = {
                "id": "20260707-153000-legacy",
                "serial": "RPG-20260707-153000",
                "date": "2026-07-07",
                "createdAt": "2026-07-07T15:30:00",
                "sourceSummary": "legacy data",
                "portraitDataUri": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciLz4=",
                "cardData": {
                    "CHAR_NAME": "旧卡",
                    "CHAR_CLASS": "旧职业",
                    "TITLE": "旧标题",
                    "CHAR_LV": "27",
                    "TAGLINE": "旧口号",
                    "ATTR_WORK_SMELL": "10",
                    "ATTR_CHILL_BALANCE": "20",
                    "ATTR_STUBBORN_STAMINA": "30",
                    "ATTR_SOCIAL_BATTERY": "40",
                    "ATTR_MEME_BRAIN": "50",
                    "ATTR_LUCK_DROP": "60",
                },
            }
            (record_dir / "metadata.json").write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")
            (history_root / "index.json").write_text(
                json.dumps({"records": [{"id": legacy["id"]}]}, ensure_ascii=False),
                encoding="utf-8",
            )

            module.rebuild_history_pages(history_root)

            migrated_text = (record_dir / "metadata.json").read_text(encoding="utf-8")
            migrated = json.loads(migrated_text)
            self.assertNotIn("portraitDataUri", migrated)
            self.assertEqual("portrait.svg", migrated["portraitFile"])
            self.assertTrue((record_dir / "portrait.svg").is_file())
            self.assertNotIn("base64", migrated_text)

    def test_rpg_stats_are_calculated_from_level_without_100_cap(self):
        module = load_history_records()

        card = module.normalize_card_data(
            {
                "CHAR_LV": "27",
                "ATTR_WORK_SMELL": "72",
                "ATTR_CHILL_BALANCE": "31",
                "ATTR_STUBBORN_STAMINA": "86",
                "ATTR_SOCIAL_BATTERY": "39",
                "ATTR_MEME_BRAIN": "78",
                "ATTR_LUCK_DROP": "57",
            },
            module.parse_now("2026-07-07T15:30:00"),
            "RPG-20260707-153000",
        )

        self.assertEqual("292", card["STAT_STRENGTH"])
        self.assertEqual("220", card["STAT_AGILITY"])
        self.assertEqual("305", card["STAT_INTELLIGENCE"])
        self.assertEqual("1180", card["STAT_HP"])
        self.assertEqual("1022", card["STAT_MP"])
        self.assertEqual("31359", card["STAT_EXP"])

    def test_sample_renderer_replaces_all_template_placeholders(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "render_sample_cards.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual("", result.stderr)
        self.assertEqual(0, result.returncode, result.stdout)
        for rel_path in (
            "output/rpg-card-codex-worker/index.html",
            "output/rpg-card-codex-worker-share/index.html",
        ):
            html = (ROOT / rel_path).read_text(encoding="utf-8")
            self.assertNotRegex(html, r"{{[A-Z_]+}}")
            self.assertNotIn("data:image", html)
            self.assertIn('src="portrait.png"', html)
            self.assertTrue((ROOT / Path(rel_path).parent / "portrait.png").is_file())

    def test_viewer_server_starts_reuses_exposes_apis_and_stops(self):
        module = load_history_records()

        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "output"
            history_root = output_root / "history"
            result = module.save_history_record(
                history_root,
                {
                    "CHAR_NAME": "本地查看器",
                    "CHAR_CLASS": "HTTP 管家",
                    "TITLE": "不重复开服的人",
                    "CHAR_LV": "27",
                    "TAGLINE": "只开一个窗口",
                    "ATTR_WORK_SMELL": "50",
                    "ATTR_CHILL_BALANCE": "50",
                    "ATTR_STUBBORN_STAMINA": "50",
                    "ATTR_SOCIAL_BATTERY": "50",
                    "ATTR_MEME_BRAIN": "50",
                    "ATTR_LUCK_DROP": "50",
                },
                ROOT / "assets" / "placeholder-portrait.svg",
                now="2026-07-07T15:30:00",
            )
            port = find_free_port()

            start_cmd = [
                sys.executable,
                str(ROOT / "scripts" / "viewer_server.py"),
                "--history-root",
                str(history_root),
                "--output-root",
                str(output_root),
                "--port",
                str(port),
                "--idle-timeout",
                "30",
                "--record",
                result["id"],
            ]
            first = subprocess.run(start_cmd, cwd=ROOT, text=True, capture_output=True, timeout=10)
            self.assertEqual(0, first.returncode, first.stderr)
            encoded_id = urllib.parse.quote(result["id"])
            self.assertIn(f"VIEWER: http://127.0.0.1:{port}/history/{encoded_id}/index.html", first.stdout)

            second = subprocess.run(start_cmd, cwd=ROOT, text=True, capture_output=True, timeout=10)
            self.assertEqual(0, second.returncode, second.stderr)
            self.assertIn("REUSED", second.stdout)

            health = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=3).read())
            self.assertEqual("ok", health["status"])
            self.assertEqual(str(history_root.resolve()), health["historyRoot"])

            records = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/records", timeout=3).read())
            self.assertEqual([result["id"]], [item["id"] for item in records["records"]])
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/history/{encoded_id}/index.html", timeout=3) as resp:
                self.assertIn("text/html", resp.headers.get("Content-Type", ""))
                self.assertIn("charset=utf-8", resp.headers.get("Content-Type", "").lower())

            record_api_id = urllib.parse.quote(result["id"])
            record = json.loads(
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/records/{record_api_id}", timeout=3).read()
            )
            self.assertEqual("本地查看器", record["cardData"]["CHAR_NAME"])
            self.assertEqual("portrait.svg", record["portraitFile"])
            self.assertNotIn("portraitDataUri", record)

            stop = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "viewer_server.py"),
                    "--history-root",
                    str(history_root),
                    "--output-root",
                    str(output_root),
                    "--stop",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=10,
            )
            self.assertEqual(0, stop.returncode, stop.stderr)
            self.assertIn("STOPPED", stop.stdout)
            self.assertFalse((output_root / ".rpg-me-viewer.json").exists())

            deadline = time.time() + 5
            while time.time() < deadline:
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.2).read()
                except OSError:
                    break
                time.sleep(0.1)
            else:
                self.fail("viewer server stayed reachable after --stop")

    def test_docs_describe_local_viewer_and_new_inputs(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        image_doc = (ROOT / "references" / "image-generation.md").read_text(encoding="utf-8")

        for doc in (skill, readme, image_doc):
            self.assertIn("同级相对路径", doc)
            self.assertIn("scripts/viewer_server.py", doc)
            self.assertNotIn("base64 内嵌", doc)
            self.assertNotIn("data URI 内嵌", doc)
        for text in ("职业", "年龄", "性别", "班味浓度", "松弛余额", "嘴硬续航"):
            self.assertIn(text, skill)
        self.assertIn("py -3", skill)
        self.assertIn("python3", skill)
        self.assertIn("python", skill)
        self.assertIn("STOP", skill)
        self.assertIn("不允许继续", skill)
        for doc in (skill, readme, image_doc):
            self.assertIn("local-image-api.md", doc)
            self.assertIn("DASHSCOPE_API_KEY", doc)
            self.assertIn("DASHSCOPE_WORKSPACE_ID", doc)
            self.assertNotIn("IMAGE_API_BASE", doc)
            self.assertNotIn("通用文生图 API 回退", doc)
            self.assertNotIn("没有任何 API 时使用", doc)

    def test_docs_describe_three_step_markdown_table_question_flow(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for text in (
            "连续问你 3 个问题",
            "每个问题都有一张选择表",
            "每题只要回一个编号，比如 A2、C4",
            "也可以直接写自己的答案",
            "答完 3 题后",
            "三张 4x4 表必须使用 Markdown 表格格式展示",
            "不能一次性把三张表都丢给用户",
        ):
            self.assertIn(text, skill)
        for table_name in ("人物设定", "成长方向", "能量来源"):
            self.assertIn(f"### {table_name}表", skill)

        for header in (
            "| 你给人的感觉 \\ 你主要在忙什么 | A 上班上学 | B 搞钱成长 | C 生活经营 | D 兴趣发电 |",
            "| 你现在离目标的状态 \\ 你想变强的方向 | A 更会赚钱 | B 更好看更自信 | C 更自由更松弛 | D 更厉害更有作品 |",
            "| 它在 RPG 里变成什么 \\ 能量来自哪里 | A 工作/技能 | B 兴趣/爱好 | C 美食/日常小物 | D 人/宠物/陪伴 |",
        ):
            self.assertIn(header, skill)
            self.assertIn("| --- | --- | --- | --- | --- |", skill)

        for option in (
            "A3 嘴硬打工王",
            "B3 野心整活家",
            "D1 兴趣安利王",
            "A2 搞钱冲刺副本",
            "B4 发光自信形态",
            "C3 逃离内耗关卡",
            "D2 作品爆肝工坊",
            "A1 自动补全魔导书",
            "B3 兴趣精灵伙伴",
            "C2 咖啡回血护符",
            "D3 宠物守护兽",
        ):
            self.assertIn(option, skill)

        for example_part in (
            "第 1 题：A3",
            "第 2 题：D2",
            "第 3 题：A1",
            "精细信息：B",
            "职业/身份：AI Agent 独立开发",
            "年龄或年龄段：80后",
            "性别或角色呈现：男",
            "外观要求：外向技术宅，有 AI 小跟班",
        ):
            self.assertIn(example_part, readme)

        for detail in (
            "A 跳过，让你发挥",
            "B 我来简单描述",
            "C 我只补充外观要求",
            "中性友好的奇幻半身英雄",
            "职业/身份",
            "年龄或年龄段",
            "性别或角色呈现",
            "外观要求",
            "不想要的元素",
            "短发",
            "戴眼镜",
            "酷一点",
            "可爱一点",
            "不露脸",
            "手办感",
            "不要太幼",
            "不要粉色",
        ):
            self.assertIn(detail, skill)

        self.assertNotIn("默认使用一屏角色创建菜单", skill)
        self.assertNotIn("默认使用一屏角色创建菜单", readme)
        self.assertNotIn("### 背景设定表", skill)
        self.assertNotIn("### 武器设定表", skill)
        self.assertNotIn("深度模式固定 5 问", skill)

    def test_image_prompt_docs_describe_adventure_world_styles_and_weapons(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        image_doc = (ROOT / "references" / "image-generation.md").read_text(encoding="utf-8")
        combined = skill + "\n" + image_doc

        for text in (
            "明亮童话 JRPG 冒险世界",
            "半身英雄立绘",
            "专属武器",
            "武器不是固定清单",
            "用户回答",
            "3D 手办风",
            "2D JRPG 风",
            "手绘童话风",
            "火柴人勇者风",
            "拼豆风",
            "方块体素风",
            "像素风",
            "不要直接写 Dragon Quest",
        ):
            self.assertIn(text, combined)

        self.assertIn("weapon clearly visible", image_doc)
        self.assertIn("no full-body shot", image_doc)

    def test_package_script_includes_install_metadata_and_viewer(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "rpg-me.skill"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "package_skill.py"),
                    "--out",
                    str(out_path),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual("", result.stderr)
            self.assertEqual(0, result.returncode, result.stdout)

            self.assertTrue(zipfile.is_zipfile(out_path))
            with zipfile.ZipFile(out_path) as archive:
                names = set(archive.namelist())
                self.assertIn("rpg-me/README.md", names)
                self.assertIn("rpg-me/LICENSE", names)
                self.assertIn("rpg-me/VERSION", names)
                self.assertIn("rpg-me/SKILL.md", names)
                self.assertIn("rpg-me/assets/readme/rpg-me-cover-20260708-120824.jpg", names)
                self.assertIn("rpg-me/assets/readme/rpg-me-cover-20260708-093202.jpg", names)
                self.assertIn("rpg-me/assets/readme/rpg-me-cover-20260708-103138.jpg", names)
                self.assertIn("rpg-me/scripts/card-template.html", names)
                self.assertIn("rpg-me/scripts/viewer_server.py", names)
                self.assertIn("rpg-me/scripts/generate_portrait.py", names)
                self.assertIn("rpg-me/scripts/history_records.py", names)
                self.assertIn("rpg-me/scripts/package_skill.py", names)
                self.assertIn("rpg-me/scripts/render_sample_cards.py", names)
                self.assertNotIn("rpg-me/assets/card-template.html", names)
                self.assertNotIn("rpg-me/local-image-api.md", names)

    def test_dist_package_check_generates_temp_artifact_instead_of_requiring_existing_dist(self):
        with tempfile.TemporaryDirectory() as tmp:
            package_path = Path(tmp) / "dist" / "rpg-me.skill"
            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "package_skill.py"), "--out", str(package_path)],
                cwd=ROOT,
                check=True,
                text=True,
                capture_output=True,
            )

            self.assertTrue(zipfile.is_zipfile(package_path))
            with zipfile.ZipFile(package_path) as archive:
                names = set(archive.namelist())

        self.assertIn("rpg-me/README.md", names)
        self.assertIn("rpg-me/LICENSE", names)
        self.assertIn("rpg-me/VERSION", names)

    def test_dist_package_does_not_include_local_image_config_secret(self):
        module = load_generate_portrait()
        local_config = module.load_local_config(ROOT / "local-image-api.md")
        key = local_config.get("DASHSCOPE_API_KEY", "").encode("utf-8")
        if not key:
            self.skipTest("local-image-api.md has no DASHSCOPE_API_KEY")

        with tempfile.TemporaryDirectory() as tmp:
            package_path = Path(tmp) / "rpg-me.skill"
            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "package_skill.py"), "--out", str(package_path)],
                cwd=ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            with zipfile.ZipFile(package_path) as archive:
                names = set(archive.namelist())
                self.assertNotIn("rpg-me/local-image-api.md", names)
                for name in names:
                    self.assertNotIn(key, archive.read(name))


if __name__ == "__main__":
    unittest.main()
