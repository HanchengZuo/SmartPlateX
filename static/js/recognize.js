document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("recognize-form");
    let latestVideoId = null;

    // 文件选择后展示参数配置
    const fileInput = document.getElementById("video-input");
    const configSection = document.getElementById("config-section");
    if (fileInput && configSection) {
        fileInput.addEventListener("change", function () {
            configSection.style.display = fileInput.files.length > 0 ? "block" : "none";
        });
    }

    if (form) {
        form.addEventListener("submit", async function (e) {
            e.preventDefault();

            const loadingDiv = document.getElementById("loading");
            const recognitionDiv = document.getElementById("recognition-status");
            if (loadingDiv) loadingDiv.style.display = "block";
            if (recognitionDiv) recognitionDiv.style.display = "none";

            const formData = new FormData(form);

            // 第一步：上传视频（只保存，不识别）
            const uploadRes = await fetch("/recognize_upload_only", {
                method: "POST",
                body: formData
            });

            if (!uploadRes.ok) {
                const errorData = await uploadRes.json();
                alert(errorData.error || "上传失败！");
                // 停止后续流程
                if (loadingDiv) loadingDiv.style.display = "none";   // ✅ 加这一行
                if (recognitionDiv) recognitionDiv.style.display = "none";  // ✅ 加这一行（双保险）
                return;
            }

            const uploadData = await uploadRes.json();
            const videoId = uploadData.video_id;

            // ✅ 抽帧之前，开始轮询 logs/ffmpeg.log
            startPollingFfmpegLog();

            // 第二步：请求开始抽帧（同步等待后端返回）
            const extractRes = await fetch("/extract", {
                method: "POST",
                body: new URLSearchParams({
                    video_id: videoId,
                    fps: formData.get("fps")
                })
            });
            const extractData = await extractRes.json();

            // ✅ 抽帧结束后，停止轮询 logs/ffmpeg.log
            stopPollingFfmpegLog();

            if (!extractRes.ok) {
                alert("抽帧失败，请检查视频格式！");
                return;
            }
            console.log("🎬 抽帧完成：", extractData.message);

            // 第三步：开始识别（显示识别进度条）
            recognitionDiv.style.display = "block";
            pollRecognitionProgress(() => {
                // 识别结束后的回调（跳转到结果页）
                window.location.href = "/recognize?selected=" + encodeURIComponent(videoId + ".mp4");
            });

            const recogForm = new FormData();
            recogForm.append("video_id", videoId);
            recogForm.append("recognition_method", formData.get("recognition_method"));
            recogForm.append("baidu_api_key", formData.get("baidu_api_key"));
            recogForm.append("baidu_secret_key", formData.get("baidu_secret_key"));
            recogForm.append("tencent_secret_id", formData.get("tencent_secret_id"));
            recogForm.append("tencent_secret_key", formData.get("tencent_secret_key"));

            const recogRes = await fetch("/recognize", {
                method: "POST",
                body: recogForm
            });

            if (!recogRes.ok) {
                alert("识别接口出错！");
            }

        });
    }

    const methodSelect = document.querySelector('select[name="recognition_method"]');
    if (methodSelect) {
        toggleAPIConfig(methodSelect.value);
        methodSelect.addEventListener("change", function () {
            toggleAPIConfig(this.value);
        });
    }

    // 渲染图表逻辑（如果存在）
    const regionCanvas = document.getElementById("regionChart");
    const colorCanvas = document.getElementById("colorChart");

    if (regionCanvas && colorCanvas) {
        const urlParams = new URLSearchParams(window.location.search);
        const videoId = urlParams.get("video_id") || urlParams.get("selected")?.replace(".mp4", "");

        if (videoId) {
            fetch(`/api/video_stats/${videoId}`)
                .then(res => res.json())
                .then(data => {
                    if (data.error) return;

                    const regionLabels = data.regionLabels;
                    const regionValues = data.regionValues;
                    const colorLabels = data.colorLabels;
                    const colorValues = data.colorValues;

                    let fuelCount = 0;
                    let evCount = 0;

                    colorLabels.forEach((color, i) => {
                        const count = colorValues[i];
                        if (color === "green" || color === "yellow_green") evCount += count;
                        else fuelCount += count;
                    });

                    const vehicleTypeData = {
                        labels: ["油车", "新能源车"],
                        datasets: [{
                            label: "车辆类型",
                            data: [fuelCount, evCount],
                            backgroundColor: ["#444", "#00CC66"]
                        }]
                    };

                    new Chart(regionCanvas, {
                        type: "bar",
                        data: {
                            labels: regionLabels,
                            datasets: [{
                                label: "地区车牌数量",
                                data: regionValues,
                                backgroundColor: "rgba(54, 162, 235, 0.6)"
                            }]
                        },
                        options: {
                            responsive: true,
                            plugins: {
                                legend: { display: false },
                                title: { display: true, text: "不同地区车牌数量" }
                            },
                            scales: {
                                y: { beginAtZero: true, ticks: { precision: 0 } }
                            }
                        }
                    });

                    new Chart(colorCanvas, {
                        type: "bar",
                        data: vehicleTypeData,
                        options: {
                            responsive: true,
                            plugins: {
                                legend: { display: false },
                                title: { display: true, text: "车辆类型统计（当前视频）" }
                            },
                            scales: {
                                y: { beginAtZero: true, ticks: { precision: 0 } }
                            }
                        }
                    });
                });
        }
    }
});

