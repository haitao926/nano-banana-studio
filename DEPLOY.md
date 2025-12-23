# 🍌 Nano Banana AI 绘图工坊 - 部署指南

这是一个基于 Python Streamlit 的 AI 图像生成应用。
您可以将其部署在本地局域网，或者云服务器上供团队使用。

## 📋 环境要求

- 操作系统：Windows / macOS / Linux
- Python 版本：3.8 或更高

## 🚀 快速部署 (给最终用户)

### 方式 A: Windows 一键运行 (推荐)
直接双击运行目录下的 `run_app.bat` 即可。
脚本会自动安装依赖并打开浏览器。

### 方式 B: 命令行/服务器部署
如果您是在 Linux 服务器或需要手动安装：

1. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

2. **启动服务**
   ```bash
   streamlit run web_ui.py
   ```

3. **访问地址**
   - 本机访问：http://localhost:8501
   - 局域网访问：http://<服务器IP>:8501

## ⚙️ 配置说明

### API Key 设置
默认 API Key 存储在 `config.json` 中。
用户首次登录网页时，也可以在左侧边栏的 **"⚙️ 全局设置"** 中输入自己的 Key，这不会修改服务器上的文件，仅对当前会话有效。

### 端口修改
如果 8501 端口被占用，请修改 `.streamlit/config.toml` 文件中的 `port` 值。

## 🔒 安全建议 (公网部署)
如果部署在公网，建议：
1. 在云服务商防火墙仅开放特定 IP 访问。
2. 或使用 Streamlit 的 `secrets.toml` 设置访问密码（高级功能）。
