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

### ✅ 创建虚拟环境并安装依赖 | Create venv & install dependencies

```bash
python3 -m venv venv
source venv/bin/activate         # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### ✅ 设置百度 OCR API 密钥 | Configure Baidu OCR Keys

在 `app.py` 中替换以下字段为你自己的百度 OCR 密钥：

```python
BAIDU_API_KEY = "你的API_KEY"
BAIDU_SECRET_KEY = "你的SECRET_KEY"
```

获取方式：https://console.bce.baidu.com/ai/#/ai/ocr/app/list

### ✅ 启动项目 | Run the App

```bash
python app.py
```

访问地址：`http://127.0.0.1:5000`

---

## 📂 文件结构 | Project Structure

```
SmartPlateX/
├── app.py                     # 主程序入口 Main Flask app
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
- ⬆️ 支持 Docker 部署与百度云 AK/配置文件分离  
- 📦 发布 Web Demo（GitHub Pages 或 Hugging Face Space）

---

## 📄 License

This project is open-source and released under the MIT License.

---

## 👨‍💻 作者 | Author

**Hancheng Zuo**  
[🌐 hanchengzuo.com](https://hanchengzuo.com)  
[🐙 GitHub @HanchengZuo](https://github.com/HanchengZuo)

