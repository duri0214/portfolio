document.addEventListener("DOMContentLoaded", () => {
    const mapElement = document.getElementById("commercial-area-map");
    const detailElement = document.getElementById("commercial-area-map-detail");
    const commercialDataElement = document.getElementById("commercial-area-map-data");

    if (!mapElement || !detailElement || !commercialDataElement || !window.jpmap) return;

    const commercialAreas = JSON.parse(commercialDataElement.textContent);
    const commercialAreaByCode = Object.fromEntries(
        commercialAreas.map((area) => [Number(area.code), area]),
    );
    const weatherColors = {
        good: { color: "#e4f4ec", hoverColor: "#c7ead8" },
        caution: { color: "#fff6d6", hoverColor: "#fde68a" },
        bad: { color: "#fee4e2", hoverColor: "#fecaca" },
        unknown: { color: "#f1f5f9", hoverColor: "#e2e8f0" },
    };
    const detailUrlTemplate = mapElement.dataset.detailUrlTemplate || "";

    const weatherPalette = (weatherCode) => {
        if (!weatherCode) return weatherColors.unknown;
        if (weatherCode.startsWith("3") || weatherCode.startsWith("4")) return weatherColors.bad;
        if (weatherCode.startsWith("2")) return weatherColors.caution;
        return weatherColors.good;
    };

    const mapAreas = commercialAreas.map((area) => {
        const palette = weatherPalette(area.weatherCode || "");
        return { code: area.code, color: palette.color, hoverColor: palette.hoverColor };
    });

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
                const area = commercialAreaByCode[Number(data.code)];
                if (!area || !detailUrlTemplate) return;
                window.location.assign(detailUrlTemplate.replace("999", area.code));
            },
        });
    } finally {
        if (window.nativeMapBeforeJpmap) window.Map = window.nativeMapBeforeJpmap;
    }
});
