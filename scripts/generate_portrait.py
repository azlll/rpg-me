#!/usr/bin/env python3
"""
generate_portrait.py — 人生游戏角色卡的稳定生图脚本

当 agent 环境没有内置生图能力时，用它通过第三方文生图 API 出图。
也可以把已有图片转成 base64 data URI 内嵌进 HTML。

用法：
    # 通过配置的 API 生成图片
    python generate_portrait.py "<英文提示词>" --out portrait.png

    # 把已有图片转成 data URI（打印到 stdout）
    python generate_portrait.py --to-datauri portrait.png

环境变量（生成图片时需要）：
    DASHSCOPE_API_KEY       百炼 API Key（优先）
    DASHSCOPE_WORKSPACE_ID  百炼 Workspace ID（优先）
    DASHSCOPE_IMAGE_MODEL   通义万相模型名（可选，默认 wan2.7-image-pro）
    DASHSCOPE_IMAGE_SIZE    输出尺寸（可选，默认 1080*1080）
    IMAGE_API_BASE    文生图接口地址（必填）
    IMAGE_API_KEY     API 密钥（必填）
    IMAGE_API_MODEL   模型名（可选）
    IMAGE_API_FORMAT  响应格式 openai | zhipu | raw_url（可选，默认 openai）
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


def load_local_config(path=None):
    """Read KEY=VALUE pairs from a local markdown file without requiring dotenv."""
    config_path = Path(path) if path else Path(os.environ.get("RPG_ME_LOCAL_CONFIG", LOCAL_CONFIG_PATH))
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
        or normalized.startswith("todo")
        or normalized.startswith("fill_")
        or normalized.startswith("replace_")
        or "workspace_id" in normalized
        or "your_" in normalized
        or "你的" in normalized
    )


def to_data_uri(path):
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def print_config_help():
    msg = """
[配置缺失] 当前环境未检测到可用生图 API。

优先推荐配置通义万相 / 阿里云百炼（不会把 key 打包进 skill）：
  1. 在项目根目录创建 local-image-api.md
  2. 写入：
     DASHSCOPE_API_KEY=你的百炼APIKey
     DASHSCOPE_WORKSPACE_ID=你的WorkspaceId
     DASHSCOPE_REGION=cn-beijing
  文档：
     https://bailian.console.aliyun.com/cn-beijing?tab=api#/api/?type=model&url=3026980

也可以使用环境变量：
  DASHSCOPE_API_KEY       百炼 API Key
  DASHSCOPE_WORKSPACE_ID  百炼 Workspace ID
  DASHSCOPE_IMAGE_MODEL   可选，默认 wan2.7-image-pro
  DASHSCOPE_IMAGE_SIZE    可选，默认 1080*1080

若不使用通义万相，请设置以下通用 API 环境变量后重试：

  IMAGE_API_BASE   文生图接口地址（必填）
  IMAGE_API_KEY    API 密钥（必填）
  IMAGE_API_MODEL  模型名（可选）
  IMAGE_API_FORMAT 响应格式 openai | zhipu | raw_url（可选，默认 openai）

示例（智谱 CogView，Windows PowerShell）：
  $env:IMAGE_API_BASE="https://open.bigmodel.cn/api/paas/v4/images/generations"
  $env:IMAGE_API_KEY="你的key"
  $env:IMAGE_API_MODEL="cogview-3-flash"
  $env:IMAGE_API_FORMAT="zhipu"

示例（OpenAI 兼容，macOS/Linux）：
  export IMAGE_API_BASE="https://api.openai.com/v1/images/generations"
  export IMAGE_API_KEY="sk-..."
  export IMAGE_API_MODEL="dall-e-3"

配置完成后重新运行本脚本即可。若暂时不想配置，skill 会自动使用占位图。
"""
    print(msg.strip())


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
    key = get_config("DASHSCOPE_API_KEY", local_config)
    workspace_id = get_config("DASHSCOPE_WORKSPACE_ID", local_config)
    if is_placeholder(key) or is_placeholder(workspace_id):
        return False

    region = get_config("DASHSCOPE_REGION", local_config, "cn-beijing")
    model = get_config("DASHSCOPE_IMAGE_MODEL", local_config, "wan2.7-image-pro")
    size = get_config("DASHSCOPE_IMAGE_SIZE", local_config, "1080*1080")
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
    local_config = load_local_config()
    if generate_with_dashscope(prompt, out_path, local_config):
        return

    base = os.environ.get("IMAGE_API_BASE", "").strip()
    key = os.environ.get("IMAGE_API_KEY", "").strip()
    model = os.environ.get("IMAGE_API_MODEL", "").strip()
    fmt = os.environ.get("IMAGE_API_FORMAT", "openai").strip().lower()

    if not base or not key:
        print_config_help()
        sys.exit(2)

    payload = {"prompt": prompt}
    if model:
        payload["model"] = model
    # OpenAI 风格默认请求 b64，减少二次下载
    if fmt == "openai":
        payload["response_format"] = "b64_json"
        payload["n"] = 1
        payload["size"] = "1024x1792"

    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }

    req = urllib.request.Request(base, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        print(f"ERROR: 生图 API 返回错误 {e.code}: {e.read().decode('utf-8', 'ignore')}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: 请求生图 API 失败: {e}")
        sys.exit(1)

    img_bytes = None

    if fmt == "raw_url":
        url = raw.strip().strip('"')
        img_bytes = fetch_bytes(url)
    else:
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            # 也许直接返回了 URL
            img_bytes = fetch_bytes(raw.strip().strip('"'))
            result = None

        if img_bytes is None:
            items = result.get("data") or result.get("images") or []
            if not items:
                print(f"ERROR: 无法从响应中解析图片：{raw[:500]}")
                sys.exit(1)
            first = items[0]
            if isinstance(first, dict):
                if first.get("b64_json"):
                    img_bytes = base64.b64decode(first["b64_json"])
                elif first.get("url"):
                    img_bytes = fetch_bytes(first["url"])
            elif isinstance(first, str):
                if first.startswith("http"):
                    img_bytes = fetch_bytes(first)
                else:
                    img_bytes = base64.b64decode(first)

    if not img_bytes:
        print(f"ERROR: 未能获得图片数据：{raw[:500]}")
        sys.exit(1)

    with open(out_path, "wb") as f:
        f.write(img_bytes)
    print(f"SAVED: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="人生游戏角色卡生图脚本")
    parser.add_argument("prompt", nargs="?", help="英文提示词")
    parser.add_argument("--out", default="portrait.png", help="输出图片路径")
    parser.add_argument("--to-datauri", metavar="IMAGE_PATH",
                        help="把指定图片转成 base64 data URI 并打印")
    args = parser.parse_args()

    if args.to_datauri:
        print(to_data_uri(args.to_datauri))
        return

    if not args.prompt:
        parser.error("需要提供提示词，或使用 --to-datauri")

    generate(args.prompt, args.out)


if __name__ == "__main__":
    main()
