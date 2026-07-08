---
name: rpg-me
description: 为用户生成「人生游戏角色卡」轮播组：根据职业、年龄、性别/角色呈现、当前状态、性格和愿望，设计明亮童话 JRPG 风格角色身份、反差社媒梗属性、技能、任务和 1:1 半身立绘，并通过本地 Python 查看器渲染成可下载 PNG 的 HTML 卡片组。用于小红书 REDSkill 等需要强视觉传播与趣味互动的场景。
---

# 人生游戏角色卡

## 工作流程

1. 收集用户信息：默认连续问你 3 个问题，每个问题都有一张选择表；三题答完后再问是否补充性别、年龄、外观等精细信息。
2. 设计角色：名称、称号、职业、Lv、种族感、画风、专属武器、6 项反差属性、RPG 面板、主动/被动技能、当前任务和解析文案。
3. 生成立绘 prompt 并决定图片来源。先始终写出完整英文 prompt；再根据当前宿主 AI 助手是否提供生图能力，让用户选择宿主生成、本地图片路径或先用占位图生成预览卡。不需要 API Key，不读取凭证，不主动请求外网生图服务。
4. 运行 `scripts/history_records.py` 保存记录，脚本会把图片复制到 `output/history/<record-id>/portrait.<ext>`，并生成同级相对路径引用的 `index.html`。
5. 运行或复用 `scripts/viewer_server.py`，给用户本次 viewer 链接和历史入口。

HTML 是结果展示页，不是生成器。不要在页面里加入输入框、生成按钮或二次生成控件。

## UI 风格约定

使用 `ui-ux-pro-max` 的 **Arcade Storybook / Purple JRPG** 方向：深紫游戏外壳 `#1a1028`、紫雾层 `#2d1b4e`、蓝紫行动按钮、暖白卡片、8px 圆角、轻微按压/悬停反馈。卡片是玩具感的 RPG 桌面道具，不做浅粉背景，也不做营销页 hero。

封面 6 个属性固定为两列三行进度条：左到右、上到下展示 `ATTR_WORK_SMELL`、`ATTR_CHILL_BALANCE`、`ATTR_STUBBORN_STAMINA`、`ATTR_SOCIAL_BATTERY`、`ATTR_MEME_BRAIN`、`ATTR_LUCK_DROP`。进度条底层宽度为 100%，上层宽度为真实属性值。

属性条不能全部共用同一条渐变。推荐色系：班味浓度橙棕、松弛余额青绿、嘴硬续航玫红、社交电量天蓝、整活脑洞紫粉、玄学掉落金绿；每个属性都用 CSS 变量 `--bar-start` / `--bar-end` 定义。

## Python 环境检测

启动脚本前先检测本机 Python 入口。按顺序试跑候选命令，选择第一个成功的：

```bash
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)"
python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)"
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)"
```

Windows 上 `python`/`python3` 可能是 Microsoft Store 占位别名，不能只靠 `which` 或 `Get-Command` 判断，必须实际试跑。

## 输入模式

默认提问不要让用户凭空写一段完整人设。不能一次性把三张表都丢给用户；必须按第 1 题、第 2 题、第 3 题逐题推进。开场先说明：

```text
我会连续问你 3 个问题，每个问题都有一张选择表。
你每题只要回一个编号，比如 A2、C4，也可以直接写自己的答案。
答完 3 题后，我再问你要不要补充性别、年龄、外观这些精细信息；也可以跳过。
```

前三题必须逐题发送，用户回答第 1 题后再问第 2 题，回答第 2 题后再问第 3 题。三张 4x4 表必须使用 Markdown 表格格式展示，不允许用列表、代码块或纯文本矩阵替代。

用户每题可以只回编号，也可以用自然语言替代编号；自然语言优先，编号作为辅助灵感。

### 人物设定表

第 1 题：你现在更像哪种人？

用于决定角色职业感、性格、文案语气。

| 你给人的感觉 \ 你主要在忙什么 | A 上班上学 | B 搞钱成长 | C 生活经营 | D 兴趣发电 |
| --- | --- | --- | --- | --- |
| 1 热闹外向 | A1 工位气氛组 | B1 搞钱冲锋队 | C1 家里主理人 | D1 兴趣安利王 |
| 2 稳定靠谱 | A2 进度条守护者 | B2 现金流管家 | C2 日常秩序官 | D2 长期主义玩家 |
| 3 反差有梗 | A3 嘴硬打工王 | B3 野心整活家 | C3 家务吐槽师 | D3 上头收藏家 |
| 4 温柔松弛 | A4 低电量职人 | B4 慢慢变富人 | C4 氛围疗愈师 | D4 快乐自留地 |

### 成长方向表

第 2 题：你最近最想在哪方面升级？

用于决定主线任务、努力方向、想成为什么样的人。

