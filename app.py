from flask import (
    Flask,
    request,
    redirect,
    url_for,
    render_template,
    send_from_directory,
)
import os
import uuid
from datetime import datetime
import subprocess
import base64
import urllib.parse
import requests
import json
from collections import Counter
import cv2
from flask import jsonify

app = Flask(__name__)

# 上传视频保存路径
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

FRAME_FOLDER = "frames"
os.makedirs(FRAME_FOLDER, exist_ok=True)

RECOGNIZED_FOLDER = "recognized"
os.makedirs(RECOGNIZED_FOLDER, exist_ok=True)

VIDEO_META_FOLDER = "video_meta"
os.makedirs(VIDEO_META_FOLDER, exist_ok=True)

# 替换为你自己的 Key
BAIDU_API_KEY = "你的API_KEY"
BAIDU_SECRET_KEY = "你的SECRET_KEY"


# 首页路由
@app.route("/")
def index():
    # 获取分页参数
    video_page = int(request.args.get("video_page", 1))
    page = int(request.args.get("page", 1))

    # 视频列表（分页）
    videos, video_total_pages = get_video_list(page=video_page)

    # 所有帧图文件夹
    frame_dirs = [
        d
        for d in os.listdir(FRAME_FOLDER)
        if os.path.isdir(os.path.join(FRAME_FOLDER, d))
    ]

    # 统一处理选中的视频（支持 selected=xxx.mp4 或 video_id=xxx）
    selected_filename = request.args.get("selected")  # 含扩展名
    if selected_filename:
        selected_video_id = os.path.splitext(selected_filename)[0]
    elif request.args.get("video_id"):
        selected_video_id = request.args.get("video_id")
    else:
        selected_filename = None
        selected_video_id = None

    # 当前帧图列表（分页）
    frames, total_pages = (
        get_frame_list(selected_video_id, page=page) if selected_video_id else ([], 0)
    )

    # 始终尝试加载识别结果（如果有）
    results = []
    current_region_stats, current_color_stats = {}, {}
    if selected_video_id:
        result_file = os.path.join(RECOGNIZED_FOLDER, f"{selected_video_id}.json")
        if os.path.exists(result_file):
            with open(result_file, "r", encoding="utf-8") as f:
                results = json.load(f)
            current_region_stats, current_color_stats = get_video_statistics(
                selected_video_id
            )

    # 渲染首页模板
    return render_template(
        "index.html",
        videos=videos,
        video_page=video_page,
        video_total_pages=video_total_pages,
        frame_dirs=frame_dirs,
        selected_video_id=selected_video_id,
        selected_filename=selected_filename,
        frames=frames,
        page=page,
        total_pages=total_pages,
        results=results,
        current_region_stats=current_region_stats,
        current_color_stats=current_color_stats,
    )


def get_video_duration(path):
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        info = json.loads(result.stdout)
        return round(float(info["format"]["duration"]), 2)
    except Exception as e:
        print("⚠️ 获取时长失败", e)
        return None


