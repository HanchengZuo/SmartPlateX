document.addEventListener("DOMContentLoaded", () => {
    fetch("/api/global_stats")
        .then((res) => res.json())
        .then((data) => {
            const regionLabels = data.regionLabels;
            const regionValues = data.regionValues;
            const colorLabels = data.colorLabels;
            const colorValues = data.colorValues;

            // 渲染文本列表
            const regionList = document.getElementById("regionList");
            regionList.innerHTML = regionLabels.map((r, i) => `<li>${r}：${regionValues[i]}</li>`).join("");

            const colorList = document.getElementById("colorList");
            colorList.innerHTML = colorLabels.map((c, i) => `<li>${c}：${colorValues[i]}</li>`).join("");

            // 车辆类型统计
            let fuelCount = 0;
            let evCount = 0;
            colorLabels.forEach((color, i) => {
                const count = colorValues[i];
                if (color === "green" || color === "yellow_green") {
                    evCount += count;
                } else {
                    fuelCount += count;
                }
            });

            // 地区图表
            new Chart(document.getElementById("allRegionChart"), {
                type: "bar",
                data: {
                    labels: regionLabels,
                    datasets: [{
                        label: "地区车牌数量（全部视频）",
                        data: regionValues,
                        backgroundColor: "rgba(75, 192, 192, 0.6)"
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { display: false },
                        title: { display: true, text: "全部视频 - 地区分布" }
                    },
                    scales: {
                        y: { beginAtZero: true, ticks: { precision: 0 } }
                    }
                }
            });

            // 车辆类型图表
            new Chart(document.getElementById("vehicleTypeChart"), {
                type: "bar",
                data: {
                    labels: ["油车", "新能源车"],
                    datasets: [{
                        label: "车辆类型统计（全部视频）",
                        data: [fuelCount, evCount],
                        backgroundColor: ["#444444", "#00CC66"]
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { display: false },
                        title: { display: true, text: "全部视频 - 车辆类型分布" }
                    },
                    scales: {
                        y: { beginAtZero: true, ticks: { precision: 0 } }
                    }
                }
            });
        });
});