| 你现在离目标的状态 \ 你想变强的方向 | A 更会赚钱 | B 更好看更自信 | C 更自由更松弛 | D 更厉害更有作品 |
| --- | --- | --- | --- | --- |
| 1 刚开始 | A1 搞钱新手村 | B1 变美开荒地 | C1 松弛练习场 | D1 作品起步营 |
| 2 正在冲 | A2 搞钱冲刺副本 | B2 风格进化塔 | C2 自由回血路线 | D2 作品爆肝工坊 |
| 3 卡住了 | A3 钱包迷雾沼泽 | B3 自信卡关镜厅 | C3 逃离内耗关卡 | D3 灵感堵车隧道 |
| 4 快看见成果了 | A4 现金流高光点 | B4 发光自信形态 | C4 松弛通关海岸 | D4 代表作发布台 |

### 能量来源表

第 3 题：什么东西最能给你回血或加 buff？

用于决定专属武器、伙伴、道具和生图 prompt。

| 它在 RPG 里变成什么 \ 能量来自哪里 | A 工作/技能 | B 兴趣/爱好 | C 美食/日常小物 | D 人/宠物/陪伴 |
| --- | --- | --- | --- | --- |
| 1 武器 | A1 自动补全魔导书 | B1 爱好发光法杖 | C1 咖啡回血杖 | D1 陪伴誓约剑 |
| 2 护符 | A2 待办清单护符 | B2 灵感收藏护符 | C2 咖啡回血护符 | D2 安心陪伴护符 |
| 3 伙伴 | A3 AI 小跟班 | B3 兴趣精灵伙伴 | C3 小面包伙伴 | D3 宠物守护兽 |
| 4 召唤物 | A4 分身加班阵 | B4 快乐自留地召唤阵 | C4 火锅治愈阵 | D4 亲友应援召唤阵 |

### 精细信息补充

三题结束后询问：

```text
要不要补充一点基础信息，让角色更贴近你？
A 跳过，让你发挥
B 我来简单描述
C 我只补充外观要求
```

用户选 A 时，默认使用中性友好的奇幻半身英雄呈现；Lv 不用年龄时，按回答里的生活阶段估算。

用户选 B 时，展示这个模板：

```text
职业/身份：
年龄或年龄段：
性别或角色呈现：
外观要求：
不想要的元素：
```

用户选 C 时，只询问外观要求，并提示可以写：短发、戴眼镜、酷一点、可爱一点、不露脸、手办感、不要太幼、不要粉色。

## 角色设计规则

整体世界观固定为**明亮童话 JRPG 冒险世界**：像勇者小队刚出新手村的轻松奇幻冒险，色彩明亮、怪物友好、城镇温暖、有任务感。不要直接写 Dragon Quest，也不要把世界观切到赛博朋克、克系、现代都市等方向。用户的现代生活元素要被翻译成奇幻 RPG 里的职业、道具、武器、护符、伙伴或小装饰。

可选画风：3D 手办风、2D JRPG 风、手绘童话风、火柴人勇者风、拼豆风、方块体素风、像素风、黏土小人风、纸艺剪贴风。用户不选时根据回答推荐，并在解析中说明原因。

### 专属武器

每个角色必须有一件**专属武器**，但武器不是固定清单，也不要按职业模板硬套。先从用户回答中提取 1 个最有辨识度的生活物件、技能工具、兴趣物、食物、职业工具、近期梗、主线任务或愿望，把它 RPG 化为武器、法器、盾牌、伙伴、召唤物、护符或魔导装置。

最终必须说明武器来自哪条用户回答、现实原型是什么、RPG 化后是什么、在图里如何露出来。

## 6 项反差属性

属性值仍为 0-100，并在封面卡以进度条展示：底层长度固定 100，上层长度为真实属性值。

| 字段 | 展示名 | 含义 |
|------|--------|------|
| `ATTR_WORK_SMELL` | 班味浓度 | 工作/责任/现实副本压在身上的程度 |
| `ATTR_CHILL_BALANCE` | 松弛余额 | 休息、放过自己、反内耗的库存 |
| `ATTR_STUBBORN_STAMINA` | 嘴硬续航 | 说没事但还能继续推进主线的能力 |
| `ATTR_SOCIAL_BATTERY` | 社交电量 | 和人连接、回复消息、出门见人的余量 |
| `ATTR_MEME_BRAIN` | 整活脑洞 | 把日常变成梗、表达欲和创造力 |
| `ATTR_LUCK_DROP` | 玄学掉落 | 近期意外收获、巧合和惊喜感 |

避免全属性都高，保留 1-2 个明显短板，角色更真实、更有传播点。短板不做负面评判，用幽默或共情表达。

## RPG 面板数值

力量、敏捷、智力、HP、MP、EXP 不设 100 上限，按 Lv 和 6 项属性计算。Lv 优先使用用户年龄；用户不透露时按职业阶段估算。

年龄段映射要稳定，避免 `80后` 这类输入忽高忽低：`00后` 用 22，`95后` 用 29，`90后` 用 34，`85后` 用 39，`80后` 用 44，`70后` 用 54。用户给出精确年龄时优先使用精确年龄。

