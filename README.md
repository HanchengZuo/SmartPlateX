# 🚗 SmartPlateX 智能车牌识别与车辆类型统计系统

**SmartPlateX** 是一个基于 Flask 构建的智能车牌识别与分析平台，支持视频上传、帧图抽取、车牌识别（调用百度云 API）以及基于车牌颜色对油车与新能源车的数量进行统计和可视化。

**SmartPlateX** is a Flask-based license plate recognition and vehicle type analysis system. It supports video upload, frame extraction, license plate recognition via Baidu OCR API, and vehicle type statistics (EV vs Fuel) based on plate color with data visualization.

---

## ✨ 项目特色 | Features

- 📥 视频上传  
  Upload your own `.mp4` video files

- 🎞 自定义帧率抽帧  
  Extract frames from videos at a specified FPS

- 🔍 百度云车牌识别（多车识别）  
  License plate recognition using Baidu OCR API (multi-plate detection)

- 📊 油车与新能源车数量统计  
  Count fuel vs electric vehicles based on plate color

- 📍 车牌地区分布统计  
  Region-wise statistics from license plate prefixes

- 📈 交互式图表展示（Chart.js）  
  Interactive charts powered by Chart.js

---

## 🧠 技术栈 | Tech Stack

- **后端 | Backend**：Python, Flask  
- **前端 | Frontend**：HTML, CSS, JavaScript  
- **可视化 | Visualization**：Chart.js  
- **识别服务 | Recognition**：Baidu OCR API

---

## 🚀 快速开始 | Quick Start

### ✅ 克隆项目 | Clone the repo

```bash
git clone https://github.com/HanchengZuo/SmartPlateX.git
cd SmartPlateX
```

### ✅ Docker 部署 | Deploy with Docker

项目已支持通过 Docker Compose 部署，容器内使用 Gunicorn 启动 Flask，并安装 `ffmpeg/ffprobe` 用于视频抽帧。

在项目根目录创建 `.env` 文件，配置百度 OCR Key：

```env
BAIDU_OCR_API_KEY=你的API_KEY
BAIDU_OCR_SECRET_KEY=你的SECRET_KEY
```

启动服务：

```bash
docker compose up -d --build
```

访问地址：

```text
http://服务器IP:5010
```

查看日志：

```bash
docker compose logs -f smartplatex
```

停止服务：

```bash
docker compose down
```

Docker Compose 会将以下运行时目录挂载到宿主机，容器重建后数据不会丢失：

- `uploads/`
- `frames/`
- `recognized/`
- `video_meta/`
- `logs/`

默认端口映射为 `5010:5000`，避免与其他 Flask 项目的 `5000` 端口冲突。

默认构建平台为 `linux/amd64`。如需覆盖，可在 `.env` 中设置 `DOCKER_PLATFORM=linux/arm64`。

### ✅ 本地开发 | Local development

#### 创建虚拟环境并安装依赖 | Create venv & install dependencies

```bash
python3 -m venv venv
source venv/bin/activate         # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

本地运行需要先安装 `ffmpeg`，并通过环境变量配置百度 OCR Key：

```bash
export BAIDU_OCR_API_KEY=你的API_KEY
export BAIDU_OCR_SECRET_KEY=你的SECRET_KEY
```

也兼容旧环境变量名 `BAIDU_API_KEY` 和 `BAIDU_SECRET_KEY`。

获取方式：https://console.bce.baidu.com/ai/#/ai/ocr/app/list

#### 启动项目 | Run the App

```bash
python app.py
```

访问地址：`http://127.0.0.1:5000`

### ✅ Docker 命令入口 | Docker command

```bash
docker compose up -d --build
```

访问地址：`http://服务器IP:5010`

---

## 📂 文件结构 | Project Structure

```
SmartPlateX/
├── app.py                     # 主程序入口 Main Flask app
├── Dockerfile                 # Docker 镜像构建文件
├── docker-compose.yml         # Docker Compose 部署配置
├── .dockerignore              # Docker 构建忽略规则
├── uploads/                  # 上传视频文件夹 Uploaded videos
├── frames/                   # 抽帧图像保存目录 Extracted frames
├── recognized/               # 识别结果（按视频 ID） Recognition results (JSON)
├── video_meta/               # 视频元信息 JSON Video metadata
├── logs/                     # 抽帧和识别日志 Logs
├── static/
│   ├── css/
│   └── js/
├── templates/
│   ├── index.html
│   └── statistics.html
├── requirements.txt
└── README.md
```

---

## 📊 数据统计说明 | Vehicle Type Logic

- `green` / `yellow_green` → 新能源车 EV
- 其他颜色（`blue`, `yellow`, 等） → 油车 Fuel

---

## 🔐 注意事项 | Notes

- 百度 OCR 接口有免费调用配额，超出需付费。
- 上传的视频格式推荐 `.mp4`，清晰度越高识别越准确。
- 抽帧频率建议：1~5 fps，防止过多无效帧。

---

## 💡 开发计划 | Future Plans

- ✅ 当前视频识别状态持久化展示  
- ✅ 识别进度条和日志监控  
- 🔄 增加多语言支持（支持中文车牌 + 英文 UI 切换）  
- ✅ 支持 Docker 部署与百度云 AK/环境变量分离  
- 📦 发布 Web Demo（GitHub Pages 或 Hugging Face Space）

---

## 📄 License

This project is open-source and released under the MIT License.

---

## 👨‍💻 作者 | Author

**Hancheng Zuo**  
[🌐 hanchengzuo.com](https://hanchengzuo.com)  
[🐙 GitHub @HanchengZuo](https://github.com/HanchengZuo)
