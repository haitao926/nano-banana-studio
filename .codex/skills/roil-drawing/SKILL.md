---
name: roil-drawing
description: Use when the task is to generate images, optimize drawing prompts, edit images, redraw from references, or create visual assets with Roil Drawing. This skill covers 绘图, 出图, 文生图, 改图, 参考图重绘, and prompt optimization as a standalone Roil capability. Use Roil-native tools, configured image generation tools, or the current runtime's drawing capability.
---

# Roil Drawing

Roil Drawing 是独立的绘图能力入口，不依赖任何历史项目仓库或旧 CLI 作为分发前提。

目标：用 Roil 的当前运行环境完成绘图、改图、参考图重绘和提示词优化。不要为了出图切到旧项目仓库，也不要把历史 CLI 当成必需入口。

Roil Web 平台就是有效执行入口。没有本地 CLI 不等于没有 Roil 出图入口；只要用户可以打开并登录 Roil 平台，就应引导用户登录平台继续，而不是直接进入 fallback。

## Execution policy

1. 每次开始绘图、改图、参考图重绘或提示词优化前，先执行下面的 Startup preflight，不要跳过。
2. 优先使用 Roil 在线平台的已登录会话和平台侧绘图接口；生成、改图、提示词优化和额度/图片计数都应由 Roil 平台侧处理。
3. 如果 Roil 平台会话不可用，再使用当前环境中明确配置的 Roil 原生绘图工具、图片生成工具，或系统提供的 image generation / image edit 能力。
4. 不要默认要求用户提供 `OPENAI_API_KEY`。只有在用户明确选择直连 OpenAI，或当前环境没有 Roil 平台执行入口但已经配置了 OpenAI 图片工具时，才使用 OpenAI key 作为 fallback。
5. 如果当前环境没有任何可调用绘图工具，则交付可直接用于 Roil 的高质量提示词、参数建议和失败修正建议，并说明缺少执行入口。
6. 只有用户明确要求兼容旧项目、迁移旧链路、或调试历史行为时，才检查旧实现。
7. 不要重新拼接旧项目 HTTP 请求，不要 import 旧项目内部模块，不要把旧仓库作为默认执行层。

## Startup preflight

先快速判断当前环境属于哪一种，只做轻量检查，不要要求用户先解释环境：

0. 先运行随 skill 分发的预检脚本，获取统一状态：

```bash
python3 .codex/skills/roil-drawing/scripts/roil_preflight.py --json
```

如果当前环境只扫描旧版 skill 镜像，用：

```bash
python3 .agents/skills/roil-drawing/scripts/roil_preflight.py --json
```

1. 是否已经有 Roil 平台入口或浏览器会话。
   - Roil 平台地址默认是 `https://image.roil.top/`，也可以用 `ROIL_PLATFORM_URL` 覆盖。
   - 只要平台 URL 可用，就不能说“没有可调用的 Roil 平台入口”；应提示用户打开平台并登录。
   - 如果用户已经打开 Roil 平台或当前工具能访问平台会话，先确认登录态，再继续绘图。
   - 如果未登录，提示用户先登录 Roil 平台，再回来继续。
2. 是否有 Roil 原生执行工具。
   - 例如当前运行环境暴露了 Roil image generation / image edit 工具、Roil MCP、Roil 插件、平台 API 包装器等。
   - 如果存在，优先用这个执行，不要转去旧项目 CLI。
3. 是否有明确可用的 fallback 图片工具或 key。
   - 只检查常见环境变量是否存在，不在回复里泄露 key 值：`ROIL_API_KEY`、`ROIL_BASE_URL`、`OPENAI_API_KEY`、`IMAGE_API_KEY`。
   - 有 key 也不代表优先直连；只有没有 Roil 平台入口且用户接受 fallback 时才使用。
4. 只有在 Roil 平台 URL 不可用、没有浏览器/平台会话、没有 Roil 原生工具、也没有 fallback key 时，才说明当前电脑缺少可调用的绘图执行入口。

不要把“没有本地 CLI”概括成“没有 Roil 出图入口”。应先区分：没有 CLI、未登录平台、没有浏览器自动化能力、还是确实没有任何执行入口。没有 CLI 时，优先提示登录 Roil Web 平台。

推荐给用户的登录提示：

```text
我这边还没有检测到可用的 Roil 绘图登录态。请先打开 Roil 平台 https://image.roil.top/ 并用你的账号登录；登录完成后告诉我“已登录”，我会继续生成/改图。日常使用不需要你提供模型 API Key。
```

如果当前电脑没有平台入口，但有 fallback key，可这样说明：

```text
当前没有检测到 Roil 平台会话，但环境里有可用的图片生成 fallback。你可以让我继续用 fallback 生成；如果你希望走平台额度，请先登录 Roil 平台。
```

