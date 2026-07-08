# 生图方案说明

角色立绘是卡片的视觉核心。新架构下，图片始终作为文件保存到记录目录，HTML 只使用同级相对路径引用图片，再通过 `scripts/viewer_server.py` 本地查看；不要把图片内容写进 HTML。

## 立绘来源

本 skill 不需要 API Key，不读取用户凭证，也不主动请求外网生图服务。

不能可靠判断用户有没有外部生图工具，只判断当前宿主 AI 助手是否有可用生图能力。角色设定完成后，先始终生成完整英文 prompt，再决定图片来源。

宿主 AI 助手支持生图时，给用户三个选项：

- A 直接帮你生成立绘
- B 你去别的生图工具生成，我等你把图片路径发回来
- C 先用占位图生成预览卡

宿主 AI 助手不能生图时，只给用户两个选项：

- A 我去别的生图工具生成，稍后把图片路径发回来
- B 先用占位图生成预览卡

如果用户选择去别的工具生图，先保存 `output/pending/<pending-id>/card-data.json`、`output/pending/<pending-id>/prompt.txt`、`output/pending/<pending-id>/source-summary.txt`，再输出：

```text
我已经写好你的立绘提示词：

[English prompt]

你可以复制到任意生图工具里。生成后保存图片，再把本地路径发给我，例如：
D:\Downloads\rpg-hero.png

我收到图片路径后，会继续生成角色卡和本地预览链接。
```

用户带图片路径回来后，读取 pending 目录里的 `card-data.json` 和 `source-summary.txt`，把图片文件传给 `scripts/history_records.py`。脚本会复制到 `output/history/<record-id>/portrait.<ext>`，并让 `index.html` 用同级相对路径引用。

如果用户暂时不提供图片，使用 `assets/placeholder-portrait.svg` 和同一份 pending 数据先生成可预览卡片；之后可替换真实立绘重新保存。

## 保存与查看

保存记录时不要手动改 HTML。统一运行：

```bash
python scripts/history_records.py --data card-data.json --portrait portrait.png --source-summary "用户输入摘要"
python scripts/viewer_server.py --record <record-id>
```

输出结构：

```text
output/history/<record-id>/
  index.html
  metadata.json
  portrait.<ext>
```

`metadata.json` 只记录 `portraitFile`。`index.html` 引用同级相对路径，例如 `src="portrait.png"`。历史列表和本次记录由本地 Python 查看器读取 `output/history` 提供，不在 HTML 内塞完整历史数据。

## 提示词写法

结构：`[明亮童话 JRPG 冒险世界] [人物画风] [角色身份/种族感] [服装/装备] [专属武器名称与外观] [姿势] [背景地点] [氛围光] [构图硬约束]`。

立绘槽是 1:1 方形区域。提示词必须明确：`square composition, upper-body hero portrait, waist-up or chest-up framing, centered subject, face clearly visible, weapon clearly visible, enough headroom, visible torso and hands, simple fantasy background, no full-body shot, no tiny character, no text, no logo, no watermark`。

原则：人物为主体、背景简洁、画面内无文字。若用户没有提供外貌，不要默认东亚人脸，可用剪影、动物拟人、Q 版、机械体等表现，风格与角色世界观一致。

示例：

> Bright whimsical JRPG adventure world, 2D JRPG character card style. A cozy coder-alchemist hero, waist-up portrait, soft adventurer hoodie with tiny rune stitches. Signature weapon: "Saturday Morning Keyboard Staff", a short magical staff shaped like a keyboard handle, topped with a glowing green herb crystal. The character holds the staff diagonally across the body, weapon clearly visible and not blocking the face. Storybook starter town workshop background, warm morning light, square composition, centered subject, face clearly visible, visible torso and hands, enough headroom, simple fantasy background, no full-body shot, no tiny character, no text, no logo, no watermark.

## 世界观、画风与武器

背景底座固定为**明亮童话 JRPG 冒险世界**：色彩明亮、轻松、冒险，像勇者小队刚出新手村。不要直接写 Dragon Quest，也不要把画面带到赛博朋克、克系、真实现代都市等世界。现代生活元素要被翻译成奇幻职业、道具、武器、护符、伙伴或装饰。

画风可从这些方向选择，未指定时由 agent 根据用户回答推荐：

| 画风 | 英文提示 | 适合场景 |
| --- | --- | --- |
| 3D 手办风 | `3D toy-like collectible figurine style` | 可爱、传播感、角色手办 |
| 2D JRPG 风 | `2D anime JRPG character illustration` | 通用、稳定、角色卡 |
| 手绘童话风 | `hand-drawn storybook fantasy illustration` | 温柔、疗愈、生活感 |
| 火柴人勇者风 | `charming stick figure hero style, simple but expressive` | 自嘲、梗图、极简 |
| 拼豆风 | `perler bead pixel craft style` | 玩具感、轻松分享 |
| 方块体素风 | `voxel block character style` | 技术、搭建、系统感；不直接写 Minecraft |
| 像素风 | `retro pixel art RPG portrait style` | 怀旧、升级感、副本感 |
| 黏土小人风 | `warm clay miniature character style` | 家庭感、治愈、温暖 |
| 纸艺剪贴风 | `paper cutout storybook collage style` | 手账感、童话书 |

每个角色必须有**专属武器**，但武器不是固定清单。不要直接从“职业 -> 某武器”的表里套。先从用户回答中找最有辨识度的生活物件、技能工具、兴趣物、食物、近期梗、主线任务或愿望，再把它 RPG 化。

武器可以不是传统兵器，可以是法器、伙伴、AI 助理、图牌、召唤物、护符、魔导书、锅铲、咖啡杯、便签本、闹钟、工具箱、调味瓶、植物或存档水晶。

最终生成前必须确定：

1. 武器来自用户哪条回答。
2. 现实原型是什么。
3. RPG 化后是什么。
4. 它在图里如何露出来。

封面图必须是**半身英雄立绘**，不是全身小人。武器必须露出来，并且不遮挡脸。根据武器类型选择一种露出方式：

- 手持型：`holding the signature weapon diagonally across the body`
- 肩扛型：`resting the signature weapon on one shoulder`
- 前景展示型：`signature weapon visible in the foreground near the lower corner`
- 漂浮伙伴型：`signature weapon or companion floating beside the character with magical glow`

每个最终 prompt 都要包含：

```text
Signature weapon: [weapon name], [short visual description].
The weapon is clearly visible and readable as the character's main weapon.
```