# 上传视频处理路由
@app.route("/upload", methods=["POST"])
def upload_video():
    if "video" not in request.files:
        return "上传失败，未选择文件", 400

    file = request.files["video"]
    if file.filename == "":
        return "上传失败，文件名为空", 400

    # 保存视频
    filename = str(uuid.uuid4()) + ".mp4"
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(save_path)

    print(f"✅ 视频已保存：{save_path}")

    # 提取时长
    duration = get_video_duration(save_path)

    # 保存视频元信息
    meta = {
        "id": os.path.splitext(filename)[0],
        "original_filename": file.filename,
        "uploaded_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "duration": duration if duration else "未知",
    }
    with open(
        os.path.join(VIDEO_META_FOLDER, f"{meta['id']}.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    return redirect(url_for("index"))


# 工具函数：获取上传的视频文件列表，按创建时间倒序排列
def get_video_list(page=1, per_page=10):
    video_list = []
    for filename in os.listdir(UPLOAD_FOLDER):
        if filename.endswith(".mp4"):
            path = os.path.join(UPLOAD_FOLDER, filename)
            video_id = os.path.splitext(filename)[0]
            meta_path = os.path.join("video_meta", f"{video_id}.json")

            # 默认值
            original_name = filename
            duration = "未知"

            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    original_name = meta.get("original_filename", filename)
                    duration = meta.get("duration", "未知")

            created_time = os.path.getctime(path)
            video_list.append(
                {
                    "name": filename,
                    "url": url_for("uploaded_file", filename=filename),
                    "created_time": created_time,
                    "original_name": original_name,
                    "duration": duration,
                }
            )

    video_list.sort(key=lambda x: x["created_time"], reverse=True)
    total = len(video_list)
    start = (page - 1) * per_page
    end = start + per_page
    paged_videos = video_list[start:end]
    total_pages = (total + per_page - 1) // per_page

    return paged_videos, total_pages


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.template_filter("datetimeformat")
def datetimeformat(value):
    return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")


@app.route("/extract", methods=["POST"])
def extract_frames():
    video_filename = request.form.get("video_path")
    fps = int(request.form.get("fps"))

    video_path = os.path.join(app.config["UPLOAD_FOLDER"], video_filename)

    # 创建子文件夹路径：frames/<视频文件名不带扩展名>
    video_id = os.path.splitext(video_filename)[0]
    output_dir = os.path.join(FRAME_FOLDER, video_id)
    os.makedirs(output_dir, exist_ok=True)

    # 清空这个视频对应的帧图（可选）
    for f in os.listdir(output_dir):
        os.remove(os.path.join(output_dir, f))

    # 输出路径模式
    output_pattern = os.path.join(output_dir, "frame_%04d.jpg")

    # 调用 ffmpeg 抽帧
    cmd = ["ffmpeg", "-i", video_path, "-vf", f"fps={fps}", output_pattern]

    with open("logs/ffmpeg.log", "w") as log_file:
        subprocess.call(cmd, stdout=log_file, stderr=log_file)

    print(f"✅ 成功从 {video_filename} 抽帧到 {output_dir}")

    return redirect(url_for("index", selected=video_filename) + "#step4")


@app.route("/progress")
def get_progress():
    try:
        with open("logs/ffmpeg.log", "r") as f:
            content = f.read()
        return content[-2000:]  # 只返回最后一段，防止太大
    except Exception:
        return "暂无进度..."


def get_frame_list(video_id, page=1, per_page=20):
    frame_list = []
    frame_path = os.path.join(FRAME_FOLDER, video_id)

    if not os.path.exists(frame_path):
        return [], 0  # 返回空帧图和总页数0

    all_filenames = sorted([f for f in os.listdir(frame_path) if f.endswith(".jpg")])

    total = len(all_filenames)
    start = (page - 1) * per_page
    end = start + per_page
    paged_filenames = all_filenames[start:end]

    for filename in paged_filenames:
        frame_list.append(
            {
                "name": filename,
                "url": url_for("frame_file", video_id=video_id, filename=filename),
            }
        )

    total_pages = (total + per_page - 1) // per_page
    return frame_list, total_pages


@app.route("/frames/<video_id>/<filename>")
def frame_file(video_id, filename):
    return send_from_directory(os.path.join(FRAME_FOLDER, video_id), filename)


def get_baidu_access_token():
    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {
        "grant_type": "client_credentials",
        "client_id": BAIDU_API_KEY,
        "client_secret": BAIDU_SECRET_KEY,
    }
    res = requests.post(url, data=params)
    return res.json().get("access_token")


def recognize_plate(image_path, access_token):
    # 读取图像
    with open(image_path, "rb") as f:
        img_data = f.read()

    # 判断文件类型是否支持
    if not image_path.lower().endswith((".jpg", ".jpeg", ".png", ".bmp")):
        return {"error_msg": "图片格式错误，仅支持 JPG/PNG/JPEG/BMP"}

    # base64 + urlencode
    base64_str = base64.b64encode(img_data).decode("utf-8")
    image_encoded = urllib.parse.quote_plus(base64_str)

    # 构建请求
    url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/license_plate?access_token={access_token}"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = f"image={image_encoded}&multi_detect=true"

    # 发起 POST 请求
    response = requests.post(url, headers=headers, data=data.encode("utf-8"))
    return response.json()


@app.route("/recognize", methods=["POST"])
def recognize_all_frames():
    video_id = request.form.get("video_id")
    if not video_id:
        return "请选择要识别的视频帧图库", 400

    frame_path = os.path.join(FRAME_FOLDER, video_id)
    frame_list = sorted([f for f in os.listdir(frame_path) if f.endswith(".jpg")])
    total = len(frame_list)

    # 初始化进度记录
    progress_file = f"logs/recognition_progress.json"
    with open(progress_file, "w") as f:
        json.dump({"current": 0, "total": total}, f)

    access_token = get_baidu_access_token()
    results = []

    for i, filename in enumerate(frame_list):
        full_path = os.path.join(frame_path, filename)
        res = recognize_plate(full_path, access_token)
        words = res.get("words_result")
        if words and isinstance(words, list):
            for car in words:
                results.append(
                    {
                        "frame": filename,
                        "plate": car.get("number"),
                        "color": car.get("color"),
                        "confidence": round(sum(car.get("probability", [])) / 7, 4),
                        "raw": res,
                    }
                )

        with open(progress_file, "w") as f:
            json.dump({"current": i + 1, "total": total}, f)

    # 保存识别结果
    result_file = os.path.join(RECOGNIZED_FOLDER, f"{video_id}.json")
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    return redirect(url_for("index", video_id=video_id, recognized=1) + "#step5")


@app.route("/recognition_progress")
def recognition_progress():
    try:
        with open("logs/recognition_progress.json", "r") as f:
            data = json.load(f)
        return data
    except:
        return {"current": 0, "total": 1}


def extract_plate_region(plate_number):
    return (
        plate_number[0]
        if plate_number and "\u4e00" <= plate_number[0] <= "\u9fff"
        else "未知"
    )


def analyze_statistics(results):
    unique_plates = set()
    region_counter = Counter()
    color_counter = Counter()

    for r in results:
        plate = r.get("plate")
        color = r.get("color")
        if plate and plate not in unique_plates:
            unique_plates.add(plate)
            region = extract_plate_region(plate)
            region_counter[region] += 1
            color_counter[color] += 1

    return region_counter, color_counter


def get_video_statistics(video_id):
    result_path = os.path.join(RECOGNIZED_FOLDER, f"{video_id}.json")
    if os.path.exists(result_path):
        with open(result_path, "r", encoding="utf-8") as f:
            results = json.load(f)
        return analyze_statistics(results)
    return {}, {}


def get_global_statistics():
    all_results = []
    for filename in os.listdir(RECOGNIZED_FOLDER):
        if filename.endswith(".json"):
            with open(
                os.path.join(RECOGNIZED_FOLDER, filename), "r", encoding="utf-8"
            ) as f:
                all_results.extend(json.load(f))
    return analyze_statistics(all_results)


@app.route("/statistics")
def statistics():
    region_stats, color_stats = get_global_statistics()

    return render_template(
        "statistics.html", region_stats=region_stats, color_stats=color_stats
    )


@app.route("/api/video_stats/<video_id>")
def api_video_stats(video_id):
    result_path = os.path.join(RECOGNIZED_FOLDER, f"{video_id}.json")
    if not os.path.exists(result_path):
        return jsonify({"error": "未找到识别结果"}), 404

    region_stats, color_stats = get_video_statistics(video_id)

    return jsonify(
        {
            "regionLabels": list(region_stats.keys()),
            "regionValues": list(region_stats.values()),
            "colorLabels": list(color_stats.keys()),
            "colorValues": list(color_stats.values()),
        }
    )


# 后端提供全局统计的 API
@app.route("/api/global_stats")
def api_global_stats():
    region_stats, color_stats = get_global_statistics()
    return jsonify(
        {
            "regionLabels": list(region_stats.keys()),
            "regionValues": list(region_stats.values()),
            "colorLabels": list(color_stats.keys()),
            "colorValues": list(color_stats.values()),
        }
    )


# 启动 Flask
if __name__ == "__main__":
    app.run(debug=True)
