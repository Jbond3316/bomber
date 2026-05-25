const express = require("express");
const path = require("path");
const fs = require("fs");

const app = express();
const PORT = process.env.PORT || 3000;
const APIs = JSON.parse(
  fs.readFileSync(path.join(__dirname, "apis.json"), "utf8")
);

app.use(express.json({ limit: "1mb" }));
app.use(express.static(path.join(__dirname, "public")));

function normalizePhone(raw) {
  const digits = String(raw).replace(/\D/g, "");
  if (!digits || digits.length < 10) {
    throw new Error("Enter a valid phone number (at least 10 digits).");
  }
  let local = digits;
  if (local.startsWith("91") && local.length >= 12) {
    local = local.slice(2);
  }
  if (local.length > 10) {
    local = local.slice(-10);
  }
  return {
    digits: local,
    e164: `+91${local}`,
    plus91: `+91${local}`,
    raw10: local,
  };
}

function applyPhone(template, phone) {
  if (!template) return null;
  return template
    .replace(/\{phone\}/g, phone.raw10)
    .replace(/\{e164\}/g, phone.e164)
    .replace(/\{plus91\}/g, phone.plus91);
}

function applyPhoneToUrl(url, phone) {
  return url
    .replace(/\{phone\}/g, phone.raw10)
    .replace(/\{e164\}/g, encodeURIComponent(phone.e164))
    .replace(/\{plus91\}/g, encodeURIComponent(phone.plus91));
}

function defaultBody(endpoint, phone) {
  const u = endpoint.url.toLowerCase();
  if (endpoint.contentType?.includes("x-www-form-urlencoded")) {
    return `phone=${phone.raw10}&mobile=${phone.raw10}`;
  }
  if (u.includes("whatsapp")) {
    return JSON.stringify({
      phone: phone.raw10,
      country_code: "+91",
      countryCode: "91",
    });
  }
  return JSON.stringify({
    phone: phone.raw10,
    mobile: phone.raw10,
    phone_number: phone.plus91,
    phoneNumber: phone.raw10,
    country_code: "+91",
    countryCode: "91",
  });
}

function buildQueryParams(endpoint, phone) {
  const params = new URLSearchParams();
  const qp = endpoint.queryParams;
  if (!qp) return params;

  if (Array.isArray(qp)) {
    for (const key of qp) {
      params.set(key, key.includes("phone") ? phone.raw10 : "null");
    }
    return params;
  }

  for (const [key, value] of Object.entries(qp)) {
    params.set(key, applyPhone(String(value), phone));
  }
  return params;
}

async function fireRequest(endpoint, phone) {
  let url = applyPhoneToUrl(endpoint.url, phone);
  const method = (endpoint.method || "POST").toUpperCase();
  const headers = {
    Accept: "application/json, text/plain, */*",
    "User-Agent":
      "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36",
    ...(endpoint.headers || {}),
  };

  const init = { method, headers, redirect: "follow" };

  if (method === "GET") {
    const extra = buildQueryParams(endpoint, phone);
    if ([...extra.keys()].length) {
      url += (url.includes("?") ? "&" : "?") + extra.toString();
    }
  } else {
    const bodyStr =
      applyPhone(endpoint.bodyTemplate, phone) ?? defaultBody(endpoint, phone);
    init.body = bodyStr;
    if (endpoint.contentType) {
      headers["Content-Type"] = endpoint.contentType;
    } else if (bodyStr.trim().startsWith("{")) {
      headers["Content-Type"] = "application/json";
    }
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(url, { ...init, signal: controller.signal });
    const text = await res.text();
    let json = null;
    try {
      json = JSON.parse(text);
    } catch {
      /* plain text body */
    }
    return {
      ok: res.ok,
      status: res.status,
      statusText: res.statusText,
      url,
      method,
      body: json ?? text.slice(0, 2000),
    };
  } finally {
    clearTimeout(timeout);
  }
}

app.get("/api/catalog", (_req, res) => {
  const summary = {};
  for (const [type, list] of Object.entries(APIs)) {
    summary[type] = list.map((e, i) => ({
      index: i,
      name: e.name,
      url: e.url,
      method: e.method,
      hasBodyTemplate: Boolean(e.bodyTemplate),
    }));
  }
  res.json(summary);
});

app.post("/api/send", async (req, res) => {
  try {
    const { type, phone, index, all } = req.body || {};
    if (!["sms", "whatsapp", "call"].includes(type)) {
      return res.status(400).json({ error: "type must be sms, whatsapp, or call" });
    }
    const normalized = normalizePhone(phone);
    const list = APIs[type] || [];
    if (!list.length) {
      return res.status(404).json({ error: `No endpoints for type: ${type}` });
    }

    const targets =
      all === true
        ? list
        : [list[Number(index) ?? 0]].filter(Boolean);

    const results = [];
    for (const endpoint of targets) {
      try {
        const result = await fireRequest(endpoint, normalized);
        results.push({ name: endpoint.name, ...result });
      } catch (err) {
        results.push({
          name: endpoint.name,
          ok: false,
          error: err.message,
          url: endpoint.url,
        });
      }
    }

    res.json({
      type,
      phone: normalized.raw10,
      count: results.length,
      results,
    });
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
});

app.get("*", (_req, res) => {
  res.sendFile(path.join(__dirname, "public", "index.html"));
});

app.listen(PORT, () => {
  console.log(`OTP API console running at http://localhost:${PORT}`);
});
