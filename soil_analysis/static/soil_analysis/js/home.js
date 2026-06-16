document.addEventListener("DOMContentLoaded", () => {
    const mapElement = document.getElementById("commercial-area-map");
    const detailElement = document.getElementById("commercial-area-map-detail");
    const dataElement = document.getElementById("commercial-area-map-data");

    if (!mapElement || !detailElement || !dataElement || !window.jpmap) {
        return;
    }

    const commercialAreas = JSON.parse(dataElement.textContent);
    const areaByCode = new Map(commercialAreas.map((area) => [Number(area.code), area]));
    const colors = {
        "area-active": { color: "#e4f4ec", hoverColor: "#c7ead8" },
        "area-risk": { color: "#fde9dc", hoverColor: "#fbd0b6" },
        "area-empty": { color: "#f1f5f9", hoverColor: "#e2e8f0" },
    };
    const mapAreas = commercialAreas.map((area) => {
        const palette = colors[area.statusClass] || colors["area-empty"];
        return {
            code: area.code,
            color: palette.color,
            hoverColor: palette.hoverColor,
        };
    });

    const renderDetail = (area) => {
        detailElement.replaceChildren();

        const title = document.createElement("strong");
        title.textContent = `${area.name}: ${area.status}`;

        const summary = document.createElement("span");
        summary.textContent = `圃場 ${area.landCount} / 企業 ${area.companyCount} / 主要作物 ${area.mainCropName}`;

        const risk = document.createElement("span");
        risk.textContent = `天気 ${area.weatherName} / 出荷信号 ${area.shippingSignalIcon} ${area.shippingSignalMessage} / 警報 ${area.warningCount} / Risk ${area.riskScore}`;

        detailElement.append(title, summary, risk);
    };

    new window.jpmap.japanMap(mapElement, {
        areas: mapAreas,
        showsPrefectureName: true,
        movesIslands: true,
        width: Math.min(mapElement.clientWidth || 720, 760),
        borderLineColor: "#8795a1",
        borderLineWidth: 0.4,
        onSelect: (data) => {
            const area = areaByCode.get(Number(data.code));
            if (area) {
                renderDetail(area);
            }
        },
    });
});
