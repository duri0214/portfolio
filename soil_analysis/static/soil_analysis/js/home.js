document.addEventListener("DOMContentLoaded", () => {
    const mapElement = document.getElementById("commercial-area-map");
    const detailElement = document.getElementById("commercial-area-map-detail");
    const dataElement = document.getElementById("commercial-area-map-data");

    if (!mapElement || !detailElement || !dataElement || !window.jpmap) {
        return;
    }

    const commercialAreas = JSON.parse(dataElement.textContent);
    const areaByCode = commercialAreas.reduce((accumulator, area) => {
        accumulator[Number(area.code)] = area;
        return accumulator;
    }, {});
    const colors = {
        good: { color: "#e4f4ec", hoverColor: "#c7ead8" },
        caution: { color: "#fff6d6", hoverColor: "#fde68a" },
        bad: { color: "#fee4e2", hoverColor: "#fecaca" },
        unknown: { color: "#f1f5f9", hoverColor: "#e2e8f0" },
    };
    const getWeatherPalette = (weatherCode) => {
        if (!weatherCode) {
            return colors.unknown;
        }
        if (weatherCode.startsWith("3") || weatherCode.startsWith("4")) {
            return colors.bad;
        }
        if (weatherCode.startsWith("2")) {
            return colors.caution;
        }
        return colors.good;
    };
    const mapAreas = commercialAreas.map((area) => {
        const palette = getWeatherPalette(area.weatherCode || "");
        return {
            code: area.code,
            color: palette.color,
            hoverColor: palette.hoverColor,
        };
    });

    const renderDetail = (area) => {
        detailElement.replaceChildren();

        const title = document.createElement("strong");
        title.textContent = `${area.name}: ${area.weatherName}`;

        const summary = document.createElement("span");
        summary.textContent = `圃場 ${area.landCount}圃場 / 企業 ${area.companyCount}社 / 主要作物 ${area.mainCropName}`;

        const risk = document.createElement("span");
        risk.textContent = `予報日 ${area.weatherReportingDate || "未取得"} / 警報・注意報 ${area.warningSummary}`;

        detailElement.append(title, summary, risk);
    };

    try {
        if (window.jpmapInternalMap) {
            window.Map = window.jpmapInternalMap;
        }
        window.jpmap.japanMap(mapElement, {
            areas: mapAreas,
            showsPrefectureName: true,
            movesIslands: true,
            width: Math.min(mapElement.clientWidth || 720, 760),
            borderLineColor: "#8795a1",
            borderLineWidth: 0.4,
            onSelect: (data) => {
                const area = areaByCode[Number(data.code)];
                if (area) {
                    renderDetail(area);
                }
            },
        });
    } finally {
        if (window.nativeMapBeforeJpmap) {
            window.Map = window.nativeMapBeforeJpmap;
        }
    }
});
