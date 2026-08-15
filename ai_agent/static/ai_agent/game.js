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
});
