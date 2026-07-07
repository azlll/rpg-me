#!/usr/bin/env python3
"""Render sample carousel cards from the HTML template."""

import base64
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def data_uri(path):
    suffix = Path(path).suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/svg+xml"
    encoded = base64.b64encode(Path(path).read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


def render_card(output_path, portrait_path, data):
    template = (ROOT / "assets" / "card-template.html").read_text(encoding="utf-8")
    template = re.sub(r"<!--.*?-->\s*", "", template, count=1, flags=re.DOTALL)
    history_items = (
        '<a class="history-item is-active" href="#" aria-current="page">'
        f'<span class="history-title">{data["CHAR_NAME"]}</span>'
        f'<span class="history-meta">{data["DATE"]} · {data["SERIAL"]}</span>'
        f'<span class="history-subtitle">{data["TITLE"]}</span>'
        "</a>"
    )
    replacements = {
        **data,
        "PORTRAIT_DATA_URI": data_uri(ROOT / portrait_path),
        "HISTORY_ITEMS": history_items,
    }
    html = template
    for key, value in replacements.items():
        html = html.replace("{{" + key + "}}", str(value))
    output = ROOT / output_path
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")


def main():
    portrait = "output/tongyi-rpg-codex-worker-square.png"
    render_card(
        "output/rpg-card-codex-worker.html",
        portrait,
        {
            "CHAR_NAME": "工位主角 · 未命名",
            "CHAR_CLASS": "牛马系代码召唤师",
            "TITLE": "工位不灭者",
            "CHAR_LV": "37",
            "TAGLINE": "白天上班，晚上改命",
            "STAT_HP": "31",
            "STAT_MP": "82",
            "STAT_EXP": "76",
            "STAT_STRENGTH": "28",
            "STAT_AGILITY": "38",
            "STAT_INTELLIGENCE": "88",
            "STAT_SOCIAL": "46",
            "STAT_CREATIVITY": "82",
            "STAT_SLACK": "63",
            "STAT_EMO": "71",
            "STAT_LUCK": "55",
            "RACE": "打工人类",
            "TRAIT": "睡眠存档",
            "TALENT": "代码召唤",
            "ACTIVE_NAME": "Codex 共鸣编译",
            "ACTIVE_DESC": "冷却时间：一个番茄钟。召唤 AI 队友一起拆 bug，短时间内获得代码推进力 +35%。",
            "PASSIVE_NAME": "牛马不掉线",
            "PASSIVE_DESC": "即使被日常任务消耗，也会在睡一觉后自动重连主线。",
            "QUEST_LIST": "<li>和 Codex 对话，把今天的代码副本推过一个检查点</li><li>按时睡觉，给明天的主角条回满一点蓝</li>",
            "ANALYSIS": "我给你选的是赛博工位 RPG：你现在的状态不是支线 NPC，而是被日常任务压住但还在推进主线的代码召唤师。体力值偏低，因为睡觉是重要回血点；创造力和 emo 抗性保留高位，说明你一边自嘲牛马，一边还能和 Codex 把代码往前推。主角感不靠光环，靠每天上线。",
            "DATE": "2026-07-07",
            "SERIAL": "CODEX-0707",
        },
    )
    render_card(
        "output/rpg-card-codex-worker-share.html",
        portrait,
        {
            "CHAR_NAME": "工位不灭者",
            "CHAR_CLASS": "牛马纪元 · 代码睡眠双修流",
            "TITLE": "带着 debuff 上线的工位主角",
            "CHAR_LV": "404",
            "TAGLINE": "白天上班，晚上改命",
            "STAT_HP": "28",
            "STAT_MP": "82",
            "STAT_EXP": "76",
            "STAT_STRENGTH": "28",
            "STAT_AGILITY": "38",
            "STAT_INTELLIGENCE": "88",
            "STAT_SOCIAL": "38",
            "STAT_CREATIVITY": "88",
            "STAT_SLACK": "76",
            "STAT_EMO": "69",
            "STAT_LUCK": "52",
            "RACE": "打工人类",
            "TRAIT": "睡眠存档",
            "TALENT": "代码召唤",
            "ACTIVE_NAME": "Ctrl+S 改命术",
            "ACTIVE_DESC": "冷却：老板转身的 3 秒。把一团乱需求保存成“至少能跑”，并临时获得主角光环。",
            "PASSIVE_NAME": "睡眠存档点",
            "PASSIVE_DESC": "每次倒下都不是退出游戏，只是把进度存到下一天继续打。",
            "QUEST_LIST": "<li>把今天的 bug 处理成明天可以吹的经验</li><li>睡前从牛马模式切回人类模式</li>",
            "ANALYSIS": "这张卡的核心不是“惨”，是“都这样了还在推进剧情”。你不是工位背景板，而是被系统误投进打工副本的主角。Codex 是临时队友，代码是当前地图，睡觉不是摆烂，是存档点。体力低、社交一般，说明你不是满级外挂；创造力和摸鱼值高，说明你会在现实缝隙里攒蓝条。适合配文：今天也是带着 debuff 上线的主角。",
            "DATE": "2026-07-07",
            "SERIAL": "WORK-404",
        },
    )


if __name__ == "__main__":
    main()
