# rpg-me

把一句“最近的状态”变成一套可晒、可下载、可回看的 **人生游戏 RPG 角色卡**。

`rpg-me` 是一个 Agent Skill：它会用低门槛的三轮选择题收集信息，把用户的职业感、生活状态、成长方向和回血来源，翻译成明亮童话 JRPG 风格的角色设定、立绘、属性面板、技能和任务卡。

<p align="center">
  <img src="assets/readme/rpg-me-cover-20260708-120824.jpg" width="31%" alt="快乐自留地召唤师角色卡封面" />
  <img src="assets/readme/rpg-me-cover-20260708-093202.jpg" width="31%" alt="AI Agent 角色卡封面" />
  <img src="assets/readme/rpg-me-cover-20260708-103138.jpg" width="31%" alt="户外工程师角色卡封面" />
</p>

## 它能生成什么

- 4 张 9:16 分享卡：封面、角色解析、RPG 面板、技能任务。
- 1 张 1:1 角色立绘：优先使用宿主 AI 助手自带生图能力；不能生图时输出 prompt 或使用用户提供的本地图片。
- 6 个反差属性：班味浓度、松弛余额、嘴硬续航、社交电量、整活脑洞、玄学掉落。
- 不设 100 上限的 RPG 数值：力量、敏捷、智力、HP、MP、EXP。
- 本地历史查看器：每次生成都会保存到 `output/history/`，可以用浏览器回看和下载 PNG。

## 为什么好玩

很多“AI 头像生成器”只会问你一大段设定。`rpg-me` 反过来做：先让用户在三张 Markdown 表格里选编号，不用组织长文，也能生成有梗、有反差、适合小红书轮播的角色卡。

默认流程是：

1. 你现在更像哪种人？
2. 你最近最想在哪方面升级？
3. 什么东西最能给你回血或加 buff？

三题答完后，用户可以选择跳过精细信息，也可以补充职业、年龄、性别呈现、外观要求和不想要的元素。

示例回复：

```text
第 1 题：A3
第 2 题：D2
第 3 题：A1
精细信息：B
职业/身份：AI Agent 独立开发
年龄或年龄段：80后
性别或角色呈现：男
外观要求：外向技术宅，有 AI 小跟班
不想要的元素：不要真实疾病/心理诊断
```

## 环境要求

- Python：必须有本机 Python 环境。
- 推荐版本：Python 3.10 或更高；脚本最低要求 Python 3.8。
- Windows 推荐使用 `py -3`，其他环境通常是 `python3` 或 `python`。
- 生图：不需要 API Key。Skill 不读取密钥、密码、私钥或云服务凭证，也不主动请求外网生图服务。
- 立绘来源：优先使用宿主 AI 助手生成；如果当前环境不能生图，Skill 会输出可复制 prompt，让用户提供本地图片路径；也可以先用内置占位图预览。

检查 Python：

```powershell
py -3 -c "import sys; print(sys.version)"
```

如果你的电脑没有 `py -3`，可以试：

```bash
python3 -c "import sys; print(sys.version)"
python -c "import sys; print(sys.version)"
```

## 立绘来源

`rpg-me` 本身不接入第三方生图 API，不需要 API Key。它不能可靠判断用户有没有外部生图工具，只会根据当前宿主 AI 助手是否有可用生图能力分流。

角色设定完成后，Skill 会先写出完整英文立绘 prompt。宿主 AI 助手支持生图时，可以直接生成；不支持时，用户体验会变成两个明确选项：

- A 我去别的生图工具生成，稍后把图片路径发回来
- B 先用占位图生成预览卡

如果用户选择去别的工具生图，Skill 会把当前进度保存到 `output/pending/<pending-id>/`，其中 `card-data.json` 是角色卡字段，`prompt.txt` 是英文提示词，`source-summary.txt` 是用户输入摘要。然后给出固定引导：

```text
我已经写好你的立绘提示词：

[English prompt]

你可以复制到任意生图工具里。生成后保存图片，再把本地路径发给我，例如：
D:\Downloads\rpg-hero.png

我收到图片路径后，会继续生成角色卡和本地预览链接。
```

如果用户暂时没有图片，使用 `assets/placeholder-portrait.svg` 先生成可预览卡片；之后可用真实立绘路径重新保存一条正式记录。

## 快速开始

运行测试确认环境：

```powershell
py -3 -m unittest tests.smoke_test
```

准备立绘。如果宿主 AI 助手支持生图，按 `references/image-generation.md` 里的 prompt 规范生成图片；如果不能生图，可先用内置占位图生成预览卡：

```powershell
Copy-Item assets/placeholder-portrait.svg portrait.svg
```

保存一条角色卡记录：

```powershell
py -3 scripts/history_records.py --data card-data.json --portrait portrait.svg --source-summary "用户输入摘要"
```

启动本地查看器：

```powershell
py -3 scripts/viewer_server.py --record <record-id>
```

脚本会输出：

```text
VIEWER: http://127.0.0.1:8765/history/<record-id>/index.html
```

重复启动时会复用已有服务，不会重复开多个 viewer。停止服务：

```powershell
py -3 scripts/viewer_server.py --stop
```

查看服务状态：

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
output/vendor/html2canvas.min.js
output/.rpg-me-viewer.json
```

`metadata.json` 只记录 `portraitFile`，不保存图片内容。`index.html` 使用同级相对路径引用图片，例如 `src="portrait.png"`，避免把 base64 大图硬塞进 HTML。
PNG 下载组件随 Skill 本地打包，记录生成时复制到 `output/vendor/`，不会运行时加载外链脚本。

## 本地查看器

`scripts/viewer_server.py` 只绑定 `127.0.0.1`，只读取当前项目的 `output` 目录，不做公网监听。生成历史会本地写入 `output/history/`。

接口：

- `GET /api/health`
- `GET /api/records`
- `GET /api/records/<id>`
- `POST /api/shutdown`

服务状态写入 `output/.rpg-me-viewer.json`，包含 `pid`、`port`、`token`、`startedAt`。它支持显式 `--stop`、Ctrl+C/SIGTERM，以及 `--idle-timeout` 空闲超时停止。

## 打包

```powershell
py -3 scripts/package_skill.py --out dist/rpg-me.skill
```

打包清单是显式维护的，不包含 `output/` 或本机历史数据。发布时请上传重新生成的 `dist/rpg-me.skill`，不要上传旧的根目录压缩包。

## 项目结构

```text
rpg-me/
  SKILL.md
  README.md
  VERSION
  assets/
    readme/
      rpg-me-cover-20260708-120824.jpg
      rpg-me-cover-20260708-093202.jpg
      rpg-me-cover-20260708-103138.jpg
    placeholder-portrait.svg
    portrait-sample.png
  references/
    image-generation.md
  scripts/
    card-template.html
    history_records.py
    package_skill.py
    render_sample_cards.py
    viewer_server.py
  vendor/
    html2canvas.min.js
    html2canvas.LICENSE.txt
  tests/
    smoke_test.py
```

## License

MIT
