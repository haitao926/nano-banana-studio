# 🍌 智绘工坊

**智绘工坊** 是一个专为教育场景打造的 AI 素材生成工坊。它不仅仅是一个绘图工具，更是一个集成了教学场景适配、提示词优化、额度管理和内容风控的完整解决方案。

---

## 🌟 核心功能

### 1. 🎨 教学素材生成
*   **学科分类 (Subject)**：支持数学、科学、英语、艺术、历史等分类，生成的图片自动归档。
*   **年级适配 (Grade)**：支持从幼儿园到大学的年级选择，AI 自动调整画风（如低年级更卡通，高年级更写实）。
*   **画质分级**：提供 1K (Standard)、2K (High)、4K (Ultra) 三档画质，自动注入画质增强指令。
*   **多画幅支持**：支持 1:1、16:9 (PPT专用)、9:16 (手机海报)。

### 2. 🪄 智能辅助
*   **Magic Optimize**：内置 Prompt Engineer，一键将简单的词语（如“猫”）扩写为电影级的光影描述。
*   **沉浸式详情页**：点击图片查看完整提示词，支持一键复制，方便教学复盘。

### 3. 🛡️ 管理与风控
*   **防刷限流**：
    *   单 IP 每分钟限生成 1 张。
    *   单 IP 每周限生成 20 张（SQLite 持久化存储，重启不丢失）。
    *   上传接口支持时间窗内频控（默认 60 秒 30 次，可配置）。
    *   额度不足时引导联系信息组。
*   **图库管理**：
    *   **精选机制**：管理员可对优质图片“加星”，普通用户默认只看到精选图片。
*   **展示区域**：所有被标记为精选的图片将优先展示在画廊中。

### 4. 🗣️ 数字人视频生成 (wan2.2-s2v / DashScope)
*   **输入**：单张图片 + 音频 + 可选提示词，生成数字人视频。
*   **支持**：中文/英文/日语/韩语/墨西哥语/印尼语提示词，支持运镜与动作描述。
*   **约束**：图片 < 5MB、最长边 < 4096；音频 < 60 秒（推荐 ≤ 15 秒）；提示词 ≤ 300 字符。

### 5. 🎬 视频模型信息 (Veo 3.1 / Veo 3.1 Fast)
*   **模型定位**：Veo 3.1 为 Google 高保真视频生成模型，可生成 8 秒 720p/1080p/4k 视频并原生生成音频。
*   **主要能力**：支持文生视频、首/尾帧插值、视频延展、最多 3 张参考图，以及 16:9 / 9:16 画幅。
*   **Fast 版本**：`veo-3.1-fast-generate-preview` 面向速度与业务场景，输出含音频；定价约 $0.15/秒（标准版 $0.40/秒）。
*   **API 端点**：
    * Gemini API (Veo 3.1)：  
      ```text
      https://generativelanguage.googleapis.com/v1beta
      POST /models/veo-3.1-generate-preview:predictLongRunning
      ```
    * OpenAI 视频 API（Sora）：  
      ```text
      POST https://api.openai.com/v1/videos
      ```

---

## 🚀 生产环境部署 (Production)

### 1. 环境要求
*   **OS**: Linux (推荐 Ubuntu/Debian) 或 macOS
*   **Python**: 3.10+
*   **Node.js**: 18+ (用于构建前端)

### 2. 一键启动
在项目根目录下运行生产环境脚本。脚本会自动构建前端、设置后端虚拟环境并启动服务：

```bash
./run_prod.sh
```

**启动成功后：**
*   脚本会自动检测并显示局域网 IP。
*   **本机访问**: `http://localhost:6060`
*   **局域网访问**: `http://<你的局域网IP>:6060` (例如 `http://192.168.1.10:6060`)

### 3. 设置开机自启动 (Linux/macOS)
支持将服务注册为系统服务 (Systemd on Linux, Launchd on macOS)，实现开机自动后台运行。

**安装自启动服务：**
```bash
# Linux (需要 sudo)
sudo ./run_prod.sh --install-startup

# macOS
./run_prod.sh --install-startup
```

> **注意**：自启动模式下，服务会自动附带 `--no-build` 参数，跳过前端构建步骤以加快启动速度。如果你更新了前端代码，请手动运行一次 `./run_prod.sh` 重新构建。