function toggleAPIConfig(value) {
    const baiduDiv = document.getElementById('baidu-config');
    const tencentDiv = document.getElementById('tencent-config');
    const yoloWarn = document.getElementById('yolo-warning');

    // 全部先隐藏
    if (baiduDiv) baiduDiv.style.display = 'none';
    if (tencentDiv) tencentDiv.style.display = 'none';
    if (yoloWarn) yoloWarn.style.display = 'none';

    // 先移除所有字段的 required
    document.getElementById('baidu_api_key')?.removeAttribute('required');
    document.getElementById('baidu_secret_key')?.removeAttribute('required');
    document.querySelector('input[name="tencent_secret_id"]')?.removeAttribute('required');
    document.querySelector('input[name="tencent_secret_key"]')?.removeAttribute('required');

    // 再根据 value 显示对应块 + 添加 required
    if (value === 'baidu' && baiduDiv) {   // ✅这里要加 && baiduDiv
        baiduDiv.style.display = 'block';
        document.getElementById('baidu_api_key')?.setAttribute('required', 'required');
        document.getElementById('baidu_secret_key')?.setAttribute('required', 'required');
    } else if (value === 'tencent' && tencentDiv) {  // ✅这里加 && tencentDiv
        tencentDiv.style.display = 'block';
        document.querySelector('input[name="tencent_secret_id"]')?.setAttribute('required', 'required');
        document.querySelector('input[name="tencent_secret_key"]')?.setAttribute('required', 'required');
    } else if (value === 'yolo' && yoloWarn) {  // ✅这里加 && yoloWarn
        yoloWarn.style.display = 'block';
    }
}


function pollRecognitionProgress(onComplete) {
    const bar = document.getElementById("recognition-progress");
    const text = document.getElementById("recognition-text");

    const interval = setInterval(() => {
        fetch("/recognition_progress")
            .then(res => res.json())
            .then(data => {
                bar.max = data.total;
                bar.value = data.current;
                text.textContent = `识别中 (${data.current}/${data.total})`;
                if (data.current >= data.total) {
                    clearInterval(interval);
                    if (onComplete) onComplete();  // ✅ 识别完成后执行回调
                }
            });
    }, 1000);
}

let ffmpegLogInterval = null;  // 全局变量，保存定时器

function startPollingFfmpegLog() {
    const loadingDiv = document.getElementById("loading");
    if (!loadingDiv) return;

    ffmpegLogInterval = setInterval(() => {
        fetch("/progress")
            .then(res => res.text())
            .then(log => {
                loadingDiv.textContent = "⏳ 正在抽帧中...\n\n" + log;
            })
            .catch(() => {
                loadingDiv.textContent = "⏳ 正在抽帧中...（日志获取失败）";
            });
    }, 1000);
}

function stopPollingFfmpegLog() {
    if (ffmpegLogInterval) {
        clearInterval(ffmpegLogInterval);
        ffmpegLogInterval = null;
    }
}


