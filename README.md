# 🍌 智绘工坊 (Nano Banana Studio)

**智绘工坊** 是面向教学场景的 AI 素材生成平台，提供统一的模型配置、额度管理、提示词优化与素材管理能力。

---

## 🌟 核心功能

### 1) 🎨 图像生成
- 学科/年级维度归类与提示词优化
- 多画幅输出（1:1 / 16:9 / 9:16）
- 统一模型配置（平台 + 模型 + Key + 积分）

### 2) 🔊 音频生成 (TTS)
- 支持阿里百炼 TTS（如 `qwen3-tts-flash`）
- 支持音色选择、指令优化、历史记录

### 3) 🎬 视频生成
- 支持火山方舟 / 向量中转平台的视频模型
- 文生视频 / 图生视频
- 模型统一配置 + 积分消耗

### 4) 🧑‍💻 数字人
- **阿里百炼 `wan2.2-s2v`**（图片 + 音频生成数字人视频）
- 默认 480P，参数统一配置

### 5) 🛡️ 管理与风控
- 额度/配额管理
- 图片精选与画廊管理
- 配置页内一键“模型测试”

---

## 📘 使用手册
- [非管理员使用手册](docs/user-manual-non-admin.md)
- [批量图片生成工具说明](docs/README_批量图片生成.md)

## 🤖 Codex Skills

本仓库内置项目级 Codex skill：

```text
.codex/skills/roil-drawing/
```

在其他电脑上克隆仓库后，用 Codex 打开这个项目并重启/刷新 Codex，即可通过 `$roil-drawing` 调用绘图、改图、参考图重绘和提示词优化工作流。

Roil Drawing 是升级后的独立绘图能力入口，不再调用旧版 NBS，也不把仓库 CLI 当成必需执行层。它会优先使用 Roil 在线平台、Roil 原生工具或当前运行环境已经配置的图片生成能力；如果当前环境没有可调用的绘图工具，则会输出可直接用于 Roil 的提示词和参数建议，并明确说明缺少执行入口。

兼容说明：部分旧版 OMX/Codex 会扫描 `.agents/skills/roil-drawing/`，仓库中保留了同名兼容镜像。其他电脑提示“没有执行入口”时，优先检查是否拉到了 `roil-drawing` 目录，以及 Codex 是否已重新扫描项目。

---

## 🚀 生产环境部署（Docker 推荐）

### 1) 环境要求
- Linux (推荐 Ubuntu)
- Docker + Docker Compose

### 2) 克隆代码
```bash
git clone http://8.145.44.54:3000/admin/nano-banana-studio.git
cd nano-banana-studio
```

### 3) 配置模型（必须）
系统配置文件在：
```
backend/data/config.json
```
> **注意：该文件包含密钥，不提交到仓库。**

你可以：
- 直接拷贝已有配置到服务器
- 或先启动服务，再到 **设置 → 模型配置** 中填写

### 4) 启动服务
```bash
docker compose up -d --build
```

### 5) 访问地址
```
http://服务器IP:18080
```
> 后端不对公网开放，前端通过容器网络转发 `/api`。

### 6) 更新版本
```bash
git pull
docker compose up -d --build
```

---

## 🧩 配置说明

### 模型配置
进入 **设置 → 模型配置**：
- 配置 **模型名称 / 平台 / Key / 积分**
- 按平台或功能分组管理
- 每条模型提供 **“测试”按钮**（会真实消耗额度）

### EXTERNAL_BASE_URL
如果模型需要公网访问静态资源（如数字人图片/音频），请确保:
- `EXTERNAL_BASE_URL` 设置为你的公网域名或反向代理地址
- Docker 里已在 `docker-compose.yml` 配置

---

## 🛠️ 开发环境 (Development)

本地开发启动：
```bash
./run_dev.sh
```

默认端口：
- 后端 API: `http://localhost:8000`
- 前端页面: `http://localhost:5173`（如占用会自动改为 5174）

---

## 📁 目录结构

```text
nano-banana-studio/
├── docker-compose.yml      # Docker 部署入口
├── docs/                   # 使用文档
│   ├── user-manual-non-admin.md
│   └── README_批量图片生成.md
├── frontend/               # Vue3 前端
│   ├── Dockerfile
│   └── nginx.conf
├── backend/                # FastAPI 后端
│   ├── Dockerfile
│   └── data/config.json    # 系统配置（不提交）
├── run_dev.sh              # 本地开发启动
└── README.md
```

---

## ⚠️ 安全提示
- 默认管理员账号 **admin / admin888**（首次启动会创建）
- 建议上线后立即修改密码
- 配置文件包含 Key，请勿提交到仓库

---

如需进一步扩展平台/模型，可在 **模型配置** 中直接新增。