**管理服务 (Linux)：**
```bash
# 查看状态
systemctl status nano-banana.service

# 重启服务
sudo systemctl restart nano-banana.service

# 查看日志
journalctl -u nano-banana.service -f
```

---

## 🛠️ 开发环境 (Development)

如果你是开发者，需要实时调试代码：

```bash
./run_dev.sh
```

此脚本会启动带有热重载功能的开发服务器：
*   后端 API: `http://localhost:8000` (Docs: `/docs`)
*   前端页面: `http://localhost:5173`

---

## 🗣️ 数字人 (OmniHuman1.5) 配置

数字人功能依赖火山引擎视觉服务，请在运行前配置以下环境变量（不要提交密钥到仓库）：

```bash
export VOLC_ACCESS_KEY="你的 Access Key ID"
export VOLC_SECRET_KEY="你的 Secret Access Key"
export EXTERNAL_BASE_URL="https://你的公网域名"
```

**说明：**
* `EXTERNAL_BASE_URL` 用于将 `/static/uploads/...` 拼成公网可访问地址（模型服务需要公网 URL）。
* 如已泄露密钥，请立即在控制台禁用/删除并重新生成。
* 也可以将环境变量写入项目根目录的 `.env.nbs`（参考 `.env.example`），`run_dev.sh` / `run_prod.sh` 会自动加载。
* `.env.nbs` 中的 `IMAGE_* / TTS_* / VIDEO_*` 会覆盖 `backend/data/config.json`（后台系统配置）。
* `IMAGE_MODEL_KEY_MAP` 支持为不同模型指定不同 Key（格式：`model=key,model2=key2` 或 JSON 字典）。
* `IMAGE_MODEL` / `IMAGE_LLM_MODEL` 可分别指定绘图模型与润色用的文本模型（不填则沿用配置里的 model）。
* `KEY_POOLS` 可配置多 Key 池与路由规则（JSON 或简化配置），用于多服务/多模型的 Key 分流。

### 可选：OSS 公网上传
默认上传使用 `/api/upload`（本地存储）。如需直接返回 OSS 公网 URL，请配置以下环境变量，并在前端设置 `VITE_PUBLIC_UPLOAD_URL=/api/upload_public`：

```bash
export OSS_BUCKET="你的 Bucket"
export OSS_ENDPOINT="你的 Endpoint"
export OSS_ACCESS_KEY_ID="你的 Access Key ID"
export OSS_ACCESS_KEY_SECRET="你的 Secret Access Key"
```

**可选：**
* `OSS_PUBLIC_BASE_URL`：自定义公网访问域名
* `OSS_UPLOAD_PREFIX`：上传前缀（默认 `uploads`）

---

## 📁 目录结构说明

```text
nano-banana-studio/
├── run_prod.sh             # 生产环境启动与部署脚本
├── run_dev.sh              # 开发环境启动脚本
├── backend/                # Python 后端 (FastAPI)
│   ├── main.py             # API 入口
│   ├── api/                # 路由分层 (auth/generate/upload/...)
│   ├── core/               # 核心逻辑 (AI生成、限流等)
│   ├── app_state.py        # 环境与核心实例初始化
│   ├── helpers.py          # 通用工具与配置封装
│   ├── schemas.py          # Pydantic Schema
│   └── static/generated/   # 图片存储区
└── frontend/               # Vue3 前端
    └── dist/               # 构建后的静态文件 (由 run_prod.sh 生成)
```

---

## 📊 管理员手册

### 数据统计
登录管理员后，点击顶部的 **📊 报表图标**，可查看：
*   各学科生成热度
*   各年级使用分布
*   活跃 IP 排行榜

### 图片管理
在“学科画廊”中，管理员可以看到每张图片右上角的 **☆ 星星**：
*   **点亮星星**：设为精选（Featured），作为展示图片。
*   **熄灭星星**：取消精选。
*   **过滤开关**：侧边栏底部有“只看精选”开关，方便预览学生视角。

---

## 📞 支持与联系
**Copyright © 上海科技大学附属学校信息组**
如需调整额度或报告问题，请联系信息组老师。
