document.addEventListener('DOMContentLoaded', function () {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl, {
            title: function () {
                var titleSelector = tooltipTriggerEl.getAttribute('data-bs-title');
                var titleTarget = document.querySelector(titleSelector);
                return titleTarget ? titleTarget.innerHTML : "";
            }
        })
    })
});
