document.addEventListener('DOMContentLoaded', function () {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        var titleSelector = tooltipTriggerEl.getAttribute('data-bs-title');
        var titleTarget = document.querySelector(titleSelector);
        var titleHtml = titleTarget ? titleTarget.innerHTML : "";
        return new bootstrap.Tooltip(tooltipTriggerEl, {
            title: titleHtml
        })
    })
});
