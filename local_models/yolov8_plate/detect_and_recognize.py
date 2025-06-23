import torch
from ultralytics import YOLO
import cv2
import os
import sys

# 加载 plate_recognition 模型
sys.path.append(os.path.dirname(__file__))
from plate_recognition.plate_rec import init_model, get_plate_result

# 设备
device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")

# 初始化模型（全局只加载一次）
det_model_path = os.path.join(os.path.dirname(__file__), "weights/yolov8s.pt")
rec_model_path = os.path.join(os.path.dirname(__file__), "weights/plate_rec_color.pth")

det_model = YOLO(det_model_path)
rec_model = init_model(device, rec_model_path, is_color=True)  # 这里用 init_model 返回


def detect_and_recognize_plate(image_path):
    results = []
    img = image_path

    # 1. 检测车牌
    det_res = det_model.predict(img, conf=0.5, iou=0.5, imgsz=640)

    for plate in det_res[0].boxes.xyxy.cpu().numpy():
        x1, y1, x2, y2 = map(int, plate)

        frame = cv2.imread(img)

        # 2. 裁剪车牌
        plate_crop = frame[y1:y2, x1:x2]
        if plate_crop.size == 0:
            continue

        # 3. 识别车牌
        number, _, color, _ = get_plate_result(
            plate_crop, device, rec_model, is_color=True
        )

        print(f"原始识别结果：车牌号={number}，颜色={color}")

        # 4. 保存结果
        results.append({"number": number, "color": color})

    return results
