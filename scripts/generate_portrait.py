#!/usr/bin/env python3
"""
generate_portrait.py — 人生游戏角色卡的稳定生图脚本

当 agent 环境没有内置生图能力时，用它通过通义万相 / 阿里云百炼 API 出图。
保留 --to-datauri 仅用于兼容旧记录或调试；新卡片应把图片作为文件交给
history_records.py，由本地 viewer 用相对路径读取。

用法：
    # 通过配置的 API 生成图片
    python generate_portrait.py "<英文提示词>" --out portrait.png

    # 兼容旧记录：把已有图片转成 data URI（打印到 stdout）
    python generate_portrait.py --to-datauri portrait.png

环境变量（生成图片时需要）：
    RPG_ME_LOCAL_CONFIG     可选，覆盖 local-image-api.md 路径（测试/调试用）

local-image-api.md（生成图片时必须配置）：
    DASHSCOPE_API_KEY       百炼 API Key
    DASHSCOPE_WORKSPACE_ID  百炼 Workspace ID
"""

import sys
import os
import json
import base64
import mimetypes
import argparse
import urllib.request
import urllib.error
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_CONFIG_PATH = ROOT / "local-image-api.md"
DASHSCOPE_SYNC_PATH = "/api/v1/services/aigc/multimodal-generation/generation"
DASHSCOPE_REGION = "cn-beijing"
DASHSCOPE_IMAGE_MODEL = "wan2.7-image-pro"
DASHSCOPE_IMAGE_SIZE = "1080*1080"


def resolve_local_config_path(path=None):
    if path:
        return Path(path)
    return Path(os.environ.get("RPG_ME_LOCAL_CONFIG", LOCAL_CONFIG_PATH))


def load_local_config(path=None):
    """Read KEY=VALUE pairs from a local markdown file without requiring dotenv."""
    config_path = resolve_local_config_path(path)
    if not config_path.is_file():
        return {}

    config = {}
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("```"):
            continue
        line = line.lstrip("-* ").strip()
        if "=" in line:
            key, value = line.split("=", 1)
        elif ":" in line:
            key, value = line.split(":", 1)
        else:
            continue
        key = key.strip().strip("`")
        value = value.strip().strip("`").strip('"').strip("'")
        if key:
            config[key] = value
    return config


def get_config(name, local_config=None, default=""):
    value = os.environ.get(name, "").strip()
    if value:
        return value
    if local_config is None:
        local_config = load_local_config()
    return local_config.get(name, default).strip()


def is_placeholder(value):
    normalized = value.strip().lower()
    return (
        not normalized
        or normalized in ("none", "null", "xxx", "changeme")
        or normalized.startswith("todo")
        or normalized.startswith("fill_")
        or normalized.startswith("replace_")
        or "api_key" in normalized
        or "workspace_id" in normalized
        or "your_" in normalized
        or "你的" in normalized
    )


def to_data_uri(path):
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def dashscope_config_errors(local_config, config_path):
    errors = []
    if not config_path.is_file():
        errors.append(f"未找到配置文件：{config_path}")

    for key in ("DASHSCOPE_API_KEY", "DASHSCOPE_WORKSPACE_ID"):
        value = local_config.get(key, "").strip()
        if is_placeholder(value):
            errors.append(f"{key} 缺失或仍是占位值")

    return errors


def print_config_help(errors=None):
    error_lines = ""
    if errors:
        error_lines = "\n".join(f"  - {item}" for item in errors)
        error_lines = f"\n检测结果：\n{error_lines}\n"

    msg = """
[配置缺失] rpg-me 必须先配置通义万相 / 阿里云百炼生图，当前流程已停止。
{error_lines}
请在项目根目录创建或更新 local-image-api.md，只填写这两项：
  DASHSCOPE_API_KEY=你的百炼APIKey
  DASHSCOPE_WORKSPACE_ID=你的WorkspaceId

以下三项已固定默认，不需要你填写：
  DASHSCOPE_REGION=cn-beijing
  DASHSCOPE_IMAGE_MODEL=wan2.7-image-pro
  DASHSCOPE_IMAGE_SIZE=1080*1080

配置完成后重新运行本脚本。配置文档：
  https://bailian.console.aliyun.com/cn-beijing?tab=api#/api/?type=model&url=3026980
""".format(error_lines=error_lines.rstrip())
    print(msg.strip())


