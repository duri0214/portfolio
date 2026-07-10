document.addEventListener("DOMContentLoaded", () => {
    const dataElement = document.getElementById("livestock-distribution-data");
    const summaryElement = document.getElementById("livestock-summary");
    const mapElement = document.getElementById("livestock-prefecture-map");
    const detailElement = document.getElementById("livestock-map-detail");
    const categoryButtons = document.querySelectorAll(".livestock-category-button");

    if (
        !dataElement ||
        !summaryElement ||
        !mapElement ||
        !detailElement ||
        !window.jpmap
    ) {
        return;
    }

    const dashboard = JSON.parse(dataElement.textContent);
    const categoriesByKey = dashboard.categories.reduce((accumulator, category) => {
        accumulator[category.key] = category;
        return accumulator;
    }, {});
    let selectedCategoryKey = dashboard.categories[0].key;
    let hasPatchedJpmapPointerEvents = false;

    const patchJpmapPointerEvents = () => {
        const mapPrototype = window.jpmapInternalMap && window.jpmapInternalMap.prototype;
        if (!mapPrototype || hasPatchedJpmapPointerEvents) {
            return;
        }

        // japan-map-js uses offsetLeft/offsetTop, which breaks inside Bootstrap grids.
        mapPrototype.addEvent = function addEvent() {
            const map = this;
            const target = this.element;
            const updatePointer = (event) => {
                const rect = target.getBoundingClientRect();
                map.pointer = {
                    x: ((event.clientX - rect.left) * target.width) / rect.width,
                    y: ((event.clientY - rect.top) * target.height) / rect.height,
                };
            };

            target.addEventListener("mousemove", (event) => {
                updatePointer(event);
                map.render();
                if (!map.isHovering()) {
                    map.options.onHoverOut(map.data);
                }
            });
            target.addEventListener("mousedown", (event) => {
                updatePointer(event);
                map.render();
                if (map.data.code !== null && map.data.name !== null) {
                    setTimeout(() => map.options.onSelect(map.data), 0);
                }
                map.pointer = null;
            });
            target.addEventListener("mouseout", () => {
                map.pointer = null;
                map.render();
            });
        };
        hasPatchedJpmapPointerEvents = true;
    };

    const renderSummary = () => {
        summaryElement.replaceChildren();

        const comparisonCard = document.createElement("div");
        comparisonCard.className = "border rounded p-3 bg-light d-grid gap-3";

        const heading = document.createElement("div");
        heading.className = "d-grid gap-1";
        const title = document.createElement("strong");
        title.className = "text-dark";
        title.textContent = "全国羽数の内訳";
        const description = document.createElement("span");
        description.className = "small text-muted";
        description.textContent =
            "採卵鶏とブロイラーの全国羽数を足したうち、どちらが多いかを示します。";
        heading.append(title, description);

        const comparisonBar = document.createElement("div");
        comparisonBar.className = "progress";
        comparisonBar.style.height = "2rem";
        dashboard.categories.forEach((category) => {
            const segment = document.createElement("span");
            const colorClass =
                category.key === "broilers" ? "bg-warning text-dark" : "bg-primary";
            segment.className = `progress-bar ${colorClass}`;
            segment.style.width = `${category.share}%`;
            segment.textContent = `${category.label} ${category.share}%`;
            comparisonBar.append(segment);
        });

        const categoryList = document.createElement("div");
        categoryList.className = "table-responsive";
        const table = document.createElement("table");
        table.className = "table table-sm align-middle mb-0";
        const tableBody = document.createElement("tbody");
        dashboard.categories.forEach((category) => {
            const row = document.createElement("tr");

            const label = document.createElement("strong");
            label.textContent = category.label;
            const labelCell = document.createElement("th");
            labelCell.scope = "row";
            labelCell.className = "text-nowrap";
            labelCell.append(label);

            const birds = document.createElement("td");
            birds.textContent = `全国羽数 ${category.nationalBirdsLabel}`;
            const households = document.createElement("td");
            households.textContent = `飼養戸数 ${category.nationalHouseholdsLabel}`;
            const share = document.createElement("td");
            share.textContent = `2分類合計内の割合 ${category.share}%`;
            const tableNumber = document.createElement("td");
            tableNumber.textContent = `表番号 ${category.tableNumber}`;

            row.append(labelCell, birds, households, share, tableNumber);
            tableBody.append(row);
        });
        table.append(tableBody);
        categoryList.append(table);

        comparisonCard.append(heading, comparisonBar, categoryList);
        summaryElement.append(comparisonCard);
    };

    const getColor = (area, maxBirds) => {
        if (!area.birdsThousand) {
            return { color: "#e2e8f0", hoverColor: "#cbd5e1" };
        }

        const ratio = area.birdsThousand / maxBirds;
        if (ratio >= 0.66) {
            return { color: "#1f6f9f", hoverColor: "#195b83" };
        }
        if (ratio >= 0.33) {
            return { color: "#76b6d8", hoverColor: "#5aa4cd" };
        }
        return { color: "#d8edf9", hoverColor: "#b9def1" };
    };

    const renderDetail = (category, area) => {
        detailElement.replaceChildren();

        const title = document.createElement("strong");
        title.textContent = `${area.name}: ${category.label}`;

        const birds = document.createElement("span");
        birds.textContent = `飼養羽数 ${area.birdsLabel}`;

        const households = document.createElement("span");
        households.textContent = `飼養戸数 ${area.householdsLabel}`;

        const share = document.createElement("span");
        if (area.birdsThousand) {
            const nationalShare = (
                (area.birdsThousand / category.nationalBirdsThousand) *
                100
            ).toFixed(1);
            share.textContent = `分類内の全国比 ${nationalShare}%`;
        } else {
            share.textContent = "分類内の全国比 秘匿・該当なし";
        }

        const year = document.createElement("span");
        year.textContent = `対象年 ${dashboard.surveyYear}年 / 取得日 ${dashboard.retrievedAt}`;

        detailElement.append(title, birds, households, share, year);
    };

    const renderMap = () => {
        const category = categoriesByKey[selectedCategoryKey];
        const areas = dashboard.maps[selectedCategoryKey];
        const areaByCode = areas.reduce((accumulator, area) => {
            accumulator[Number(area.code)] = area;
            return accumulator;
        }, {});
        const maxBirds = Math.max(
            ...areas.map((area) => area.birdsThousand || 0)
        );
        const mapAreas = areas.map((area) => {
            const palette = getColor(area, maxBirds);
            return {
                code: area.code,
                color: palette.color,
                hoverColor: palette.hoverColor,
            };
        });

        mapElement.replaceChildren();
        detailElement.replaceChildren();
        const initialTitle = document.createElement("strong");
        initialTitle.textContent = `${category.label}の都道府県別分布`;
        const initialText = document.createElement("span");
        initialText.textContent = "地図から都道府県を選択";
        detailElement.append(initialTitle, initialText);

        try {
            if (window.jpmapInternalMap) {
                window.Map = window.jpmapInternalMap;
            }
            patchJpmapPointerEvents();
            window.jpmap.japanMap(mapElement, {
                areas: mapAreas,
                showsPrefectureName: true,
                movesIslands: true,
                width: Math.min(mapElement.clientWidth || 680, 720),
                borderLineColor: "#8795a1",
                borderLineWidth: 0.4,
                onSelect: (data) => {
                    const area = areaByCode[Number(data.code)];
                    if (area) {
                        renderDetail(category, area);
                    }
                },
            });
        } finally {
            if (window.nativeMapBeforeJpmap) {
                window.Map = window.nativeMapBeforeJpmap;
            }
        }
    };

    categoryButtons.forEach((button) => {
        button.addEventListener("click", () => {
            selectedCategoryKey = button.dataset.category;
            categoryButtons.forEach((item) => item.classList.remove("active"));
            button.classList.add("active");
            renderMap();
        });
    });

    renderSummary();
    renderMap();
});
