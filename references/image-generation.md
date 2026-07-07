# 生图方案说明

角色立绘是这张卡的视觉灵魂。由于运行 skill 的 agent 环境各不相同（有的内置文生图工具，有的什么都没有），必须按优先级取图，保证最终 HTML 里是一张真实能显示的图片。

## 目录

1. 优先级总览
2. 方式一：环境内置生图能力
3. 方式二：可配置 API 的脚本
4. 方式三：占位图回退
5. 把图片内嵌进 HTML（关键）
6. 提示词写法
7. 世界观、画风与专属武器

## 1. 优先级总览

| 优先级 | 方式 | 适用场景 |
|--------|------|----------|
| 1 | 调用当前 agent 的生图工具/skill | 环境已配置文生图能力 |
| 2 | 运行 `scripts/generate_portrait.py`，优先检测通义万相 / 阿里云百炼 API | 环境无生图能力，但用户能配置国内第三方 API |
| 3 | 脚本回退到通用文生图 API | 已有 OpenAI 风格 / 智谱 / 自定义 endpoint |
| 4 | 使用 `assets/placeholder-portrait.svg` | 完全无生图能力，先出卡片，提示可后续配置 |

无论哪种方式，最终都要把图片转成 base64 data URI 内嵌进 HTML（见第 5 节）。

## 2. 方式一：环境内置生图能力

先判断当前是否有可用生图工具，常见形式：

- 平台内置文生图工具（如 ImageGen 类工具）。
- 已安装的生图 skill，例如 `autoglm-generate-image`（脚本地址通常在其 skill 目录下，调用后返回 `data.image_url`）。

调用后得到图片文件路径或 URL，进入第 5 节内嵌。

## 3. 方式二：可配置 API 的脚本

当环境没有生图能力时，运行：

```bash
python scripts/generate_portrait.py "<英文提示词>" --out portrait.png
```

脚本先检测通义万相 / 阿里云百炼 API，再检测通用文生图 API。通义万相文档 URL：

```text
https://bailian.console.aliyun.com/cn-beijing?tab=api#/api/?type=model&url=3026980
```

### 3.1 通义万相 / 阿里云百炼（优先）

推荐把 key 和 Workspace ID 放在项目根目录的 `local-image-api.md`，该文件已被 `.gitignore` 排除，也不会被 `scripts/package_skill.py` 打进 `.skill` 包。

```markdown
DASHSCOPE_API_KEY=你的百炼APIKey
DASHSCOPE_WORKSPACE_ID=你的WorkspaceId
DASHSCOPE_REGION=cn-beijing
DASHSCOPE_IMAGE_MODEL=wan2.7-image-pro
DASHSCOPE_IMAGE_SIZE=1080*1080
```

也可以使用环境变量：

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `DASHSCOPE_API_KEY` | 百炼 API Key | 必填 |
| `DASHSCOPE_WORKSPACE_ID` | 百炼 Workspace ID | 必填 |
| `DASHSCOPE_REGION` | 百炼地域 | `cn-beijing` |
| `DASHSCOPE_IMAGE_MODEL` | 通义万相模型 | `wan2.7-image-pro` |
| `DASHSCOPE_IMAGE_SIZE` | 输出尺寸 | `1080*1080` |
| `DASHSCOPE_PROMPT_EXTEND` | 是否开启提示词智能改写 | `true` |
| `DASHSCOPE_WATERMARK` | 是否加水印 | `false` |
| `DASHSCOPE_NEGATIVE_PROMPT` | 负向提示词 | 空 |

脚本请求北京地域时会使用：

```text
https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation
```

鉴权方式为 `Authorization: Bearer <DASHSCOPE_API_KEY>`。密钥只放在本机配置或环境变量中，不能写入 `SKILL.md`、`README.md`、`references/` 或打包产物。

### 3.2 通用文生图 API（回退）

如果没有检测到通义万相配置，脚本再读取以下环境变量（脚本在缺失时会打印指引）：

| 环境变量 | 说明 | 示例 |
|----------|------|------|
| `IMAGE_API_BASE` | 文生图接口地址 | `https://api.openai.com/v1/images/generations` |
| `IMAGE_API_KEY` | API 密钥 | `sk-...` |
| `IMAGE_API_MODEL` | 模型名（可选） | `dall-e-3` / `cogview-3` |
| `IMAGE_API_FORMAT` | 响应格式：`openai` / `zhipu` / `raw_url`（可选，默认 `openai`） | `openai` |

脚本兼容三种常见响应：

- `openai`：`{"data":[{"url": "..."}]}` 或 `{"data":[{"b64_json": "..."}]}`
- `zhipu`（智谱 CogView）：`{"data":[{"url": "..."}]}`
- `raw_url`：响应体直接是图片 URL 或图片二进制

设置示例（Windows PowerShell）：

```powershell
$env:IMAGE_API_BASE="https://open.bigmodel.cn/api/paas/v4/images/generations"
$env:IMAGE_API_KEY="你的key"
$env:IMAGE_API_MODEL="cogview-3-flash"
$env:IMAGE_API_FORMAT="zhipu"
```

设置示例（macOS/Linux）：

```bash
export IMAGE_API_BASE="https://api.openai.com/v1/images/generations"
export IMAGE_API_KEY="sk-..."
export IMAGE_API_MODEL="dall-e-3"
```

脚本会把图片保存到 `--out` 指定路径，并在 stdout 打印保存路径。

## 4. 方式三：占位图回退

若以上方式都不可用，使用 `assets/placeholder-portrait.svg`。这是一张风格中性的剪影占位图，能保证卡片完整。同时必须在给用户的文字里说明：未检测到生图能力，已用占位图，配置 API key 后可重新生成真实立绘。

