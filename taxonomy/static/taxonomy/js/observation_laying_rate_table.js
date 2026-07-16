function initializeObservationLayingRateTable() {
    const filterButtons = document.querySelectorAll(".observation-feed-filter");
    const rows = document.querySelectorAll(".observation-table-card tbody tr[data-feed-group]");
    if (!filterButtons.length || !rows.length) {
        return;
    }

    filterButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const selectedFeedGroup = button.dataset.feedGroup;
            filterButtons.forEach((item) => {
                item.classList.toggle("active", item === button);
                item.classList.toggle("btn-primary", item === button);
                item.classList.toggle("btn-outline-primary", item !== button);
            });

            rows.forEach((row) => {
                const shouldShow = selectedFeedGroup === "all" || row.dataset.feedGroup === selectedFeedGroup;
                row.classList.toggle("d-none", !shouldShow);
            });
        });
    });
}

document.addEventListener("DOMContentLoaded", initializeObservationLayingRateTable);
