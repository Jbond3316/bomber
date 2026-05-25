const phoneInput = document.getElementById("phone");
const sendAllCheck = document.getElementById("sendAll");
const catalogEl = document.getElementById("catalog");
const statusEl = document.getElementById("status");
const logEl = document.getElementById("log");

let catalog = null;

function setStatus(text, kind = "idle") {
  statusEl.textContent = text;
  statusEl.className = `status ${kind}`;
}

function getPhone() {
  return phoneInput.value.replace(/\D/g, "").slice(-10);
}

function renderCatalog(data) {
  catalog = data;
  const order = ["sms", "whatsapp", "call"];
  const labels = { sms: "SMS (MSService)", whatsapp: "WhatsApp (TOAService)", call: "Call / IVR (VSService)" };
  catalogEl.innerHTML = order
    .map((type) => {
      const items = data[type] || [];
      const rows = items
        .map(
          (ep) => `
        <div class="endpoint">
          <strong>${ep.method}</strong> ${ep.name}<br />
          <span>${ep.url}</span>
          <br />
          <button type="button" data-type="${type}" data-index="${ep.index}">Send to this only</button>
        </div>`
        )
        .join("");
      return `<div class="catalog-group ${type}"><h3>${labels[type]} (${items.length})</h3>${rows || "<p>No endpoints</p>"}</div>`;
    })
    .join("");

  catalogEl.querySelectorAll("button[data-type]").forEach((btn) => {
    btn.addEventListener("click", () => {
      runSend(btn.dataset.type, Number(btn.dataset.index), false);
    });
  });
}

async function loadCatalog() {
  try {
    const res = await fetch("/api/catalog");
    const data = await res.json();
    renderCatalog(data);
  } catch (e) {
    catalogEl.textContent = "Failed to load catalog: " + e.message;
  }
}

async function runSend(type, index = 0, all = sendAllCheck.checked) {
  const phone = getPhone();
  if (phone.length !== 10) {
    setStatus("Please enter a 10-digit mobile number.", "err");
    return;
  }

  document.querySelectorAll(".btn").forEach((b) => (b.disabled = true));
  setStatus(`Sending ${type.toUpperCase()} requests…`, "loading");
  logEl.textContent = "";

  try {
    const res = await fetch("/api/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type, phone, index, all }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || res.statusText);
    }

    const okCount = data.results.filter((r) => r.ok).length;
    setStatus(
      `Done: ${okCount}/${data.results.length} succeeded for ${type}.`,
      okCount ? "ok" : "err"
    );
    logEl.textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    setStatus(e.message, "err");
    logEl.textContent = String(e.stack || e);
  } finally {
    document.querySelectorAll(".btn").forEach((b) => (b.disabled = false));
  }
}

document.querySelectorAll(".btn[data-type]").forEach((btn) => {
  btn.addEventListener("click", () => runSend(btn.dataset.type, 0));
});

phoneInput.addEventListener("input", () => {
  phoneInput.value = phoneInput.value.replace(/\D/g, "").slice(0, 10);
});

loadCatalog();
