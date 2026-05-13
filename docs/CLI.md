# CLI

项目现在提供一个仓库内可直接使用的 CLI 入口：`./nbs`。

## 前提

- 已安装 `backend/requirements.txt` 里的 Python 依赖
- 已配置 `.env.nbs`
- 已准备好 `backend/data/config.json` 中的模型 / Key / base_url

## 给 agent 的调用约定

- 已登录 `nbs auth login` 时，`image/audio/video/digital-human/prompt/batch/queue` 会优先走后端认证链路
- 只有在显式传 `--api-key` / `--base-url`，或设置 `NBS_FORCE_DIRECT=1` 时，才走直连上游 key 模式
- 需要结构化结果时，统一加 `--json`
- 生成类命令尽量显式传 `--output`
- 如果要看到底层 `backend/core/*` 的调试日志，设置 `NBS_VERBOSE=1`
- CLI 默认直接复用 `backend/core/*`，不要再重复拼 HTTP API

## 常用命令

```bash
# 登录后端（普通用户只需要用户名 + 密码）
./nbs auth login --base-url http://127.0.0.1:8000 --username demo
./nbs auth whoami --base-url http://127.0.0.1:8000 --json

# 浏览器已经登录时，把网页登录态同步给 CLI
./nbs auth sync-web --base-url https://image.roil.top

# 查看已配置模型
./nbs models --service image --json

# 提示词优化
./nbs prompt optimize \
  --prompt "生成一张关于具身智能的教学插图" \
  --subject textbook

# 先优化再生成图片
./nbs image generate \
  --prompt "生成一张关于具身智能的教学插图" \
  --subject textbook \
  --model gemini-3.1-flash-image-preview \
  --optimize

# 基于参考图重绘
./nbs image edit \
  --prompt "把图中的狗换成猫" \
  --image ./input/a.png

# 生成 TTS
./nbs audio tts \
  --text "大家好，今天我们学习人工智能。" \
  --voice Cherry \
  --model qwen-tts-latest

# 查看批量提示词配置
./nbs batch prompts --json

# 生成一个批量任务（requirement index 为 0-based）
./nbs batch generate \
  --system-key ppt_education \
  --requirement-index 0 \
  --model z-image-turbo \
  --output-dir /tmp/nbs_batch_cli \
  --json

# 生成多类型队列模板
./nbs queue template --type mixed --output /tmp/nbs_queue_tasks.json --json

# 运行一个 JSON 队列（示例里可混合 image/audio/video/digital_human）
./nbs queue run \
  --file /tmp/nbs_queue_tasks.json \
  --output-dir /tmp/nbs_queue_output \
  --continue-on-error \
  --json

# 提交视频任务并等待完成
./nbs video submit \
  --prompt "让画面中的人物微笑并挥手" \
  --model sora-2 \
  --image-url https://example.com/demo.png \
  --wait --json

# 数字人任务
./nbs digital-human submit \
  --image-url https://example.com/avatar.png \
  --audio-url https://example.com/audio.wav \
  --model wan2.2-s2v \
  --wait --json
```

## 已原子化能力

- `models`：查看模型目录
- `auth login/refresh/whoami/logout/sync-web`：系统登录态管理
- `prompt optimize`：提示词优化
- `image generate`：图片生成
- `image edit`：参考图编辑
- `audio tts`：语音合成
- `batch prompts/history/generate`：批量图片配置查看、历史查看、批量生成
- `queue template/run`：多类型 JSON 队列模板与执行
- `video submit/status`：视频任务提交与查询
- `digital-human submit/status`：数字人任务提交与查询

## 已验证状态

2026-03-18 已在本地仓库做过 smoke test：

- `./nbs --help`
- `./nbs auth login ...`
- `./nbs auth whoami ... --json`
- `./nbs models --service image --json`
- `./nbs prompt optimize --prompt "生成一张关于具身智能的教学插图" --subject textbook --json`
  - CLI 链路正常
  - 当前提示词通道上游仍可能因 key / 分组策略失败
- `./nbs image generate --prompt "一只白底橙猫插画，简洁明亮" --model z-image-turbo --output /tmp/nbs_auth_image.png --json`
  - 已成功（登录后走后端认证）
- `./nbs audio tts --text "大家好，今天我们测试后端认证模式。" --model qwen-tts-latest --voice Cherry --output /tmp/nbs_auth_audio.wav --json`
  - 已成功（登录后走后端认证）
- `./nbs image generate --prompt "一只白底橙猫插画，简洁明亮" --model z-image-turbo --output /tmp/nbs_cli_test_image.png --json`
  - 已成功
- `./nbs audio tts --text "大家好，今天我们测试 CLI 语音合成。" --model qwen-tts-latest --voice Cherry --output /tmp/nbs_cli_test_audio.wav --json`
  - 已成功
- `./nbs batch prompts --json`
  - 已成功
- `./nbs batch history --limit 3 --json`
  - 已成功
- `./nbs batch generate --system-key ppt_education --requirement-index 0 --model z-image-turbo --output-dir /tmp/nbs_batch_cli --json`
  - 已成功
- `./nbs queue template --type mixed --json`
  - 已成功
- `./nbs queue run --file /tmp/nbs_queue_tasks.json --output-dir /tmp/nbs_queue_output --continue-on-error --json`
  - 已成功（本地实测 image + audio 混合队列）
- `./nbs queue run --file /tmp/nbs_queue_tasks.json --output-dir /tmp/nbs_queue_backend_output --continue-on-error --json`
  - 已成功（登录后 image + audio 混合队列走后端认证）

## 设计原则

- CLI 优先复用 `backend/core/*` 的现有能力，不再绕 HTTP API
- 普通用户认证只需要用户名 + 密码；模型 API Key 由后端保管
- 如果浏览器已经登录但 CLI 本地 refresh token 失效，可用 `./nbs auth sync-web --base-url https://image.roil.top` 发起设备码同步；浏览器打开提示链接确认后，CLI 会自动写回新的本地会话
- 默认从 `backend/data/config.json` 取模型 / Key / base_url
- 支持用命令行参数覆盖 `api_key` / `base_url`
- 默认优先走后端认证；显式传 `--api-key` / `--base-url` 或设置 `NBS_FORCE_DIRECT=1` 时再直连上游
- `--json` 模式下默认静音底层打印，方便其他 agent 直接解析
- 生成类命令尽量落本地文件并返回明确路径
- `batch generate` 里的 `--requirement-index` 使用 0-based 索引
- `queue run` 会把 image/audio 直接落到本地；video/digital_human 在拿到远端结果后会继续下载到本地
- `queue run` 处理 video/digital_human 的输入媒体时，优先使用 public URL；若是 `/static/...` 且已配置 OSS，会尝试自动转成可访问的公网 URL
- `image edit` 目前仍主要走直连模式；如果要走后端，需要先把参考图变成后端可访问的静态资源/公网 URL
