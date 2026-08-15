document.addEventListener("DOMContentLoaded", () => {
    const board = document.querySelector("[data-game-board]");
    if (!board) {
        return;
    }

    board.style.setProperty("--board-size", board.dataset.boardSize || "3");
    board.querySelectorAll(".board-piece-form").forEach((form) => {
        form.addEventListener("submit", () => {
            const button = form.querySelector("button");
            if (button) {
                button.classList.add("is-selected");
                button.disabled = true;
            }
        });
    });

    const progress = document.querySelector("[data-agent-progress]");
    const agentForms = document.querySelectorAll("[data-agent-form]");
    const progressBar = document.querySelector("[data-agent-progress-bar]");
    const progressText = document.querySelector("[data-agent-progress-text]");
    const progressSteps = [
        { value: 25, text: "セリフを確認しています。" },
        { value: 50, text: "利用するToolを選んでいます。" },
        { value: 75, text: "Toolを実行しています。" },
        { value: 90, text: "結果をゲーム状態へ反映しています。" },
    ];

    agentForms.forEach((form) => {
        form.addEventListener("submit", () => {
            if (!progress) {
                return;
            }
            progress.classList.remove("d-none");
            agentForms.forEach((agentForm) => {
                const button = agentForm.querySelector("[data-agent-submit]");
                if (button) {
                    button.disabled = true;
                }
            });
            let stepIndex = 0;
            const updateProgress = () => {
                const step = progressSteps[stepIndex];
                progressBar.style.width = `${step.value}%`;
                progressBar.parentElement.setAttribute("aria-valuenow", step.value);
                progressText.textContent = step.text;
                stepIndex = Math.min(stepIndex + 1, progressSteps.length - 1);
            };
            updateProgress();
            window.setInterval(updateProgress, 700);
        });
    });
});
