# 🍌 Nano Banana 2.0 - 架构重构计划 (Vue.js 版)

## 1. 项目愿景
构建一个**企业级、现代化、高颜值**的 AI 绘图 SaaS 平台。
将原有的脚本工具升级为标准的 **前后端分离 (B/S)** 架构，支持独立部署、多端访问和极致的用户体验。

## 2. 技术栈选型

### 🎨 前端 (Client)
*   **核心框架**: Vue 3 (Composition API) - 响应式核心
*   **构建工具**: Vite - 极速开发体验
*   **UI 框架**: Naive UI 或 Element Plus - 优雅的组件库 (暗黑模式支持)
*   **样式库**: Tailwind CSS - 高度定制化设计
*   **状态管理**: Pinia - 管理任务队列和全局配置
*   **路由**: Vue Router

### ⚡ 后端 (Server)
*   **API 框架**: FastAPI - 高性能 Python Web 框架 (替代 Streamlit)
*   **核心逻辑**: 复用现有的 `image_generator.py` 和 `batch_image_generator.py`
*   **数据存储**: SQLite (轻量级) 或 JSON 文件系统 (保持现状)

## 3. 目录结构规划

重构后的项目将分为两个主要目录，保持整洁：

```
D:\project\nano banana\
├── 📂 backend/              # 后端服务 (Python)
│   ├── main.py             # FastAPI 入口
│   ├── router.py           # API 路由
│   ├── image_generator.py  # (复用) 核心绘图类
│   ├── models.py           # Pydantic 数据模型
│   └── static/             # 存放生成的图片 (供前端访问)
│
├── 📂 frontend/             # 前端应用 (Vue.js)
│   ├── src/
│   │   ├── api/            # Axios 请求封装
│   │   ├── components/     # UI 组件 (Gallery, BatchTable...)
│   │   ├── views/          # 页面 (Playground, History...)
│   │   └── App.vue
│   ├── package.json
│   └── vite.config.ts
│
└── 📄 run_server.bat        # 一键启动脚本 (同时拉起前后端)
```

## 4. API 接口设计 (Draft)

后端将提供标准的 RESTful 接口供 Vue 调用：

| 方法 | 路径 | 描述 |
| :--- | :--- | :--- |
| **GET** | `/api/status` | 检查服务健康状态 |
| **POST** | `/api/generate` | 单图生成 (Playground) |
| **POST** | `/api/batch/task` | 提交批量生成任务 |
| **GET** | `/api/batch/progress` | 获取任务进度 (轮询/SSE) |
| **GET** | `/api/gallery` | 获取历史图片列表 |
| **GET** | `/api/config` | 获取/更新系统配置 |

## 5. 核心页面规划

### A. 🎨 创作空间 (Playground)
*   **左侧**: 控制面板。极简设计的表单，支持折叠/展开高级选项（尺寸、步数）。
*   **右侧**: 实时预览区。加载骨架屏 (Skeleton) -> 渐进式加载图片。
*   **交互**: 生成成功后，提供“一键下载”和“查看元数据”的浮层。

### B. 🏭 批量流水线 (Batch Factory)
*   **矩阵配置器**: 类似 Excel 的网格视图，直观勾选 [风格] x [内容]。
*   **任务监视器**: 动态进度条，实时显示 `(3/20)` 完成度。
*   **防误触**: 生成过程中锁定按钮，防止重复提交。

### C. 🖼️ 沉浸式画廊 (Gallery)
*   **瀑布流布局 (Masonry)**: 优雅展示不同尺寸的图片。
*   **灯箱模式 (Lightbox)**: 点击图片放大，支持键盘左右切换。
*   **筛选**: 按时间、Prompt 关键词快速搜索。

## 6. 实施路线图 (Roadmap)

1.  **后端先行**: 初始化 FastAPI，将现有 Python 逻辑包装为 API 接口。
2.  **前端脚手架**: 搭建 Vue 3 + Vite 环境，配置 Tailwind。
3.  **核心联调**: 实现“单图生成”的前后端打通。
4.  **批量迁移**: 移植批量生成逻辑，实现前端进度条。
5.  **UI 润色**: 添加过渡动画、Loading 态、错误提示。
6.  **打包交付**: 编译 Vue 为静态文件，由 Python 统一托管，实现“单文件部署”。

---
*Created by Nano Banana Engineering Agent*