def require_dashscope_config(local_config, config_path):
    errors = dashscope_config_errors(local_config, config_path)
    if errors:
        print_config_help(errors)
        sys.exit(2)


def fetch_bytes(url):
    with urllib.request.urlopen(url, timeout=120) as resp:
        return resp.read()


def dashscope_endpoint(workspace_id, region):
    region = (region or "cn-beijing").strip()
    if region in ("us-east-1", "us-virginia", "dashscope-us"):
        return f"https://dashscope-us.aliyuncs.com{DASHSCOPE_SYNC_PATH}"
    return f"https://{workspace_id}.{region}.maas.aliyuncs.com{DASHSCOPE_SYNC_PATH}"


def parse_bool(value, default=False):
    if value is None or value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "y", "on")


def extract_dashscope_image_url(result):
    output = result.get("output") or {}
    choices = output.get("choices") or []
    for choice in choices:
        message = choice.get("message") or {}
        for item in message.get("content") or []:
            if isinstance(item, dict) and item.get("image"):
                return item["image"]

    for item in output.get("results") or []:
        if isinstance(item, dict) and item.get("url"):
            return item["url"]

    return None


def generate_with_dashscope(prompt, out_path, local_config):
    key = local_config["DASHSCOPE_API_KEY"].strip()
    workspace_id = local_config["DASHSCOPE_WORKSPACE_ID"].strip()
    region = DASHSCOPE_REGION
    model = DASHSCOPE_IMAGE_MODEL
    size = DASHSCOPE_IMAGE_SIZE
    negative_prompt = get_config("DASHSCOPE_NEGATIVE_PROMPT", local_config, "")
    prompt_extend = parse_bool(get_config("DASHSCOPE_PROMPT_EXTEND", local_config, "true"), True)
    watermark = parse_bool(get_config("DASHSCOPE_WATERMARK", local_config, "false"), False)

    payload = {
        "model": model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ]
        },
        "parameters": {
            "prompt_extend": prompt_extend,
            "watermark": watermark,
            "n": 1,
            "negative_prompt": negative_prompt,
            "size": size,
        },
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }
    req = urllib.request.Request(
        dashscope_endpoint(workspace_id, region),
        data=data,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        print(f"ERROR: 通义万相 API 返回错误 {e.code}: {e.read().decode('utf-8', 'ignore')}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: 请求通义万相 API 失败: {e}")
        sys.exit(1)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        print(f"ERROR: 通义万相响应不是 JSON：{raw[:500]}")
        sys.exit(1)

    image_url = extract_dashscope_image_url(result)
    if not image_url:
        print(f"ERROR: 无法从通义万相响应中解析图片 URL：{raw[:500]}")
        sys.exit(1)

    with open(out_path, "wb") as f:
        f.write(fetch_bytes(image_url))
    print(f"SAVED: {out_path}")
    return True


def generate(prompt, out_path):
    config_path = resolve_local_config_path()
    local_config = load_local_config()
    require_dashscope_config(local_config, config_path)
    generate_with_dashscope(prompt, out_path, local_config)


def main():
    parser = argparse.ArgumentParser(description="人生游戏角色卡生图脚本")
    parser.add_argument("prompt", nargs="?", help="英文提示词")
    parser.add_argument("--out", default="portrait.png", help="输出图片路径")
    parser.add_argument("--to-datauri", metavar="IMAGE_PATH",
                        help="兼容旧记录：把指定图片转成 data URI 并打印")
    args = parser.parse_args()

    if args.to_datauri:
        print(to_data_uri(args.to_datauri))
        return

    if not args.prompt:
        parser.error("需要提供提示词，或使用 --to-datauri")

    generate(args.prompt, args.out)


if __name__ == "__main__":
    main()
