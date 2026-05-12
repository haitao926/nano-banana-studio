---
name: roil-drawing
description: Use when the task is to generate images, optimize drawing prompts, edit images, redraw from references, or create visual assets with Roil Drawing. This is the single teacher-facing drawing skill. It covers 绘图, 出图, 文生图, 改图, 参考图重绘, and prompt optimization, and should decide internally whether to use local Roil/NBS login, the public Roil platform, or other available drawing execution paths.
---

# Roil Drawing

Roil Drawing 是对外唯一的绘图入口，面向老师隐藏内部链路差异。老师只需要提出需求，skill 负责判断使用哪条执行路径。

## Purpose And Guarantees

- 默认目标是产出实际图片；如果当前环境没有可执行出图路径，再退化为可执行提示词和参数建议。
- 默认优先使用已登录的 Roil/NBS 链路，不要求普通用户先提供模型 API Key。
- Roil Web 平台是有效入口，但主要承担登录和兜底作用，不是默认的浏览器点击执行路径。
- 没有独立的 `roil` 或 `roil-drawing` 可执行命令，不等于这个 skill 不可用；只要预检确认 `./nbs` 或 Roil 平台入口可用，就仍然存在有效执行路径。
- 不暴露密钥，不重拼旧项目 HTTP 请求，不 import 旧项目内部模块，不把旧仓库实现当默认执行层。
- 当前 skill 文档描述契约，实际路由与结果字段以 `scripts/roil_preflight.py` 和 `scripts/roil_draw.py` 为准。

## Routing Rules

- 每次开始绘图、改图、参考图重绘或提示词优化前，先运行预检脚本。
- 在没有跑过预检脚本前，不允许把当前环境描述成“Roil Drawing 不可用”或“没有 Roil 出图入口”。
- 只要工作区里已经有 `roil_preflight.py` / `roil_draw.py`，就不要先去手工读取 `~/.nbs/auth.json`、搜索环境变量、grep `backend/`、grep `gpt-image-2`，或继续寻找“别的可能入口”。
- 如果预检结果是 `generate_via_nbs_cli_backend` 或 `try_nbs_cli_direct`，下一步必须直接调用 `roil_draw.py` 或 `./nbs image generate`；不要在真正执行前反复做模型、key、配置和代码层面的额外探索。
- 一次预检加一次实际生成尝试，优先级高于多轮环境侦察；只有脚本失败且错误信息不足时，才继续向内排查。
- 优先级保持不变：
  1. 已确认登录态的 `./nbs` 后端认证链路
  2. 本地 `./nbs` 直连链路
  3. 生成 `.prompt.txt` 并交还 Roil 平台登录入口
- 不要把“缺少独立命令 `roil` / `roil-drawing`”当成失败信号。这个 skill 的入口判定以 `roil_preflight.py` 结果为准，而不是以 `command -v roil` 是否命中为准。
- 在 Codex 桌面环境里，只要 `./nbs auth whoami --json` 和 `./nbs models --service image --json` 能正常返回，就不要使用 Browser Use、Computer Use 或其他浏览器自动化执行常规出图。
- 只有两类情况允许进入浏览器相关动作：
  1. 用户明确要求打开平台、浏览器操作或网页演示。
  2. CLI 路径不可用或失败，需要把用户引导到登录页；此时只允许打开登录页，不要在网页里代替用户持续点按钮完成常规生图。

## Startup Preflight Contract

统一预检入口：

```bash
python3 .codex/skills/roil-drawing/scripts/roil_preflight.py --json
```

旧镜像环境使用：

```bash
python3 .agents/skills/roil-drawing/scripts/roil_preflight.py --json
```

预检脚本负责：

