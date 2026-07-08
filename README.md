# rpg-me

> 把你此刻的状态，变成一组可晒的人生游戏角色卡。

`rpg-me` 是一个 Agent Skill。它根据用户的职业、年龄、性别/角色呈现、近况、性格和小愿望，生成一组明亮童话 JRPG 风格的「人生游戏角色卡」轮播图。

输出是 4 张 9:16 卡片：封面、角色解析、RPG 面板、技能任务。立绘图片放在每条记录目录里，HTML 用同级相对路径引用，避免把大块图片内容塞进 HTML。

UI 风格按 `ui-ux-pro-max` 的 Arcade Storybook / Purple JRPG 约定：深紫游戏背景、暖白卡片、蓝紫行动按钮、8px 圆角、轻触反馈。封面 6 个属性固定为两列三行进度条，且每个属性使用不同色系。

## 生成内容

- 角色身份：名称、职业、称号、Lv、种族感
- 6 项反差属性：班味浓度、松弛余额、嘴硬续航、社交电量、整活脑洞、玄学掉落
- RPG 面板：力量、敏捷、智力、HP、MP、EXP，不设 100 上限
- 主动技能、被动技能、当前任务
- 1:1 半身英雄立绘
- 角色解析文案

## 低门槛玩法

默认使用 3 轮表格问答。用户不需要自己写完整人设，agent 会连续问 3 个问题，每个问题都有一张 Markdown 4x4 选择表。

前三题分别是人物设定表、成长方向表、能量来源表。每题只要回一个编号，也可以直接写自己的答案。三题答完后，agent 会再问要不要补充性别、年龄、外观这些精细信息，也可以跳过。

示例对话：

```text
第 1 题：A3
第 2 题：D2
第 3 题：A1
精细信息：B
职业/身份：AI Agent 独立开发
年龄或年龄段：80后
性别或角色呈现：男
外观要求：外向技术宅，有 AI 小跟班
不想要的元素：不要太幼、不要粉色
```

## 快速开始

先确认 Python 入口。Windows 常见可用命令是 `py -3`，其他环境可能是 `python3` 或 `python`。

```powershell
py -3 -m unittest tests.smoke_test
py -3 scripts/generate_portrait.py "<英文提示词>" --out portrait.png
py -3 scripts/history_records.py --data card-data.json --portrait portrait.png --source-summary "用户输入摘要"
py -3 scripts/viewer_server.py --record <record-id>
```

`scripts/viewer_server.py` 会输出：

```text
VIEWER: http://127.0.0.1:8765/history/<record-id>/index.html
```

重复启动时会复用已有服务，不会重复开多个。停止服务：

```powershell
py -3 scripts/viewer_server.py --stop
```

查看状态：

```powershell
py -3 scripts/viewer_server.py --status
```

## 输出结构

每次生成都会写入 `output/history/`，不会覆盖上一条结果：

```text
output/history/<record-id>/
  index.html
  metadata.json
  portrait.<ext>
output/history/index.json
output/history/index.html
output/.rpg-me-viewer.json
```

`metadata.json` 包含 `portraitFile`，不包含图片内容。`index.html` 使用同级相对路径引用 `portrait.<ext>`。

## Python 服务

`scripts/viewer_server.py` 只绑定 `127.0.0.1`，只读取当前 skill 的 `output` 目录。它提供：

- `GET /api/health`
- `GET /api/records`
- `GET /api/records/<id>`
- `POST /api/shutdown`

服务状态写入 `output/.rpg-me-viewer.json`，包含 pid、port、token、startedAt。服务支持显式 `--stop`、Ctrl+C/SIGTERM，以及 `--idle-timeout` 空闲超时停止。

## 生图

生成前必须先配置项目根目录的 `local-image-api.md`。缺少文件，或 `DASHSCOPE_API_KEY` / `DASHSCOPE_WORKSPACE_ID` 没有真实值时，脚本会停止，不会继续生成角色卡。

只需要填写两项：

```markdown
DASHSCOPE_API_KEY=你的百炼APIKey
DASHSCOPE_WORKSPACE_ID=你的WorkspaceId
```

以下三项由脚本固定默认：

```text
DASHSCOPE_REGION=cn-beijing
DASHSCOPE_IMAGE_MODEL=wan2.7-image-pro
DASHSCOPE_IMAGE_SIZE=1080*1080
```

配置完成后运行：

```powershell
py -3 scripts/generate_portrait.py "<英文提示词>" --out portrait.png
```

更多说明见 `references/image-generation.md`。

## 打包

```powershell
py -3 scripts/package_skill.py --out dist/rpg-me.skill
```

打包清单是显式维护的，不包含 `local-image-api.md`、`output/` 或本机历史数据。

## 目录

```text
rpg-me/
  SKILL.md
  README.md
  VERSION
  assets/
    placeholder-portrait.svg
    portrait-sample.png
  references/
    image-generation.md
  scripts/
    card-template.html
    generate_portrait.py
    history_records.py
    package_skill.py
    render_sample_cards.py
    viewer_server.py
  tests/
    smoke_test.py
```

## 许可

MIT
