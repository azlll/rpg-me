# rpg-me

> 把你此刻的状态，变成一组可晒的人生游戏角色卡

`rpg-me` 是一个 Agent Skill。它根据你输入的近况、性格和小愿望，自动为你设计一组 RPG 风格的「人生游戏角色卡」轮播图——包含职业身份、六维属性、RPG 面板、主动/被动技能、当前任务和角色立绘，最终渲染成 4 张可下载、可截图分享的网页卡片。

专为小红书 [REDSkill 大赏](https://www.xiaohongshu.com/) 这类需要强视觉传播、轻互动的场景设计。

<p align="center">
  <img src="assets/portrait-sample.png" alt="角色立绘示例" width="320" />
</p>

## 它能做什么

你只需要一句话描述现在的自己，比如「最近刚辞职，想 gap 一年，喜欢海边和咖啡」，rpg-me 就会为你生成：

- 一个契合你气质的 **角色身份**（职业、称号、等级）
- 六项 **人生属性**：体力值、社交力、创造力、摸鱼值、emo 抗性、运气值
- 一个和你近况有关的 **主动技能** 和一个性格向的 **被动技能**
- 一到两条你当下的 **主线任务**
- 一张由 AI 生成的 **角色立绘**
- 一段温暖又戳心的 **角色解析** 文字

所有内容会被渲染进 4 张 9:16 的轮播卡片：封面、角色解析、RPG 面板、技能任务。页面支持下载全部 4 张，也支持逐张 PNG 下载，直接发小红书。

## 两种玩法

| 模式 | 怎么玩 | 适合 |
|------|--------|------|
| 一句话生成 | 用一句话描述自己，剩下交给 skill | 想快、图个乐 |
| 回答问题 | 回答 5 个趣味问题后再生成 | 想要更贴合自己的结果 |

## 快速开始

这是一个 Agent Skill，需要在支持 Skill 的 Agent 环境中使用。

1. 下载本仓库，或直接获取打包好的 [`dist/rpg-me.skill`](dist/rpg-me.skill) 文件。
2. 把 skill 安装/导入到你的 Agent 环境中。
3. 对 Agent 说：「帮我生成一张人生游戏角色卡」，然后按提示描述自己即可。

生成完成后，Agent 会给你一个 HTML 结果页链接，打开就能看到你的角色卡组。点击「下载全部 4 张」会依次保存 4 张独立 PNG；也可以在每张卡下方点击「下载这一张」。

每次生成都会写入 `output/history/`，不会覆盖上一条结果。结果页左侧有一个类似聊天记录的「生成历史」列表，点击任意记录会在当前页面切换显示对应角色卡；也可以打开 `output/history/index.html` 查看全部生成历史。

## 验证与打包

本项目使用 Python 标准库完成 smoke test 和打包，不依赖额外安装包。

```powershell
# 运行基础验证
py -3 -m unittest tests.smoke_test

# 保存一条生成记录（Agent 通常会自动执行）
py -3 scripts/history_records.py --data card-data.json --portrait portrait.png --source-summary "用户输入摘要"

# 重新生成可安装 skill 包
py -3 scripts/package_skill.py --out dist/rpg-me.skill
```

当前版本记录在 [`VERSION`](VERSION)；发布包会包含 `README.md`、`LICENSE`、`VERSION` 和 skill 运行所需文件。

## 角色立绘怎么来的

不同 Agent 环境的生图能力不一样，rpg-me 内置了分层兜底策略，保证卡片里始终有一张能显示的图：

1. **优先** 使用当前环境已有的生图能力（内置文生图工具或生图 skill）。
2. **其次** 通过 `scripts/generate_portrait.py` 优先调用通义万相 / 阿里云百炼 API。
3. **再次** 回退到你自己配置的通用第三方文生图 API。
4. **最后** 回退到占位立绘，并提示你配置 API 后可重新生成真实图片。

生成的图片会以 base64 内嵌进 HTML，所以卡片文件可以随意移动、分享，图片都不会丢失。封面图区域固定为 1:1，推荐生图尺寸为 `1080*1080`。

### 配置生图 API（可选）

如果你的环境没有内置生图能力，推荐先配置通义万相 / 阿里云百炼。API 文档：

```text
https://bailian.console.aliyun.com/cn-beijing?tab=api#/api/?type=model&url=3026980
```

在项目根目录创建 `local-image-api.md`，写入本机配置；这个文件已被 `.gitignore` 排除，也不会被打包进 skill：

```markdown
DASHSCOPE_API_KEY=你的百炼APIKey
DASHSCOPE_WORKSPACE_ID=你的WorkspaceId
DASHSCOPE_REGION=cn-beijing
DASHSCOPE_IMAGE_MODEL=wan2.7-image-pro
DASHSCOPE_IMAGE_SIZE=1080*1080
```

未配置通义万相时，也可以配置 OpenAI 兼容 / 智谱 CogView / 自定义的文生图接口：

```bash
# OpenAI 兼容
export IMAGE_API_BASE="https://api.openai.com/v1/images/generations"
export IMAGE_API_KEY="sk-..."
export IMAGE_API_MODEL="dall-e-3"

# 智谱 CogView
export IMAGE_API_BASE="https://open.bigmodel.cn/api/paas/v4/images/generations"
export IMAGE_API_KEY="你的key"
export IMAGE_API_MODEL="cogview-3-flash"
export IMAGE_API_FORMAT="zhipu"
```

更多细节见 [`references/image-generation.md`](references/image-generation.md)。

## 目录结构

```
rpg-me/
├── README.md
├── SKILL.md                       # Skill 主文件（角色设计规则与工作流）
├── VERSION                        # 当前 skill 版本
├── assets/
│   ├── card-template.html         # 角色卡展示模板（纯展示，支持下载）
│   ├── placeholder-portrait.svg   # 无生图能力时的占位立绘
│   └── portrait-sample.png        # 示例立绘
├── references/
│   └── image-generation.md        # 分层生图方案与 API 配置说明
├── scripts/
│   ├── generate_portrait.py       # 可配置 API key 的生图脚本
│   ├── history_records.py         # 保存生成历史并刷新历史查看页
│   └── package_skill.py           # 生成 dist/rpg-me.skill 的打包脚本
├── tests/
│   └── smoke_test.py              # 基础可用性与打包完整性验证
└── dist/
    └── rpg-me.skill               # 打包好的可安装 skill
```

## 设计理念

- **结果即展示**：网页只负责展示 Agent 生成好的结果，不做二次生成，避免误导。
- **历史可回看**：每次生成都是一条独立记录，HTML 左侧可以像切换聊天记录一样切换角色卡。
- **图片永不丢**：立绘 base64 内嵌，分享和搬运都不掉图。
- **人人可用**：不假设环境有生图能力，三级兜底让任何 Agent 都能出卡。
- **有梗有共情**：属性保留短板，文案带小红书感，短板也用幽默化解。

## 许可证

MIT
