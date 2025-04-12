function showLoading() {
  const submitBtn = document.querySelector('#step3 button[type="submit"]');
  submitBtn.disabled = true;
  submitBtn.textContent = "抽帧中...";
  document.getElementById('loading').style.display = 'block';
}


function showLoading() {
  const submitBtn = document.querySelector('#step3 button[type="submit"]');
  submitBtn.disabled = true;
  submitBtn.textContent = "抽帧中...";
  document.getElementById('loading').style.display = 'block';

  // 启动轮询日志进度
  const logEl = document.getElementById('progress-log');
  setInterval(() => {
    fetch('/progress')
      .then(res => res.text())
      .then(data => {
        logEl.textContent = data;
        logEl.scrollTop = logEl.scrollHeight; // 自动滚动到底部
      });
  }, 1000);
}

function startRecognitionProgress() {
  const statusEl = document.getElementById("recognition-status");
  const textEl = document.getElementById("recognition-text");
  const progressEl = document.getElementById("recognition-progress");

  statusEl.style.display = "block";

  const interval = setInterval(() => {
    fetch("/recognition_progress")
      .then(res => res.json())
      .then(data => {
        const percent = (data.current / data.total) * 100;
        progressEl.value = percent;
        textEl.textContent = `正在识别：${data.current} / ${data.total}`;
        if (data.current >= data.total) {
          clearInterval(interval);
          textEl.textContent = "识别完成！即将刷新页面...";
        }
      });
  }, 1000);
}

document.addEventListener("DOMContentLoaded", function () {
  const regionCanvas = document.getElementById("regionChart");
  const colorCanvas = document.getElementById("colorChart");

  if (!regionCanvas || !colorCanvas) return;

  // 从当前页面 URL 中获取 video_id 参数
  const urlParams = new URLSearchParams(window.location.search);
  const videoId = urlParams.get("video_id") || urlParams.get("selected")?.replace(".mp4", "");
  if (!videoId) {
    console.warn("未指定 video_id，跳过图表渲染");
    return;
  }

  fetch(`/api/video_stats/${videoId}`)
    .then((res) => res.json())
    .then((data) => {
      if (data.error) {
        console.warn("API 错误：", data.error);
        return;
      }

      const regionLabels = data.regionLabels;
      const regionValues = data.regionValues;
      const colorLabels = data.colorLabels;
      const colorValues = data.colorValues;

      let fuelCount = 0;
      let evCount = 0;

      colorLabels.forEach((color, idx) => {
        const count = colorValues[idx];
        if (color === "green" || color === "yellow_green") {
          evCount += count;
        } else {
          fuelCount += count;
        }
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
});


