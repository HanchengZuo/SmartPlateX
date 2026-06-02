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
import hashlib
import hmac

import sys

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "local_models"))
)

from yolov8_plate.detect_and_recognize import detect_and_recognize_plate


app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def get_runtime_path(env_name, default_folder):
    path = os.environ.get(env_name, default_folder)
    if not os.path.isabs(path):
        path = os.path.join(BASE_DIR, path)
    return path


# 运行时数据目录，可通过环境变量覆盖，Docker 部署时会挂载为持久化目录。
UPLOAD_FOLDER = get_runtime_path("UPLOAD_FOLDER", "uploads")
FRAME_FOLDER = get_runtime_path("FRAME_FOLDER", "frames")
RECOGNIZED_FOLDER = get_runtime_path("RECOGNIZED_FOLDER", "recognized")
VIDEO_META_FOLDER = get_runtime_path("VIDEO_META_FOLDER", "video_meta")
LOG_FOLDER = get_runtime_path("LOG_FOLDER", "logs")

for folder in [
    UPLOAD_FOLDER,
    FRAME_FOLDER,
    RECOGNIZED_FOLDER,
    VIDEO_META_FOLDER,
    LOG_FOLDER,
]:
    os.makedirs(folder, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# 首页路由
@app.route("/")
def index():
    return render_template("index.html")


# 定义 Flask 路由 `/videos`，仅允许 GET 请求
@app.route("/videos", methods=["GET"])
def videos_page():
    video_data = get_selected_video_and_list()

    frames, total_pages = (
        get_frame_list(video_data["selected_video_id"], page=1, per_page=9999)
        if video_data["selected_video_id"]
        else ([], 0)
    )

    results = []
    current_region_stats, current_color_stats = {}, {}
    if video_data["selected_video_id"]:
        result_file = os.path.join(
            RECOGNIZED_FOLDER, f"{video_data['selected_video_id']}.json"
        )
        if os.path.exists(result_file):
            with open(result_file, "r", encoding="utf-8") as f:
                results = json.load(f)
            current_region_stats, current_color_stats = get_video_statistics(
                video_data["selected_video_id"]
            )

    return render_template(
        "videos.html",
        videos=video_data["videos"],
        video_page=video_data["video_page"],
        video_total_pages=video_data["video_total_pages"],
        selected_video_id=video_data["selected_video_id"],
        selected_filename=video_data["selected_filename"],
        frames=frames,
        total_pages=total_pages,
        results=results,
        current_region_stats=current_region_stats,
        current_color_stats=current_color_stats,
    )


def get_selected_video_and_list():
    # 从URL参数获取视频分页页码
    video_page = int(request.args.get("video_page", 1))

    # 从URL参数获取选中的视频文件名
    selected_filename = request.args.get("selected")

    # 根据文件名提取视频ID（不带.mp4扩展名），或者备用 video_id
    selected_video_id = (
        os.path.splitext(selected_filename)[0]
        if selected_filename
        else request.args.get("video_id")
    )

    # 获取当前页的视频列表和总页数
    videos, video_total_pages = get_video_list(page=video_page)

    return {
        "video_page": video_page,
        "selected_filename": selected_filename,
        "selected_video_id": selected_video_id,
        "videos": videos,
        "video_total_pages": video_total_pages,
    }


# 工具函数：获取上传的视频文件列表，并按创建时间倒序排序，支持分页
def get_video_list(page=1, per_page=10):
    video_list = []  # 用于存储所有视频的元数据信息

    # 遍历上传目录中的所有文件
    for filename in os.listdir(UPLOAD_FOLDER):
        # 只处理以 .mp4 结尾的文件（即视频）
        if filename.endswith(".mp4"):
            path = os.path.join(UPLOAD_FOLDER, filename)  # 视频文件完整路径
            video_id = os.path.splitext(filename)[0]  # 去掉扩展名得到 video_id
            meta_path = os.path.join(
                VIDEO_META_FOLDER, f"{video_id}.json"
            )  # 对应的视频元数据路径

            # 设置默认值（防止没有对应元数据文件时出错）
            original_name = filename  # 默认使用系统生成的文件名
            duration = "未知"  # 默认显示为“未知”时长

            # 如果存在对应的视频元数据文件，就读取原始文件名和时长
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    original_name = meta.get("original_filename", filename)
                    duration = meta.get("duration", "未知")

            # 获取视频文件的创建时间（用于排序）
            created_time = os.path.getctime(path)

            # 构造视频信息字典，并加入视频列表
            video_list.append(
                {
                    "name": filename,  # 系统内部使用的文件名（带 .mp4）
                    "url": url_for(
                        "uploaded_file", filename=filename
                    ),  # 访问该视频的 URL（用于下载或播放）
                    "created_time": created_time,  # 文件创建时间（用于排序）
                    "original_name": original_name,  # 上传时的原始文件名
                    "duration": duration,  # 视频时长（单位秒）
                }
            )

    # 按创建时间倒序排列视频（新上传的在最前面）
    video_list.sort(key=lambda x: x["created_time"], reverse=True)

    # 计算分页范围
    total = len(video_list)  # 视频总数量
    start = (page - 1) * per_page  # 当前页起始索引
    end = start + per_page  # 当前页结束索引

    # 获取当前页的视频子集
    paged_videos = video_list[start:end]

    # 计算总页数（向上取整）
    total_pages = (total + per_page - 1) // per_page

    # 返回：当前页的视频列表 + 总页数
    return paged_videos, total_pages


# 工具函数：获取指定视频的帧图列表，并支持分页
def get_frame_list(video_id, page=1, per_page=20):
    frame_list = []  # 用于存储当前页的帧图信息列表

    # 构造该视频的帧图文件夹路径，例如 frames/abc123/
    frame_path = os.path.join(FRAME_FOLDER, video_id)

    # 如果该目录不存在，则说明视频尚未抽帧，返回空列表和总页数 0
    if not os.path.exists(frame_path):
        return [], 0

    # 获取该目录下所有 jpg 格式的帧图文件，并按文件名排序
    all_filenames = sorted([f for f in os.listdir(frame_path) if f.endswith(".jpg")])

    # 计算总帧图数量
    total = len(all_filenames)

    # 计算分页的起止索引（默认每页 20 张）
    start = (page - 1) * per_page
    end = start + per_page

    # 取出当前页需要显示的帧图文件名
    paged_filenames = all_filenames[start:end]

    # 构造当前页每一张帧图的访问信息（包括文件名和 URL）
    for filename in paged_filenames:
        frame_list.append(
            {
                "name": filename,  # 帧图文件名，例如 frame_0001.jpg
                "url": url_for(
                    "frame_file", video_id=video_id, filename=filename
                ),  # 提供前端访问链接
            }
        )

    # 计算总页数（向上取整）
    total_pages = (total + per_page - 1) // per_page

    # 返回当前页的帧图信息 + 总页数
    return frame_list, total_pages


# 路由：提供帧图访问接口 —— 允许前端访问指定视频下的帧图文件
@app.route("/frames/<video_id>/<filename>")
def frame_file(video_id, filename):
    # 从 frames/<video_id>/ 目录中读取并返回指定帧图文件
    return send_from_directory(os.path.join(FRAME_FOLDER, video_id), filename)


# 定义路由 `/upload`，用于接收上传视频的 POST 请求
@app.route("/upload", methods=["POST"])
def upload_video():
    # 检查是否包含名为 "video" 的文件字段（来自前端 form 表单）
    if "video" not in request.files:
        return "上传失败，未选择文件", 400  # 返回 400 状态码表示请求错误

    # 从请求中获取上传的文件对象
    file = request.files["video"]

    # 如果用户上传了空文件（即文件名为空），也提示失败
    if file.filename == "":
        return "上传失败，文件名为空", 400

    # 使用 UUID 生成一个唯一的视频文件名，防止重名覆盖
    filename = str(uuid.uuid4()) + ".mp4"

    # 构建完整的保存路径：uploads/xxx.mp4
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    # 将上传的文件保存到服务器指定目录
    file.save(save_path)

    # 打印日志，提示上传成功及文件路径
    print(f"✅ 视频已保存：{save_path}")

    # 使用 ffprobe 提取视频时长（单位：秒）
    duration = get_video_duration(save_path)

    # 构建视频元信息字典
    meta = {
        "id": os.path.splitext(filename)[0],  # 视频唯一 ID（不含扩展名）
        "original_filename": file.filename,  # 用户上传的原始文件名
        "uploaded_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # 当前时间戳
        "duration": duration if duration else "未知",  # 视频时长，获取失败则设为“未知”
    }

    # 将元信息保存为 JSON 文件，文件名与视频一致，存入 video_meta 目录
    with open(
        os.path.join(VIDEO_META_FOLDER, f"{meta['id']}.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    # 重定向到 /recognize 页面（即 recognize_page 路由函数绑定的路径）
    return redirect(
        url_for(
            "recognize_page",  # ✅ 指向 Flask 中定义的函数 recognize_page（绑定的就是 /recognize 路由）
            selected=filename,  # ✅ 将刚刚上传的视频名作为参数 selected 传给前端（如 abc123.mp4）
        )
    )


# 函数：获取视频文件的时长（单位：秒）
def get_video_duration(path):
    try:
        # 使用 ffprobe 命令行工具，提取视频格式中的 duration 信息
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",  # 只显示错误，避免输出多余信息
                "-show_entries",
                "format=duration",  # 只提取视频总时长字段
                "-of",
                "json",  # 输出格式为 JSON 结构，方便解析
                path,  # 要处理的视频文件路径
            ],
            stdout=subprocess.PIPE,  # 捕获命令输出结果
            stderr=subprocess.PIPE,  # 捕获错误输出结果
            text=True,  # 将输出结果作为字符串返回（而不是字节流）
        )

        # 将 JSON 格式的输出结果反序列化为 Python 字典
        info = json.loads(result.stdout)

        # 从字典中提取 duration 字段并转换为 float，保留两位小数
        return round(float(info["format"]["duration"]), 2)

    except Exception as e:
        # 如果处理失败（比如视频格式不对、路径错误等），打印错误信息并返回 None
        print("⚠️ 获取时长失败", e)
        return None


# 路由：匹配 /uploads/<filename>，用于访问上传的原始视频文件
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    # 从上传目录中读取指定文件，并将其发送给浏览器（用于播放、下载等）
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


# 定义一个 Jinja2 模板过滤器，名字叫 "datetimeformat"
@app.template_filter("datetimeformat")
def datetimeformat(value):
    # 将时间戳转换为 "年-月-日 时:分:秒" 格式的字符串
    return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")


# 定义 Flask 路由 `/recognize`，用于处理 GET 请求
@app.route("/recognize", methods=["GET"])
def recognize_page():
    video_data = get_selected_video_and_list()

    results = []
    current_region_stats, current_color_stats = {}, {}
    if video_data["selected_video_id"]:
        result_file = os.path.join(
            RECOGNIZED_FOLDER, f"{video_data['selected_video_id']}.json"
        )
        if os.path.exists(result_file):
            with open(result_file, "r", encoding="utf-8") as f:
                results = json.load(f)
            current_region_stats, current_color_stats = get_video_statistics(
                video_data["selected_video_id"]
            )

    return render_template(
        "recognize.html",
        videos=video_data["videos"],
        video_page=video_data["video_page"],
        video_total_pages=video_data["video_total_pages"],
        selected_video_id=video_data["selected_video_id"],
        selected_filename=video_data["selected_filename"],
        results=results,
        current_region_stats=current_region_stats,
        current_color_stats=current_color_stats,
        baidu_ocr_configured=has_baidu_env_credentials(),
    )


# 定义路由 /progress，用于前端实时获取 ffmpeg 抽帧日志进度（通过轮询）
@app.route("/progress")
def get_progress():
    try:
        # 尝试读取 ffmpeg 抽帧日志文件（该文件由 /extract 路由生成）
        with open(os.path.join(LOG_FOLDER, "ffmpeg.log"), "r") as f:
            content = f.read()

        # 返回日志的最后 2000 个字符（避免整个日志太长，减轻前端负担）
        return content[-2000:]

    except Exception:
        # 如果文件不存在或读取失败，返回默认提示
        return "暂无进度..."


def get_baidu_env_credentials():
    api_key = (
        os.environ.get("BAIDU_OCR_API_KEY")
        or os.environ.get("BAIDU_API_KEY")
        or ""
    ).strip()
    secret_key = (
        os.environ.get("BAIDU_OCR_SECRET_KEY")
        or os.environ.get("BAIDU_SECRET_KEY")
        or ""
    ).strip()
    return api_key, secret_key


def has_baidu_env_credentials():
    api_key, secret_key = get_baidu_env_credentials()
    return bool(api_key and secret_key)


def get_baidu_credentials(api_key=None, secret_key=None):
    env_api_key, env_secret_key = get_baidu_env_credentials()
    return (
        env_api_key or (api_key or "").strip(),
        env_secret_key or (secret_key or "").strip(),
    )


# 工具函数：获取百度智能云的 Access Token（用于调用 OCR 接口）
def get_baidu_access_token(api_key=None, secret_key=None):
    """
    使用 AK，SK 生成鉴权签名（Access Token）
    :return: access_token，或是None(如果错误)
    """
    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {
        "grant_type": "client_credentials",
        "client_id": api_key,
        "client_secret": secret_key,
    }
    return str(requests.post(url, params=params).json().get("access_token"))


# 调用百度云车牌识别 API，对指定图片进行识别
def recognize_plate(image_path, access_token):
    # 读取图像的二进制内容
    with open(image_path, "rb") as f:
        img_data = f.read()

    # 判断图像格式是否合法（仅支持常见的位图格式）
    if not image_path.lower().endswith((".jpg", ".jpeg", ".png", ".bmp")):
        return {"error_msg": "图片格式错误，仅支持 JPG/PNG/JPEG/BMP"}

    # 将图像进行 base64 编码（API 要求）并进行 URL 编码
    base64_str = base64.b64encode(img_data).decode("utf-8")
    image_encoded = urllib.parse.quote_plus(base64_str)

    # 拼接百度车牌识别接口 URL（附带 access_token）
    url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/license_plate?access_token={access_token}"

    # 设置请求头（必须为 x-www-form-urlencoded）
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    # 设置请求体参数（包含图像内容和是否多车牌识别）
    data = f"image={image_encoded}&multi_detect=true"

    # 发送 POST 请求，进行识别
    response = requests.post(url, headers=headers, data=data.encode("utf-8"))

    # 返回识别结果（JSON 格式）
    return response.json()


def recognize_plate_by_tencent(image_path, secret_id, secret_key):
    # 读取图像并进行 base64 编码
    with open(image_path, "rb") as f:
        image_data = f.read()
    image_base64 = base64.b64encode(image_data).decode("utf-8")

    # 腾讯云通用参数
    service = "ocr"
    host = "ocr.tencentcloudapi.com"
    endpoint = f"https://{host}"
    region = "ap-guangzhou"
    action = "LicensePlateOCR"
    version = "2018-11-19"
    algorithm = "TC3-HMAC-SHA256"

    # 当前时间戳
    t = int(datetime.now().timestamp())
    date = datetime.utcnow().strftime("%Y-%m-%d")

    # 构造请求头部和正文
    payload = {"ImageBase64": image_base64}

    http_request_method = "POST"
    canonical_uri = "/"
    canonical_querystring = ""
    canonical_headers = f"content-type:application/json\nhost:{host}\n"
    signed_headers = "content-type;host"
    hashed_request_payload = hashlib.sha256(
        json.dumps(payload).encode("utf-8")
    ).hexdigest()
    canonical_request = "\n".join(
        [
            http_request_method,
            canonical_uri,
            canonical_querystring,
            canonical_headers,
            signed_headers,
            hashed_request_payload,
        ]
    )

    credential_scope = f"{date}/{service}/tc3_request"
    string_to_sign = "\n".join(
        [
            algorithm,
            str(t),
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )

    def sign(key, msg):
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    secret_date = sign(("TC3" + secret_key).encode("utf-8"), date)
    secret_service = sign(secret_date, service)
    secret_signing = sign(secret_service, "tc3_request")
    signature = hmac.new(
        secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    authorization = (
        f"{algorithm} Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json",
        "Host": host,
        "X-TC-Action": action,
        "X-TC-Version": version,
        "X-TC-Timestamp": str(t),
        "X-TC-Region": region,
    }

    response = requests.post(endpoint, headers=headers, json=payload)
    return response.json()


# 上传视频
@app.route("/recognize_upload_only", methods=["POST"])
def recognize_upload_only():
    file = request.files.get("video")
    if not file:
        return "未上传视频", 400

    # 保存到临时文件
    temp_filename = str(uuid.uuid4()) + ".mp4"
    temp_path = os.path.join(UPLOAD_FOLDER, temp_filename)
    file.save(temp_path)

    # 计算上传文件的 MD5 哈希
    video_hash = calculate_file_md5(temp_path)
    print(f"🔍 新上传视频 MD5: {video_hash}")

    # 检查是否有相同的哈希
    for meta_file in os.listdir(VIDEO_META_FOLDER):
        if meta_file.endswith(".json"):
            with open(
                os.path.join(VIDEO_META_FOLDER, meta_file), "r", encoding="utf-8"
            ) as f:
                meta = json.load(f)
                if meta.get("hash") == video_hash:
                    # 删除临时文件
                    os.remove(temp_path)
                    return jsonify({"error": "已存在相同的视频文件！请勿重复上传"}), 409

    # 没有重复，正式保存
    video_id = os.path.splitext(temp_filename)[0]
    duration = get_video_duration(temp_path)
    meta = {
        "id": video_id,
        "original_filename": file.filename,
        "uploaded_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "duration": duration if duration else "未知",
        "hash": video_hash,  # 🔥 保存哈希值
    }

    with open(
        os.path.join(VIDEO_META_FOLDER, f"{video_id}.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    return jsonify({"video_id": video_id})


@app.route("/extract", methods=["POST"])
def extract_frames():
    video_id = request.form.get("video_id")
    fps = request.form.get("fps", 1)

    print(f"🎬 [抽帧开始] video_id={video_id}, fps={fps}")

    video_path = os.path.join(UPLOAD_FOLDER, f"{video_id}.mp4")
    output_dir = os.path.join(FRAME_FOLDER, video_id)
    os.makedirs(output_dir, exist_ok=True)

    # 清空之前的帧图
    for f in os.listdir(output_dir):
        os.remove(os.path.join(output_dir, f))

    output_pattern = os.path.join(output_dir, "frame_%04d.jpg")

    log_path = os.path.join(LOG_FOLDER, "ffmpeg.log")
    os.makedirs(LOG_FOLDER, exist_ok=True)

    with open(log_path, "w") as log_file:
        process = subprocess.Popen(
            ["ffmpeg", "-i", video_path, "-vf", f"fps={fps}", output_pattern],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
        )

        # 把输出一行行写入日志
        for line in process.stdout:
            log_file.write(line)
            log_file.flush()

        # ✨ 关键！等待ffmpeg进程抽帧完成
        process.wait()

    print(f"✅ [抽帧完成] video_id={video_id}")

    return jsonify({"message": "抽帧完成"})


# 实际识别任务（在抽帧结束后调用）
@app.route("/recognize", methods=["POST"])
def recognize_all_frames():
    video_id = request.form.get("video_id")
    method = request.form.get("recognition_method")
    baidu_key = request.form.get("baidu_api_key")
    baidu_secret = request.form.get("baidu_secret_key")
    tencent_id = request.form.get("tencent_secret_id")
    tencent_key = request.form.get("tencent_secret_key")

    print(f"🛠️ [识别开始] video_id={video_id}, method={method}")

    output_dir = os.path.join(FRAME_FOLDER, video_id)
    frame_list = sorted([f for f in os.listdir(output_dir) if f.endswith(".jpg")])
    total = len(frame_list)

    print(f"🖼️ [抽帧图片总数] {total} 张")

    progress_file = os.path.join(LOG_FOLDER, "recognition_progress.json")
    with open(progress_file, "w") as f:
        json.dump({"current": 0, "total": total}, f)

    if method == "baidu":
        baidu_key, baidu_secret = get_baidu_credentials(baidu_key, baidu_secret)
        if not baidu_key or not baidu_secret:
            return jsonify({"error": "请配置百度 OCR API Key 和 Secret Key"}), 400
        access_token = get_baidu_access_token(baidu_key, baidu_secret)
        print("🔑 [Baidu AccessToken] 获取成功")
    elif method == "tencent":
        print("🔑 [使用腾讯云识别]")
    elif method == "yolo":
        print("🔑 [使用本地YOLO识别]")
    else:
        print("⚠️ 未知识别方法")
        return jsonify({"error": "未知识别方法"}), 400

    results = []
    for i, frame_file in enumerate(frame_list):
        full_path = os.path.join(output_dir, frame_file)
        print(f"🔍 正在识别第 {i+1}/{total} 张: {frame_file}")
        try:
            if method == "baidu":
                res = recognize_plate(full_path, access_token)
                words = res.get("words_result")
                if words and isinstance(words, list):
                    for car in words:
                        results.append(
                            {
                                "frame": frame_file,
                                "plate": car.get("number"),
                                "color": car.get("color"),
                                "confidence": round(
                                    sum(car.get("probability", [])) / 7, 4
                                ),
                                "raw": res,
                            }
                        )
            elif method == "tencent":
                res = recognize_plate_by_tencent(full_path, tencent_id, tencent_key)
                license_plates = res.get("Response", {}).get("LicensePlateInfos", [])
                for car in license_plates:
                    results.append(
                        {
                            "frame": frame_file,
                            "plate": car.get("Number"),
                            "color": car.get("Color"),
                            "confidence": car.get("Confidence"),
                            "raw": res,
                        }
                    )
            elif method == "yolo":
                res = detect_and_recognize_plate(full_path)
                for car in res:
                    results.append(
                        {
                            "frame": frame_file,
                            "plate": car["number"],
                            "color": car["color"],
                            "confidence": "NA",  # ✅ 置信度填NA
                            "raw": res,
                        }
                    )
        except Exception as e:
            print(f"⚠️ 第 {i+1} 张识别失败: {e}")

        # 更新识别进度
        with open(progress_file, "w") as f:
            json.dump({"current": i + 1, "total": total}, f)

    # 保存识别结果
    recognized_path = os.path.join(RECOGNIZED_FOLDER, f"{video_id}.json")
    with open(recognized_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"✅ [识别完成] 总计识别出 {len(results)} 条车牌")
    print(f"📁 [结果已保存] {recognized_path}")

    return jsonify({"video_id": video_id})


# 路由：获取车牌识别进度（供前端识别进度条实时展示）
@app.route("/recognition_progress")
def recognition_progress():
    try:
        # 尝试读取识别进度 JSON 文件
        with open(os.path.join(LOG_FOLDER, "recognition_progress.json"), "r") as f:
            data = json.load(f)

        # 返回当前进度数据，例如 {"current": 12, "total": 50}
        return data

    except:
        # 如果文件不存在或读取失败，返回默认占位值，防止前端出错
        return {"current": 0, "total": 1}


# 工具函数：提取车牌号的“所属地区简称”（即第一个汉字）
def extract_plate_region(plate_number):
    return (
        plate_number[0]  # 如果车牌号存在且第一个字符是中文，返回该字符（如“沪”、“粤”）
        if plate_number and "\u4e00" <= plate_number[0] <= "\u9fff"
        else "未知"  # 否则返回“未知”（可能是识别失败或格式错误）
    )


# 工具函数：统计识别结果中的不同地区车牌数量与颜色数量（去重后）
def analyze_statistics(results):
    unique_plates = set()  # 用于记录已识别的唯一车牌号，避免重复计数
    region_counter = Counter()  # 地区统计器（如：沪、粤、京...）
    color_counter = Counter()  # 颜色统计器（如：blue、green...）

    # 遍历所有识别结果
    for r in results:
        plate = r.get("plate")  # 获取车牌号
        color = r.get("color")  # 获取车牌颜色

        # 如果车牌号有效，且尚未统计过（去重）
        if plate and plate not in unique_plates:
            unique_plates.add(plate)  # 标记为已处理
            region = extract_plate_region(plate)  # 提取省份简称（如“沪”）
            region_counter[region] += 1  # 地区计数 +1
            color_counter[color] += 1  # 颜色计数 +1

    # 返回两个 Counter 结果：地区分布、颜色分布
    return region_counter, color_counter


# 获取指定视频的车牌识别统计结果（地区/颜色分布）
def get_video_statistics(video_id):
    # 构造识别结果文件路径，如 recognized/abc123.json
    result_path = os.path.join(RECOGNIZED_FOLDER, f"{video_id}.json")

    # 如果识别结果文件存在
    if os.path.exists(result_path):
        # 读取该视频的识别结果 JSON 文件
        with open(result_path, "r", encoding="utf-8") as f:
            results = json.load(f)

        # 调用分析函数，返回地区分布和颜色分布（已去重）
        return analyze_statistics(results)

    # 否则返回空统计
    return {}, {}


# 汇总所有视频的识别结果，计算全局的车牌统计数据
def get_global_statistics():
    all_results = []  # 存储所有视频的识别结果

    # 遍历 recognized/ 文件夹下所有 .json 文件
    for filename in os.listdir(RECOGNIZED_FOLDER):
        if filename.endswith(".json"):
            # 打开并读取每个识别结果文件的内容
            with open(
                os.path.join(RECOGNIZED_FOLDER, filename), "r", encoding="utf-8"
            ) as f:
                all_results.extend(json.load(f))  # 将其加入总列表中

    # 对所有视频识别结果做统计分析（合并统计）
    return analyze_statistics(all_results)


# 路由：展示全局车牌识别统计页面（汇总所有视频的统计结果）
@app.route("/statistics")
def statistics():
    # 调用工具函数，获取所有识别结果中的地区与颜色统计数据
    region_stats, color_stats = get_global_statistics()

    # 渲染 statistics.html 页面，并传入统计数据用于图表展示
    return render_template(
        "statistics.html",  # 模板路径
        region_stats=region_stats,  # 地区分布数据（如“沪”、“粤”、“浙”等）
        color_stats=color_stats,  # 颜色分布数据（如“blue”、“green”等）
    )


# API 路由：返回指定视频的车牌识别统计数据（地区/颜色）
@app.route("/api/video_stats/<video_id>")
def api_video_stats(video_id):
    # 构造该视频的识别结果文件路径（JSON 文件）
    result_path = os.path.join(RECOGNIZED_FOLDER, f"{video_id}.json")

    # 如果文件不存在，返回 404 错误
    if not os.path.exists(result_path):
        return jsonify({"error": "未找到识别结果"}), 404

    # 获取该视频的地区与颜色统计数据（调用封装函数）
    region_stats, color_stats = get_video_statistics(video_id)

    # 将统计结果以 JSON 格式返回（供前端图表使用）
    return jsonify(
        {
            "regionLabels": list(
                region_stats.keys()
            ),  # 地区标签，如 ["沪", "粤", "浙"]
            "regionValues": list(region_stats.values()),  # 地区对应数量，如 [5, 3, 2]
            "colorLabels": list(color_stats.keys()),  # 颜色标签，如 ["blue", "green"]
            "colorValues": list(color_stats.values()),  # 颜色对应数量，如 [6, 4]
        }
    )


# 后端提供全局统计的 API（供前端图表使用）
@app.route("/api/global_stats")
def api_global_stats():
    # 获取所有视频的识别结果统计（地区分布 & 颜色分布）
    region_stats, color_stats = get_global_statistics()

    # 返回 JSON 格式的数据，供前端 Chart.js 渲染使用
    return jsonify(
        {
            "regionLabels": list(
                region_stats.keys()
            ),  # 地区标签（如["沪", "粤", "浙"]）
            "regionValues": list(region_stats.values()),  # 对应数量（如 [10, 6, 2]）
            "colorLabels": list(color_stats.keys()),  # 颜色标签（如["blue", "green"]）
            "colorValues": list(color_stats.values()),  # 对应数量（如 [8, 4]）
        }
    )


@app.route("/delete_video", methods=["POST"])
def delete_video():
    filename = request.form.get("video_filename")

    if not filename:
        return "未提供视频文件名", 400

    video_id = os.path.splitext(filename)[0]

    # 要删除的文件和文件夹列表
    paths_to_delete = [
        os.path.join(UPLOAD_FOLDER, filename),  # 上传的视频
        os.path.join(VIDEO_META_FOLDER, f"{video_id}.json"),  # 视频元数据
        os.path.join(RECOGNIZED_FOLDER, f"{video_id}.json"),  # 识别结果
    ]

    # 删除单个文件
    for path in paths_to_delete:
        if os.path.exists(path):
            os.remove(path)

    # 删除帧图文件夹
    frame_folder = os.path.join(FRAME_FOLDER, video_id)
    if os.path.exists(frame_folder):
        for f in os.listdir(frame_folder):
            os.remove(os.path.join(frame_folder, f))
        os.rmdir(frame_folder)

    print(f"🗑️ 已成功删除视频及相关数据：{video_id}")

    return redirect(url_for("videos_page"))


def calculate_file_md5(filepath):
    """计算一个文件的 MD5 值"""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


# 启动 Flask
if __name__ == "__main__":
    app.run(debug=True)