- 探测平台入口、局域网地址、本地认证文件记录的候选地址
- 检测本地 `nbs` CLI 是否可用
- 检测已保存的 Roil/NBS 登录态、可用额度与 refresh 结果
- 检测 fallback key 是否存在，但不泄露 key 值
- 显式输出一条防误判说明，提醒 agent 不要因为缺少 `roil` 独立命令就宣告不可用
- 输出稳定 JSON，至少包含：
  - `skill`
  - `platform_url`
  - `platform_probe`
  - `nbs_cli`
  - `nbs_auth`
  - `fallback_key_available`
  - `availability_tier`
  - `decision_summary`
  - `safe_to_show_user`
  - `recommended_next_step`

`recommended_next_step` 只允许以下值：

- `generate_via_nbs_cli_backend`
- `try_nbs_cli_direct`
- `open_or_login_platform`
- `check_network_or_open_platform_manually`

`availability_tier` 使用更直白的入口分层，只允许以下值：

- `native_cli_backend`
- `native_cli_direct`
- `web_handoff`
- `manual_or_none`

当 `recommended_next_step` 为 `generate_via_nbs_cli_backend` 或 `try_nbs_cli_direct` 时，agent 不得对用户说“没有可调用的 Roil 平台/CLI 出图入口”。

对老师的登录提示统一使用：

```text
请先登录 Roil 平台：https://image.roil.top/
```

如果当前电脑没有平台会话，不要主动切到 key fallback；统一这样说明：

```text
当前没有检测到可用的 Roil 平台会话。请先登录 Roil 平台：https://image.roil.top/
```

如果当前电脑没有自动执行入口，可这样说明：

```text
当前电脑还没有可自动调用的绘图工具，但 Roil Web 平台可以作为执行入口。请先登录 Roil 平台：https://image.roil.top/
```

## Prompt And Reference Contract

- 先读 `references/gallery.md` 判断任务类型。
- 普通任务最多读取 1 个分类，混合风格最多 2-3 个分类。
- 需要润色提示词、中文文字、信息图、科研图、UI mockup、构图一致性时，再读 `references/craft.md`。
- 用户明确要求“保留原词”或“不要润色”时，不读 `craft.md`，不优化 prompt。
- 可复用参考：
  - `references/gallery.md`
  - `references/craft.md`
  - `references/patterns.md`

## Execution Contract

统一执行入口：

```bash
python3 .codex/skills/roil-drawing/scripts/roil_draw.py \
  --prompt "生成一张白底橙猫教学插图，简洁明亮，无文字，无水印" \
  --model gpt-image-2-all \
  --out output/roil-drawing/test.png \
  --json
```

旧镜像环境使用：

```bash
python3 .agents/skills/roil-drawing/scripts/roil_draw.py --prompt "..." --json
```

`roil_draw.py` 是执行层 source of truth。默认请求模型是 `gpt-image-2-all`；只有这条链路失败时，才允许继续回退到其他可用模型或执行入口。它保持当前分支顺序不变，并返回稳定结果字段。所有分支都应尽量包含：

- `success`
- `status`
- `via`
- `runner`
- `model`
- `output_path`
- `message`

在相关分支保留现有扩展字段：

- `fallback_from`
- `previous_attempt`
- `platform_url`
- `platform_probe`
- `prompt_path`
- `error`
- `error_type`

`needs_platform_login` 仍然是标准登录交还状态。`--open-platform` 只允许在登录交还分支触发打开平台，不代表浏览器变成默认执行入口。

执行后，agent 应向用户明确汇报：

- 输出位置
- 使用的执行入口
- 模型或工具名
- 是否做过提示词优化
- 平台侧剩余额度或计数（如可得）
- 失败时的具体原因

## Failure Triage

命令或工具失败时，按下面顺序判断：

1. 输入图片路径、输出路径、参数是否有效。
2. 当前环境是否真的有可调用的 Roil 平台会话或 Roil 绘图执行入口。
3. 平台登录态、模型、账号、额度、网络或网关是否不可用。
4. 如果是文字错误、构图混乱或图表不可读，优先回到 `references/craft.md` 修提示词。
5. 只有用户明确要求旧链路兼容时，才检查历史实现行为。