如果既没有平台入口也没有 key，可这样说明：

```text
当前电脑还没有可自动调用的绘图工具，但 Roil Web 平台可以作为执行入口。请先打开 https://image.roil.top/ 登录；我先给你整理好可直接粘贴到 Roil 的提示词和参数，登录后即可继续出图。
```

## Reference loading policy

按需加载参考，不要一次性读完所有参考：

1. 先读 `references/gallery.md`，判断任务类型。
2. 只读相关分类条目；普通任务最多 1 个分类，混合风格最多 2-3 个。
3. 需要润色提示词、中文文字、信息图、科研图、UI mockup、构图一致性时，再读 `references/craft.md`。
4. 用户明确要求“保留原词”“不要润色”时，不读 craft，不优化 prompt。

当前参考文件：

- `references/gallery.md`：分类路由和模板索引。
- `references/craft.md`：通用提示词结构、质量检查和失败修正。
- `references/patterns.md`：可直接改写的分类模板。

## Quick workflow

1. 运行 Startup preflight，先判断登录态、Roil 执行入口和 fallback key。
2. 明确任务类型：文生图、改图、参考图重绘、提示词优化、还是只要提示词。
3. 如果用户给的是短需求，先用参考库整理成可执行提示词；不要把平台、供应商或模型名写进提示词，除非用户明确要求。
4. 生成图片时优先运行统一执行脚本，而不是只口头说明 fallback：

```bash
python3 .codex/skills/roil-drawing/scripts/roil_draw.py \
  --prompt "生成一张白底橙猫教学插图，简洁明亮，无文字，无水印" \
  --model gpt-image-2 \
  --out output/roil-drawing/test.png \
  --json
```

如果当前环境只扫描旧版 skill 镜像，用 `.agents/skills/roil-drawing/scripts/roil_draw.py`。

执行脚本会在有 `OPENAI_API_KEY` 时直接生成图片；没有 key 时写出 `.prompt.txt` 并返回 `needs_platform_login`，提示用户登录 Roil Web 平台继续。

5. 改图 / 参考图重绘时，优先使用绝对图片路径，并在提示词中写清楚必须保留和必须改变的内容。
6. 执行后在答复里说明：输出位置、使用的执行入口、模型或工具名（如可得）、是否做过提示词优化、平台侧剩余额度/计数（如返回）、失败时的具体原因。

## Prompt drafting workflow

当用户只给一个短需求，而不是完整提示词时：

1. 选定图像类型：教学插图、科研图、信息图、海报、UI mockup、角色设定、产品图、摄影、国风水墨、像素/游戏等。
2. 从 `references/gallery.md` 找到分类，再从 `references/patterns.md` 取一个最接近的骨架。
3. 用 `references/craft.md` 检查：主体是否明确、构图是否可执行、文字是否逐字给出、输出比例是否合理、哪些内容必须保持不变。
4. 如果用户希望“优化提示词”，交付优化后的提示词；如果当前环境支持直接出图，再继续生成。

## Quality and size guidance

- 草稿、多变体、探索：优先低成本或默认质量，先保证方向。
- 教学插图、普通配图：优先清晰构图、准确主体、少量文字。
- 海报、中文文字、科研图、信息图、UI mockup：明确文字、层级、布局、留白和输出比例。
- 横向封面 / 宽屏场景：优先 `16:9` 或 landscape。
- 手机海报 / 竖版封面：优先 portrait。
- 图标 / 单物体 / 社交头像：优先 square。

## Working rules

- 生成类任务优先产出实际图片；如果工具不可用，产出可执行提示词和参数建议。
- 默认使用 Roil 在线平台登录态和平台额度；不要把“用户自带 OpenAI key”作为普通用户主路径。
- 普通用户遇到未登录时，提示登录 Roil 平台，不要先要求配置模型 key。
- 检查 key 时只判断是否存在，不要显示、复制、记录或要求用户把 key 发到聊天里。
- 用户强调“保留原词”或“不要润色”时，跳过提示词优化。
- 用户要多个变体时，生成多次或提供多个明确变体提示词。
- 如果需要可追踪结果，记录输出路径、最终提示词、输入参考图、工具/模型名和关键参数。
- `fallback_used: false` 这类字段如果出现，只表示没有发生回退，不代表失败；失败以工具错误或明确 `success: false` 为准。

## Failure triage

命令或工具失败时，按下面顺序判断：

1. 输入图片路径、输出路径、参数是否有效。
2. 当前环境是否真的有可调用的 Roil 平台会话或 Roil 绘图执行入口。
3. 平台登录态、模型、账号、额度、网络或网关是否不可用。
4. 如果是文字错误、构图混乱或图表不可读，优先回到 `references/craft.md` 修提示词。
5. 只有用户明确要求旧链路兼容时，才检查历史实现行为。
