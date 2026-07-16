(() => {
  const WS_URL = "ws://localhost:8765";

  // ── Shadow DOM host (isolates our styles from the host page) ─────────────
  const host = document.createElement("div");
  host.id = "cluely-overlay-host";
  host.style.position = "fixed";
  host.style.top = "16px";
  host.style.left = "16px";
  host.style.zIndex = "2147483647"; // max z-index — sits above page content
  document.documentElement.appendChild(host);

  const shadow = host.attachShadow({ mode: "open" });
  shadow.innerHTML = `
    <style>
      .container {
        width: 360px;
        background: rgba(12, 12, 14, 0.92);
        border-radius: 14px;
        border: 1px solid rgba(255, 255, 255, 0.07);
        padding: 14px 18px;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        color: #f0f0f5;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
      }
      .header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
      .label { color: rgba(120, 120, 130, 0.86); font-size: 10px; letter-spacing: 1px; }
      .status { color: rgba(99, 102, 241, 0.86); font-size: 10px; }
      .transcript { color: rgba(170, 170, 185, 0.82); font-size: 11px; line-height: 1.4; margin-bottom: 8px; max-height: 48px; overflow: hidden; }
      .divider { border-top: 1px solid rgba(255, 255, 255, 0.05); margin-bottom: 8px; }
      .response { font-size: 13px; line-height: 1.5; margin-bottom: 10px; min-height: 20px; white-space: pre-wrap; }
      .bottom { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
      button {
        background: rgba(50, 50, 58, 0.78); color: rgba(180, 180, 190, 0.78);
        border: none; border-radius: 5px; padding: 3px 10px; font-size: 11px; cursor: pointer;
      }
      button:hover { background: rgba(70, 70, 80, 0.78); }
      button.active { background: rgba(99, 102, 241, 0.86); color: white; font-weight: 600; }
      button.primary { background: rgba(99, 102, 241, 0.86); color: white; font-weight: 600; margin-left: auto; }
    </style>
    <div class="container">
      <div class="header-row">
        <span class="label" id="conn-label">● CONNECTING…</span>
        <span class="status" id="status"></span>
      </div>
      <div class="transcript" id="transcript">Waiting for speech…</div>
      <div class="divider"></div>
      <div class="response" id="response"></div>
      <div class="bottom" id="backend-buttons"></div>
    </div>
  `;

  const el = {
    connLabel: shadow.getElementById("conn-label"),
    status: shadow.getElementById("status"),
    transcript: shadow.getElementById("transcript"),
    response: shadow.getElementById("response"),
    backendButtons: shadow.getElementById("backend-buttons"),
  };

  let availableBackends = [];
  let activeBackend = null;
  let ws = null;

  function send(payload) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(payload));
    }
  }

  function renderButtons() {
    el.backendButtons.innerHTML = "";
    for (const name of availableBackends) {
      const btn = document.createElement("button");
      btn.textContent = name;
      if (name === activeBackend) btn.classList.add("active");
      btn.addEventListener("click", () => send({ type: "switch_backend", name }));
      el.backendButtons.appendChild(btn);
    }

    const trigger = document.createElement("button");
    trigger.textContent = "Run";
    trigger.classList.add("primary");
    trigger.addEventListener("click", () => send({ type: "trigger" }));
    el.backendButtons.appendChild(trigger);

    const pause = document.createElement("button");
    pause.textContent = "Pause/Resume";
    pause.addEventListener("click", () => send({ type: "toggle_pause" }));
    el.backendButtons.appendChild(pause);
  }

  function connect() {
    ws = new WebSocket(WS_URL);

    ws.addEventListener("open", () => {
      el.connLabel.textContent = "● LISTENING";
    });

    ws.addEventListener("close", () => {
      el.connLabel.textContent = "● DISCONNECTED";
      setTimeout(connect, 3000);
    });

    ws.addEventListener("error", () => {
      el.connLabel.textContent = "● DISCONNECTED";
    });

    ws.addEventListener("message", (event) => {
      let msg;
      try {
        msg = JSON.parse(event.data);
      } catch {
        return;
      }
      switch (msg.type) {
        case "transcript":
          el.transcript.textContent = msg.text;
          break;
        case "response":
          el.response.textContent = msg.text;
          break;
        case "status":
          el.status.textContent = msg.text || "";
          break;
        case "backends":
          availableBackends = msg.available || [];
          if (!activeBackend) activeBackend = availableBackends[0] || null;
          renderButtons();
          break;
        case "backend":
          activeBackend = msg.active;
          renderButtons();
          break;
      }
    });
  }

  renderButtons();
  connect();
})();
