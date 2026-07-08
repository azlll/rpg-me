#!/usr/bin/env python3
"""Render sample carousel cards from the HTML template."""

import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "scripts" / "card-template.html"


def render_card(output_dir, portrait_path, data):
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    history_items = (
        '<a class="history-item is-active" href="#" aria-current="page">'
        f'<span class="history-title">{data["CHAR_NAME"]}</span>'
        f'<span class="history-meta">{data["DATE"]} · {data["SERIAL"]}</span>'
        f'<span class="history-subtitle">{data["TITLE"]}</span>'
        "</a>"
    )
    output = ROOT / output_dir
    output.mkdir(parents=True, exist_ok=True)
    portrait_target = output / "portrait.png"
    shutil.copyfile(ROOT / portrait_path, portrait_target)
    replacements = {
        **data,
        "PORTRAIT_FILE": "portrait.png",
        "HISTORY_ITEMS": history_items,
    }
    html = template
    for key, value in replacements.items():
        html = html.replace("{{" + key + "}}", str(value))
    html = re.sub(r"<!--.*?-->\s*", "", html, count=1, flags=re.DOTALL)
    (output / "index.html").write_text(html, encoding="utf-8")


def base_data():
    return {
        "CHAR_NAME": "工位主角 · 未命名",
        "CHAR_CLASS": "牛马系代码召唤师",
        "TITLE": "工位不灭者",
        "CHAR_LV": "37",
        "TAGLINE": "白天上班，晚上改命",
        "ATTR_WORK_SMELL": "82",
        "ATTR_CHILL_BALANCE": "31",
        "ATTR_STUBBORN_STAMINA": "76",
        "ATTR_SOCIAL_BATTERY": "46",
        "ATTR_MEME_BRAIN": "88",
        "ATTR_LUCK_DROP": "55",
        "STAT_HP": "1538",
        "STAT_MP": "1302",
        "STAT_EXP": "58243",
        "STAT_STRENGTH": "368",
        "STAT_AGILITY": "292",
        "STAT_INTELLIGENCE": "403",
        "RACE": "打工人类",
        "TRAIT": "睡眠存档",
        "TALENT": "代码召唤",
        "ACTIVE_NAME": "Codex 共鸣编译",
        "ACTIVE_DESC": "冷却时间：一个番茄钟。召唤 AI 队友一起拆 bug，短时间内获得代码推进力 +35%。",
        "PASSIVE_NAME": "牛马不掉线",
        "PASSIVE_DESC": "即使被日常任务消耗，也会在睡一觉后自动重连主线。",
        "QUEST_LIST": "<li>和 Codex 对话，把今天的代码副本推进过一个检查点</li><li>按时睡觉，给明天的主角条回满一点蓝</li>",
        "ANALYSIS": "我给你选的是打工冒险 RPG：你现在不是支线 NPC，而是被日常任务压住但还在推进主线的代码召唤师。班味浓度偏高，说明副本开得太满；整活脑洞和嘴硬续航保留高位，说明你一边自嘲牛马，一边还能和 Codex 把代码往前推。主角感不靠光环，靠每天上线。",
        "DATE": "2026-07-07",
        "SERIAL": "CODEX-0707",
    }


def main():
    portrait = "assets/portrait-sample.png"
    render_card("output/rpg-card-codex-worker", portrait, base_data())
    render_card(
        "output/rpg-card-codex-worker-share",
        portrait,
        {
            **base_data(),
            "CHAR_NAME": "工位不灭者",
            "CHAR_CLASS": "牛马纪元 · 代码睡眠双修流",
            "TITLE": "带着 debuff 上线的工位主角",
            "CHAR_LV": "404",
            "TAGLINE": "今天也是带着 debuff 上线的主角",
            "ATTR_WORK_SMELL": "91",
            "ATTR_CHILL_BALANCE": "24",
            "ATTR_STUBBORN_STAMINA": "89",
            "ATTR_SOCIAL_BATTERY": "38",
            "ATTR_MEME_BRAIN": "92",
            "ATTR_LUCK_DROP": "52",
            "STAT_HP": "12567",
            "STAT_MP": "10104",
            "STAT_EXP": "6857620",
            "STAT_STRENGTH": "3306",
            "STAT_AGILITY": "2856",
            "STAT_INTELLIGENCE": "3710",
            "ACTIVE_NAME": "Ctrl+S 改命术",
            "ACTIVE_DESC": "冷却：老板转身的 3 秒。把一团乱需求保存成“至少能跑”，并临时获得主角光环。",
            "PASSIVE_NAME": "睡眠存档点",
            "PASSIVE_DESC": "每次倒下都不是退出游戏，只是把进度存到下一天继续打。",
            "QUEST_LIST": "<li>把今天的 bug 处理成明天可以吹的经验</li><li>睡前从牛马模式切回人类模式</li>",
            "ANALYSIS": "这张卡的核心不是“惨”，是“都这样了还在推进剧情”。你不是工位背景板，而是被系统误投进打工副本的主角。班味很浓，松弛余额偏低，但整活脑洞和嘴硬续航很高，适合配文：今天也是带着 debuff 上线的主角。",
            "SERIAL": "WORK-404",
        },
    )


if __name__ == "__main__":
    main()
