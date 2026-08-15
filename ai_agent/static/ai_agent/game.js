document.addEventListener("DOMContentLoaded", () => {
    const setupBoard = () => {
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
    };
    setupBoard();

    const progressTitle = document.querySelector("[data-agent-progress-title]");
    const progressSpinner = document.querySelector("[data-agent-spinner]");
    const agentForms = document.querySelectorAll("[data-agent-form]");
    const progressBar = document.querySelector("[data-agent-progress-bar]");
    const progressText = document.querySelector("[data-agent-progress-text]");
    const currentTool = document.querySelector("[data-agent-current-tool]");
    const csrfToken = (form) => form.querySelector("[name=csrfmiddlewaretoken]").value;

    const setProgress = (value, text) => {
        progressTitle.textContent = value >= 100 ? "Agentの処理が完了しました" : "Agentが処理しています";
        progressSpinner.classList.toggle("d-none", value >= 100);
        progressBar.classList.remove("bg-secondary", "bg-success");
        progressBar.classList.add(value >= 100 ? "bg-success" : "bg-primary");
        progressBar.style.width = `${value}%`;
        progressBar.parentElement.setAttribute("aria-valuenow", value);
        progressText.textContent = text;
    };

    const setCurrentTool = (status, event) => {
        const name = textValue(event.display_name, event.tool_name);
        currentTool.textContent = `${status}: ${name}`;
    };

    const textValue = (value, fallback = "") => {
        if (value === null || value === undefined) {
            return fallback;
        }
        if (typeof value === "object") {
            return JSON.stringify(value);
        }
        return String(value);
    };

    const handleAgentEvent = (event) => {
        if (event.type === "run.started") {
            setProgress(35, "Agentが利用するToolを選んでいます。");
        } else if (event.type === "tool.selected") {
            setCurrentTool("発生", event);
            setProgress(50, `${textValue(event.display_name, event.tool_name)}を実行します。`);
        } else if (event.type === "tool.started") {
            setCurrentTool("実行中", event);
            setProgress(65, `${textValue(event.display_name, event.tool_name)}を処理しています。`);
        } else if (event.type === "tool.completed" || event.type === "tool.failed") {
            setCurrentTool(event.type === "tool.completed" ? "完了" : "失敗", event);
            setProgress(75, "Skillの結果をゲーム状態へ反映しています。");
        } else if (event.type === "report.completed") {
            setProgress(90, "実行結果を保存しています。");
            return event.state_token;
        }
        return null;
    };

    const readSse = async (response, onEvent) => {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let stateToken = null;
        const consume = (block) => {
            const dataLine = block.split("\n").find((line) => line.startsWith("data: "));
            if (!dataLine) {
                return;
            }
            const token = onEvent(JSON.parse(dataLine.slice(6)));
            if (token) {
                stateToken = token;
            }
        };
        while (true) {
            const { value, done } = await reader.read();
            buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
            const blocks = buffer.split("\n\n");
            buffer = blocks.pop();
            blocks.filter(Boolean).forEach(consume);
            if (done) {
                if (buffer.trim()) {
                    consume(buffer);
                }
                break;
            }
        }
        return stateToken;
    };

    const saveStreamState = async (form, stateToken) => {
        const endpoint = form.getAttribute("action") || window.location.href;
        const body = new URLSearchParams({
            action: "save_stream_state",
            state_token: stateToken,
            csrfmiddlewaretoken: csrfToken(form),
        });
        const response = await fetch(endpoint, {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken(form) },
            body,
        });
        if (!response.ok) {
            throw new Error("実行結果を保存できませんでした。");
        }
        return response.text();
    };

    const refreshPersistedState = (html) => {
        const nextDocument = new DOMParser().parseFromString(html, "text/html");
        ["[data-agent-messages]", "[data-game-board]", "[data-game-experience]", "[data-execution-history]"].forEach((selector) => {
            const current = document.querySelector(selector);
            const next = nextDocument.querySelector(selector);
            if (current && next) {
                current.replaceWith(next);
            }
        });
        setupBoard();
    };

    agentForms.forEach((form) => {
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            agentForms.forEach((agentForm) => {
                const button = agentForm.querySelector("[data-agent-submit]");
                if (button) {
                    button.disabled = true;
                }
            });
            try {
                const endpoint = form.getAttribute("action") || window.location.href;
                const response = await fetch(endpoint, {
                    method: "POST",
                    headers: { Accept: "text/event-stream" },
                    body: new FormData(form),
                });
                if (!response.ok) {
                    throw new Error(`Agent実行開始に失敗しました (HTTP ${response.status})`);
                }
                if (!response.body) {
                    throw new Error("Agent実行のストリームを受信できませんでした。");
                }
                const stateToken = await readSse(response, handleAgentEvent);
                if (!stateToken) {
                    throw new Error("Agent実行の完了状態を受け取れませんでした。");
                }
                const savedPage = await saveStreamState(form, stateToken);
                refreshPersistedState(savedPage);
                setProgress(100, "実行結果を表示しています。");
            } catch (error) {
                const reason = error instanceof Error ? error.message : String(error);
                console.error("Agent streaming failed", error);
                setProgress(100, `Agent実行に失敗しました: ${reason}`);
                progressTitle.textContent = "Agent実行に失敗しました";
                progressBar.classList.remove("bg-success");
                progressBar.classList.add("bg-danger");
            }
        });
    });
});