```text
STAT_STRENGTH = lv*8 + (100-ATTR_CHILL_BALANCE)*0.6 + ATTR_STUBBORN_STAMINA*0.4
STAT_AGILITY = lv*7 + ATTR_SOCIAL_BATTERY*0.4 + ATTR_CHILL_BALANCE*0.5
STAT_INTELLIGENCE = lv*9 + ATTR_MEME_BRAIN*0.8
STAT_HP = lv*30 + (100-ATTR_WORK_SMELL)*4 + ATTR_STUBBORN_STAMINA*3
STAT_MP = lv*24 + ATTR_MEME_BRAIN*4 + ATTR_CHILL_BALANCE*2
STAT_EXP = lv*lv*42 + ATTR_LUCK_DROP*13
```

结果四舍五入为整数。`scripts/history_records.py` 会按这些公式补齐/覆盖 RPG 面板数值。

## HTML 与历史输出

使用 `scripts/card-template.html` 作为模板；不要手写大段 HTML。图片必须以同级相对路径引用，不要把图片内容写成大块字符串。

推荐流程：

```bash
py -3 scripts/history_records.py --data card-data.json --portrait portrait.png --source-summary "用户输入摘要"
py -3 scripts/viewer_server.py --record <record-id>
```

脚本会创建：

- `output/history/<record-id>/index.html`：轻量结果页，不含图片大字符串。
- `output/history/<record-id>/metadata.json`：本次角色数据，包含 `portraitFile`。
- `output/history/<record-id>/portrait.<ext>`：立绘图片，和 HTML 同级。
- `output/history/index.json`：历史索引，新记录排在最前。
- `output/history/index.html`：历史入口。

`scripts/viewer_server.py` 只绑定 `127.0.0.1`，读取 skill 目录下的 `output`，并通过 `output/.rpg-me-viewer.json` 记录 pid、port、token、startedAt。重复启动时先探活，健康则复用，不健康则清理后重启。可用命令：

```bash
py -3 scripts/viewer_server.py --record <record-id>
py -3 scripts/viewer_server.py --status
py -3 scripts/viewer_server.py --stop
```

可选参数：`--port 8765`、`--idle-timeout 3600`、`--history-root <path>`。

## 生图方案

详见 `references/image-generation.md`。本 skill 不需要 API Key，不读取用户凭证，也不主动请求外网生图服务。

不能可靠判断用户有没有外部生图工具，只判断当前宿主 AI 助手是否有可用生图能力。无论哪种情况，都先生成英文立绘 prompt，并把继续流程说清楚。

宿主 AI 助手支持生图时，给用户三个选项：

- A 直接帮你生成立绘
- B 你去别的生图工具生成，我等你把图片路径发回来
- C 先用占位图生成预览卡

宿主 AI 助手不能生图时，只给用户两个选项：

- A 我去别的生图工具生成，稍后把图片路径发回来
- B 先用占位图生成预览卡

当用户需要去别的工具生图时，先把当前角色数据保存到 `output/pending/<pending-id>/`：`card-data.json` 保存模板字段，`prompt.txt` 保存英文提示词，`source-summary.txt` 保存用户输入摘要。然后输出这段固定引导：

```text
我已经写好你的立绘提示词：

[English prompt]

你可以复制到任意生图工具里。生成后保存图片，再把本地路径发给我，例如：
D:\Downloads\rpg-hero.png

我收到图片路径后，会继续生成角色卡和本地预览链接。
```

用户带图片路径回来后，读取对应 `output/pending/<pending-id>/card-data.json` 和 `source-summary.txt`，运行：

```bash
py -3 scripts/history_records.py --data output/pending/<pending-id>/card-data.json --portrait "用户图片路径" --source-summary "source-summary.txt 里的摘要"
py -3 scripts/viewer_server.py --record <record-id>
```

如果用户选择占位图，使用同一份 pending 数据和 `assets/placeholder-portrait.svg` 先生成预览；之后用户给出真实图片路径时，再用 pending 数据重新保存一条正式记录。

生图提示词必须包含：`square composition, upper-body hero portrait, waist-up or chest-up framing, centered subject, face clearly visible, weapon clearly visible, enough headroom, visible torso and hands, simple fantasy background, no full-body shot, no tiny character, no text, no logo, no watermark`。

## 安全与隐私说明

- 不需要 API Key，不要求用户提供密钥、密码、私钥或云服务凭证。
- 不主动请求外网生图服务；图片由宿主 AI 助手、用户本地文件或内置占位图提供。
- `scripts/viewer_server.py` 只绑定 `127.0.0.1`，用于本地预览和下载卡片，不做公网监听。
- 生成历史会本地写入 `output/history/`，图片以文件形式保存，HTML 使用同级相对路径引用。

## 注意事项

- 不对用户做负面评判，短板属性用幽默或共情方式表达。
- 避免真实疾病、心理诊断、封建迷信等敏感内容。
- 文案要有小红书感：句子短、有画面感、适合截图。
- 未指定风格时自主选择，并在解析中点明为什么选这个风格。
