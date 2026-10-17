document.addEventListener("DOMContentLoaded", () => {
    const mapElement = document.getElementById("commercial-area-map");
    const detailElement = document.getElementById("commercial-area-map-detail");
    const commercialDataElement = document.getElementById("commercial-area-map-data");
    const soilDataElement = document.getElementById("soil-map-data");
    const modeToggle = document.getElementById("soil-map-mode");
    const sourceElement = document.getElementById("soil-map-source");
    const weatherLegendElement = document.getElementById("weather-map-legend");
    const soilLegendElement = document.getElementById("soil-map-legend");

    if (!mapElement || !detailElement || !commercialDataElement || !soilDataElement || !modeToggle || !sourceElement || !weatherLegendElement || !soilLegendElement || !window.jpmap) return;

    const commercialAreas = JSON.parse(commercialDataElement.textContent);
    const soilMap = JSON.parse(soilDataElement.textContent);
    const commercialAreaByCode = Object.fromEntries(commercialAreas.map((area) => [Number(area.code), area]));
    const soilAreaByCode = Object.fromEntries(soilMap.areas.map((area) => [Number(area.code), area]));
    const weatherColors = {
        good: { color: "#e4f4ec", hoverColor: "#c7ead8" },
        caution: { color: "#fff6d6", hoverColor: "#fde68a" },
        bad: { color: "#fee4e2", hoverColor: "#fecaca" },
        unknown: { color: "#f1f5f9", hoverColor: "#e2e8f0" },
    };
    const detailUrlTemplate = mapElement.dataset.detailUrlTemplate || "";
    const soilDetailUrlTemplate = mapElement.dataset.soilDetailUrlTemplate || "";

    const weatherPalette = (weatherCode) => {
        if (!weatherCode) return weatherColors.unknown;
        if (weatherCode.startsWith("3") || weatherCode.startsWith("4")) return weatherColors.bad;
        if (weatherCode.startsWith("2")) return weatherColors.caution;
        return weatherColors.good;
    };

    const showCommercialDetail = (area) => {
        detailElement.replaceChildren();
        const title = document.createElement("strong");
        title.textContent = `${area.name}: ${area.weatherName}`;
        const jmaArea = document.createElement("span");
        jmaArea.textContent = `エリア ${area.jmaAreaName || "未設定"}`;
        const summary = document.createElement("span");
        summary.textContent = `圃場 ${area.landCount}圃場 / 企業 ${area.companyCount}社 / 登録作物 ${area.cropSummary}`;
        const risk = document.createElement("span");
        risk.textContent = `予報日 ${area.weatherReportingDate || "未取得"} / 警報・注意報 ${area.warningSummary}`;
        const detailLink = document.createElement("a");
        detailLink.className = "btn btn-sm btn-primary justify-self-start mt-2";
        detailLink.href = detailUrlTemplate.replace("999", area.code);
        detailLink.textContent = "詳細ページへ";
        detailElement.append(title, jmaArea, summary, risk, detailLink);
    };

    const showMapModeGuide = (isSoilMode) => {
        detailElement.replaceChildren();
        const title = document.createElement("strong");
        const summary = document.createElement("span");
        if (isSoilMode) {
            title.textContent = "地図から都道府県を選択";
            summary.textContent = "市区町村ごとの土壌面積・構成比を確認できます。";
        } else {
            title.textContent = "地図から都道府県を選択";
            summary.textContent = "商圏の集計値を確認できます。";
        }
        detailElement.append(title, summary);
    };

    const renderLegend = (isSoilMode) => {
        weatherLegendElement.hidden = isSoilMode;
        soilLegendElement.hidden = !isSoilMode;
        if (!isSoilMode) return;

        soilLegendElement.replaceChildren();
        const title = document.createElement("span");
        title.textContent = "主な土壌群:";
        soilLegendElement.append(title);
        for (const item of soilMap.legend || []) {
            const legendItem = document.createElement("span");
            const dot = document.createElement("i");
            dot.className = "legend-dot";
            dot.style.backgroundColor = item.color;
            dot.style.borderColor = item.hoverColor;
            const label = document.createElement("a");
            label.href = item.soilGroupUrl;
            label.target = "_blank";
            label.rel = "noopener noreferrer";
            label.textContent = `${item.soilGroupName}（${item.soilGroupCode}）`;
            legendItem.append(dot, label);
            soilLegendElement.append(legendItem);
        }
    };

    const renderMap = () => {
        const isSoilMode = modeToggle.checked;
        showMapModeGuide(isSoilMode);
        renderLegend(isSoilMode);
        const mapAreas = isSoilMode
            ? soilMap.areas.map((area) => ({ code: area.code, color: area.color, hoverColor: area.hoverColor }))
            : commercialAreas.map((area) => {
                const palette = weatherPalette(area.weatherCode || "");
                return { code: area.code, color: palette.color, hoverColor: palette.hoverColor };
            });

        sourceElement.hidden = !isSoilMode;
        if (isSoilMode) {
            sourceElement.replaceChildren();
            if (soilMap.dataset) {
                const link = document.createElement("a");
                link.href = soilMap.dataset.sourceUrl;
                link.target = "_blank";
                link.rel = "noopener noreferrer";
                link.textContent = "農研機構 日本土壌インベントリー（縮尺20万分の1土壌図、CC BY 4.0）";
                const excludedSummary = soilMap.dataset.excludedFeatureCount
                    ? ` / 属性未設定の除外: ${soilMap.dataset.excludedFeatureCount.toLocaleString()}件`
                    : "";
                sourceElement.append("出典: ", link, ` / ファイル: ${soilMap.dataset.sourceFileName} / 取込: ${new Date(soilMap.dataset.importedAt).toLocaleString("ja-JP")} / 地物数: ${soilMap.dataset.featureCount.toLocaleString()}件${excludedSummary}`);
            } else {
                sourceElement.textContent = "土壌図はまだ取り込まれていません。管理者が全国Shape ZIPを登録すると表示されます。";
            }
        }

        mapElement.replaceChildren();
        try {
            if (window.jpmapInternalMap) window.Map = window.jpmapInternalMap;
            window.jpmap.japanMap(mapElement, {
                areas: mapAreas,
                showsPrefectureName: true,
                movesIslands: true,
                width: Math.min(mapElement.clientWidth || 720, 760),
                borderLineColor: "#8795a1",
                borderLineWidth: 0.4,
                onSelect: (data) => {
                    const area = isSoilMode ? soilAreaByCode[Number(data.code)] : commercialAreaByCode[Number(data.code)];
                    if (!area) return;
                    if (isSoilMode && soilDetailUrlTemplate) {
                        window.location.assign(soilDetailUrlTemplate.replace("999", area.code));
                        return;
                    }
                    showCommercialDetail(area);
                },
            });
        } finally {
            if (window.nativeMapBeforeJpmap) window.Map = window.nativeMapBeforeJpmap;
        }
    };

    modeToggle.addEventListener("change", renderMap);
    renderMap();
});