## 5. 把图片内嵌进 HTML（关键）

不要在 HTML 里用相对路径 `src="portrait.png"`，否则用户移动 HTML 或单独分享时图片会丢失。务必转成 base64 data URI。

生成 data URI：

```bash
python scripts/generate_portrait.py --to-datauri portrait.png
```

或用一行 Python：

```python
import base64, mimetypes, sys
p = sys.argv[1]
mime = mimetypes.guess_type(p)[0] or "image/png"
b64 = base64.b64encode(open(p, "rb").read()).decode()
print(f"data:{mime};base64,{b64}")
```

把结果字符串替换模板里的 `{{PORTRAIT_DATA_URI}}`。

## 6. 提示词写法

结构：`[明亮童话 JRPG 冒险世界] [人物画风] [角色身份/种族感] [服装/装备] [专属武器名称与外观] [姿势] [背景地点] [氛围光] [构图硬约束]`。

立绘槽是 1:1 方形区域，通义万相默认尺寸为 `1080*1080`。提示词必须明确：`square composition, upper-body hero portrait, waist-up or chest-up framing, centered subject, face clearly visible, weapon clearly visible, enough headroom, visible torso and hands, simple fantasy background, no full-body shot, no tiny character, no text, no logo, no watermark`。避免生成整张竖版海报或全身远景，否则放进卡片顶部会丢失人物细节。

原则：人物为主体、背景简洁、画面内无文字。若用户没提供外貌，不要默认东亚人脸，可用剪影、动物拟人、Q 版、机械体等表现，风格与角色世界观一致。

示例：

> Bright whimsical JRPG adventure world, 2D JRPG character card style. A cozy coder-alchemist hero, waist-up portrait, soft adventurer hoodie with tiny rune stitches. Signature weapon: "Saturday Morning Keyboard Staff", a short magical staff shaped like a keyboard handle, topped with a glowing green herb crystal. The character holds the staff diagonally across the body, weapon clearly visible and not blocking the face. Storybook starter town workshop background, warm morning light, square composition, centered subject, face clearly visible, visible torso and hands, enough headroom, simple fantasy background, no full-body shot, no tiny character, no text, no logo, no watermark.

## 7. 世界观、画风与专属武器

### 7.1 固定世界观

背景底座固定为**明亮童话 JRPG 冒险世界**：色彩明亮、轻松、冒险、像勇者小队刚出新手村。不要直接写 Dragon Quest，也不要把画面带到赛博朋克、克系、真实现代都市等世界。现代生活元素要被翻译成奇幻职业、道具、武器、护符、伙伴或装饰。

背景地点从同一世界里选择：新手村广场、草地小山丘、魔法道具店、冒险者酒馆、森林小路、城堡门口、海边港口、云朵神殿、地下迷宫入口、篝火营地。背景只服务人物，不抢主体。

### 7.2 人物画风库

用户可以选择画风；未选择时 agent 默认推荐。画风是参考，不是机械模板，最终仍要由 agent 写成完整英文 prompt。

| 画风 | 英文提示 | 适合场景 |
|------|----------|----------|
| 3D 手办风 | `3D toy-like collectible figurine style` | 可爱、传播感、角色手办 |
| 2D JRPG 风 | `2D anime JRPG character illustration` | 通用、稳定、角色卡 |
| 手绘童话风 | `hand-drawn storybook fantasy illustration` | 温柔、疗愈、生活感 |
| 火柴人勇者风 | `charming stick figure hero style, simple but expressive` | 自嘲、梗图、极简 |
| 拼豆风 | `perler bead pixel craft style` | 玩具感、轻松分享 |
| 方块体素风 | `voxel block character style` | 技术、搭建、系统感；不直接写 Minecraft |
| 像素风 | `retro pixel art RPG portrait style` | 怀旧、升级感、副本感 |
| 黏土小人风 | `warm clay miniature character style` | 家庭感、治愈、温暖 |
| 纸艺剪贴风 | `paper cutout storybook collage style` | 手账感、童话书 |

默认推荐：疲惫/想下班/自嘲时，优先火柴人勇者风、像素风或 Q 版；想变强/赚钱/创造时，优先 2D JRPG 风或 3D 手办风；家庭/疗愈主题，优先手绘童话风、黏土小人风或纸艺剪贴风；技术/系统感强，优先方块体素风或像素风。

### 7.3 专属武器生成规则

每个角色必须有**专属武器**，但武器不是固定清单。不要直接从“职业=某武器”的表里套。先从用户回答中找最有辨识度的生活物件、技能工具、兴趣物、食物、近期梗、主线任务或愿望，再把它 RPG 化。

武器可以不是传统兵器，可以是法器、伙伴、AI 助理、盾牌、召唤物、护符、魔导书、锅铲、咖啡杯、便签本、闹钟、工具箱、调味瓶、植物或存档水晶。

选择优先级：

1. 明确喜欢或常做的事：喜欢炒菜 -> 锅铲、炒锅、调味瓶、围裙盾。
2. 当前工作或技能：程序员 -> AI 助理、代码精灵、调试镜、提交印章、自动补全魔导书。
3. 近期梗、食物或物件：折耳根 -> 怪味护符、绿色灵感草、草本法杖。
4. 当前主线任务：备孕 -> 晨光罗盘、温柔小巢盾、作息沙漏。只用抽象温柔符号，不画医疗或育儿场景。
5. 想要的能力：无限创造力 -> 点子熔炉、造物扳手、灵感魔杖。

最终生成前必须确定：

- 武器来自用户哪条回答。
- 现实原型是什么。
- RPG 化后是什么。
- 它在图里如何露出来。

### 7.4 半身构图与武器露出

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
