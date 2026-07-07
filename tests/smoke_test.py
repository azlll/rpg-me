import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import urllib.request
import zipfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def load_generate_portrait():
    module_path = ROOT / "scripts" / "generate_portrait.py"
    spec = importlib.util.spec_from_file_location("generate_portrait", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_history_records():
    module_path = ROOT / "scripts" / "history_records.py"
    spec = importlib.util.spec_from_file_location("history_records", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SmokeTests(unittest.TestCase):
    def test_generate_portrait_can_convert_placeholder_to_data_uri(self):
        module = load_generate_portrait()

        data_uri = module.to_data_uri(ROOT / "assets" / "placeholder-portrait.svg")

        self.assertTrue(data_uri.startswith("data:image/svg+xml;base64,"))
        self.assertIn("PHN2Zy", data_uri)

    def test_generate_portrait_requires_api_configuration_when_generating(self):
        module = load_generate_portrait()
        original_base = os.environ.get("IMAGE_API_BASE")
        original_key = os.environ.get("IMAGE_API_KEY")
        original_dashscope_key = os.environ.get("DASHSCOPE_API_KEY")
        original_dashscope_workspace = os.environ.get("DASHSCOPE_WORKSPACE_ID")
        original_local_config = os.environ.get("RPG_ME_LOCAL_CONFIG")

        try:
            with tempfile.TemporaryDirectory() as tmp:
                out_path = Path(tmp) / "portrait.png"
                os.environ.pop("IMAGE_API_BASE", None)
                os.environ.pop("IMAGE_API_KEY", None)
                os.environ.pop("DASHSCOPE_API_KEY", None)
                os.environ.pop("DASHSCOPE_WORKSPACE_ID", None)
                os.environ["RPG_ME_LOCAL_CONFIG"] = str(Path(tmp) / "missing-local-image-api.md")

                with self.assertRaises(SystemExit) as raised:
                    module.generate("cyber worker portrait", out_path)

                self.assertEqual(2, raised.exception.code)
                self.assertFalse(out_path.exists())
        finally:
            if original_base is None:
                os.environ.pop("IMAGE_API_BASE", None)
            else:
                os.environ["IMAGE_API_BASE"] = original_base
            if original_key is None:
                os.environ.pop("IMAGE_API_KEY", None)
            else:
                os.environ["IMAGE_API_KEY"] = original_key
            if original_dashscope_key is None:
                os.environ.pop("DASHSCOPE_API_KEY", None)
            else:
                os.environ["DASHSCOPE_API_KEY"] = original_dashscope_key
            if original_dashscope_workspace is None:
                os.environ.pop("DASHSCOPE_WORKSPACE_ID", None)
            else:
                os.environ["DASHSCOPE_WORKSPACE_ID"] = original_dashscope_workspace
            if original_local_config is None:
                os.environ.pop("RPG_ME_LOCAL_CONFIG", None)
            else:
                os.environ["RPG_ME_LOCAL_CONFIG"] = original_local_config

    def test_generate_portrait_prefers_dashscope_over_generic_api(self):
        module = load_generate_portrait()
        originals = {
            name: os.environ.get(name)
            for name in (
                "DASHSCOPE_API_KEY",
                "DASHSCOPE_WORKSPACE_ID",
                "DASHSCOPE_REGION",
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
                out_path = Path(tmp) / "portrait.png"
                os.environ["DASHSCOPE_API_KEY"] = "dashscope-key"
                os.environ["DASHSCOPE_WORKSPACE_ID"] = "workspace-123"
                os.environ["DASHSCOPE_REGION"] = "cn-beijing"
                os.environ["DASHSCOPE_IMAGE_SIZE"] = "1080*1080"
                os.environ["IMAGE_API_BASE"] = "https://generic.example/images"
                os.environ["IMAGE_API_KEY"] = "generic-key"
                os.environ.pop("RPG_ME_LOCAL_CONFIG", None)

                with mock.patch.object(module.urllib.request, "urlopen", side_effect=fake_urlopen):
                    module.generate("worker hero", out_path)

                self.assertEqual(b"png-bytes", out_path.read_bytes())
                self.assertEqual(2, len(calls))
                first_request = calls[0]
                self.assertIn(
                    "https://workspace-123.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
                    first_request.full_url,
                )
                self.assertEqual("Bearer dashscope-key", first_request.headers["Authorization"])
        finally:
            for name, value in originals.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_generate_portrait_ignores_placeholder_dashscope_workspace(self):
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
                self.assertEqual("https://generic.example/images", req.full_url)
                return FakeResponse(json.dumps({
                    "data": [{"url": "https://example.test/generic.png"}]
                }).encode("utf-8"))
            self.assertEqual("https://example.test/generic.png", req)
            return FakeResponse(b"generic-png")

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

                with mock.patch.object(module.urllib.request, "urlopen", side_effect=fake_urlopen):
                    module.generate("fallback hero", out_path)

                self.assertEqual(b"generic-png", out_path.read_bytes())
                self.assertEqual(2, len(calls))
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
        template = (ROOT / "assets" / "card-template.html").read_text(encoding="utf-8")

        placeholders = set(re.findall(r"{{([A-Z_]+)}}", template))

        self.assertEqual(
            {
                "CHAR_NAME",
                "CHAR_CLASS",
                "CHAR_LV",
                "TAGLINE",
                "PORTRAIT_DATA_URI",
                "STAT_HP",
                "STAT_SOCIAL",
                "STAT_CREATIVITY",
                "STAT_SLACK",
                "STAT_EMO",
                "STAT_LUCK",
                "STAT_STRENGTH",
                "STAT_AGILITY",
                "STAT_INTELLIGENCE",
                "STAT_MP",
                "STAT_EXP",
                "ACTIVE_NAME",
                "ACTIVE_DESC",
                "PASSIVE_NAME",
                "PASSIVE_DESC",
                "QUEST_LIST",
                "ANALYSIS",
                "RACE",
                "TRAIT",
                "TALENT",
                "TITLE",
                "DATE",
                "SERIAL",
                "HISTORY_ITEMS",
            },
            placeholders,
        )

    def test_card_template_has_responsive_accessible_polish(self):
        template = (ROOT / "assets" / "card-template.html").read_text(encoding="utf-8")

        self.assertIn('class="history-sidebar"', template)
        self.assertIn('aria-label="生成历史"', template)
        self.assertIn('class="history-list"', template)
        self.assertIn('class="deck-stage"', template)
        self.assertIn("width: min(100%, var(--card-width), calc(100vw - 32px));", template)
        self.assertIn("max-width: calc(100vw - 32px);", template)
        self.assertIn("aspect-ratio: 9 / 16;", template)
        self.assertIn("aspect-ratio: 1 / 1;", template)
        self.assertEqual(4, template.count('class="share-card'))
        self.assertIn("download-all", template)
        self.assertIn('data-download-card', template)
        self.assertIn('data-download-all', template)
        self.assertIn('data-busy-text="正在导出..."', template)
        self.assertIn('class="download-status"', template)
        self.assertIn('aria-live="polite"', template)
        self.assertIn('data-card-kind="cover"', template)
        self.assertIn('data-card-kind="analysis"', template)
        self.assertIn('data-card-kind="profile"', template)
        self.assertIn('data-card-kind="skills"', template)
        self.assertEqual(4, template.count('data-filename="rpg-me-0'))
        self.assertIn('class="icon-grid"', template)
        self.assertIn('class="svg-icon"', template)
        self.assertIn('class="skill-panel"', template)
        self.assertIn('class="persona-grid"', template)
        self.assertIn('class="trait-chip"', template)
        self.assertIn("-webkit-line-clamp: 1;", template)
        self.assertIn("-webkit-line-clamp: 4;", template)
        self.assertIn("overflow: hidden;", template)
        self.assertIn("flex-wrap: wrap;", template)
        self.assertIn("@media (max-width: 860px)", template)
        self.assertIn("@media (max-width: 420px)", template)
        self.assertIn("@media (prefers-reduced-motion: reduce)", template)
        self.assertIn('aria-label="下载全部卡片"', template)
        self.assertIn('loading="eager"', template)
        self.assertIn("touch-action: manipulation;", template)
        self.assertNotIn("localStorage", template)
        self.assertNotIn("sessionStorage", template)

    def test_history_records_create_unique_output_and_refresh_sidebar(self):
        module = load_history_records()
        first_data = {
            "CHAR_NAME": "夜班咖啡骑士",
            "CHAR_CLASS": "低电量策士",
            "TITLE": "把困意炼成魔法的人",
            "CHAR_LV": "18",
            "TAGLINE": "先续杯，再通关",
            "STAT_HP": "42",
            "STAT_MP": "76",
            "STAT_EXP": "51",
            "STAT_STRENGTH": "36",
            "STAT_AGILITY": "48",
            "STAT_INTELLIGENCE": "82",
            "STAT_SOCIAL": "39",
            "STAT_CREATIVITY": "78",
            "STAT_SLACK": "65",
            "STAT_EMO": "61",
            "STAT_LUCK": "57",
            "RACE": "夜行人类",
            "TRAIT": "咖啡续航",
            "TALENT": "临门一脚",
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

            index = json.loads((history_root / "index.json").read_text(encoding="utf-8"))
            self.assertEqual([second["id"], first["id"]], [item["id"] for item in index["records"]])
            self.assertEqual("周末地图师", index["records"][0]["charName"])
            self.assertEqual("最近熬夜赶项目，但想周末去看海", index["records"][1]["sourceSummary"])

            first_metadata = json.loads((history_root / first["id"] / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual("夜班咖啡骑士", first_metadata["cardData"]["CHAR_NAME"])
            self.assertTrue(first_metadata["portraitDataUri"].startswith("data:image/svg+xml;base64,"))

            first_html = (history_root / first["id"] / "index.html").read_text(encoding="utf-8")
            second_html = (history_root / second["id"] / "index.html").read_text(encoding="utf-8")
            self.assertIn("夜班咖啡骑士", first_html)
            self.assertIn("周末地图师", first_html)
            self.assertIn('aria-current="page"', first_html)
            self.assertIn("../" + second["id"] + "/index.html", first_html)
            self.assertIn("../" + first["id"] + "/index.html", second_html)
            self.assertNotRegex(second_html, r"{{[A-Z_]+}}")

            history_index = (history_root / "index.html").read_text(encoding="utf-8")
            self.assertIn("生成历史", history_index)
            self.assertIn(second["id"] + "/index.html", history_index)

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
            "output/rpg-card-codex-worker.html",
            "output/rpg-card-codex-worker-share.html",
        ):
            html = (ROOT / rel_path).read_text(encoding="utf-8")
            self.assertNotRegex(html, r"{{[A-Z_]+}}")

    def test_docs_describe_multi_card_carousel_output(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for doc in (skill, readme):
            self.assertIn("4 张", doc)
            self.assertIn("轮播", doc)
            self.assertIn("逐张 PNG", doc)
            self.assertIn("生成历史", doc)
            self.assertIn("output/history", doc)
            self.assertNotIn("进度条", doc)

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

    def test_package_script_includes_install_metadata(self):
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
                self.assertIn("rpg-me/assets/card-template.html", names)
                self.assertIn("rpg-me/scripts/generate_portrait.py", names)
                self.assertIn("rpg-me/scripts/history_records.py", names)
                self.assertNotIn("rpg-me/local-image-api.md", names)

    def test_dist_package_already_contains_install_metadata(self):
        package_path = ROOT / "dist" / "rpg-me.skill"

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

        package_path = ROOT / "dist" / "rpg-me.skill"
        with zipfile.ZipFile(package_path) as archive:
            names = set(archive.namelist())
            self.assertNotIn("rpg-me/local-image-api.md", names)
            for name in names:
                self.assertNotIn(key, archive.read(name))


if __name__ == "__main__":
    unittest.main()
