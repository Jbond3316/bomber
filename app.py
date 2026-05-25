#!/usr/bin/env python3
"""
Consent-based SMS, WhatsApp, and voice-call web app.

The checked-in a.java file is decompiled Android code that invokes many
unrelated third-party OTP endpoints. This app intentionally does not reuse
those endpoints. It sends only through a provider account you own and keeps
live sending behind dry-run, allow-list, consent, and rate-limit controls.
"""

from __future__ import annotations

import base64
import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


APP_NAME = "Consent Messaging Console"
CHANNELS = {"sms", "whatsapp", "call"}
MAX_REQUEST_BYTES = 16 * 1024
PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")
SEPARATOR_RE = re.compile(r"[\s().-]+")
RATE_BUCKETS: dict[str, list[float]] = {}


class AppError(Exception):
    """Expected application error returned to the browser."""

    status = HTTPStatus.BAD_REQUEST

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ValidationError(AppError):
    pass


class RateLimitError(AppError):
    status = HTTPStatus.TOO_MANY_REQUESTS


class ProviderError(AppError):
    status = HTTPStatus.BAD_GATEWAY


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    dry_run: bool
    allow_any_recipient: bool
    allowed_recipients: frozenset[str]
    default_country_code: str
    rate_limit_window_seconds: int
    rate_limit_max: int
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_from_sms: str
    twilio_from_whatsapp: str
    twilio_from_call: str
    twilio_call_twiml: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            host=os.getenv("HOST", "127.0.0.1"),
            port=int(os.getenv("PORT", "8000")),
            dry_run=parse_bool(os.getenv("APP_DRY_RUN", "true")),
            allow_any_recipient=parse_bool(os.getenv("APP_ALLOW_ANY_RECIPIENT", "false")),
            allowed_recipients=parse_allowed_recipients(
                os.getenv("APP_ALLOWED_RECIPIENTS", "")
            ),
            default_country_code=normalize_country_code(
                os.getenv("APP_DEFAULT_COUNTRY_CODE", "+91")
            ),
            rate_limit_window_seconds=int(os.getenv("APP_RATE_WINDOW_SECONDS", "3600")),
            rate_limit_max=int(os.getenv("APP_RATE_LIMIT_MAX", "5")),
            twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
            twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
            twilio_from_sms=os.getenv("TWILIO_FROM_SMS", ""),
            twilio_from_whatsapp=os.getenv("TWILIO_FROM_WHATSAPP", ""),
            twilio_from_call=os.getenv("TWILIO_FROM_CALL", ""),
            twilio_call_twiml=os.getenv(
                "TWILIO_CALL_TWIML",
                "<Response><Say>This is your requested call from the consent messaging console.</Say></Response>",
            ),
        )


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def normalize_country_code(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if value.startswith("+") and value[1:].isdigit():
        return value
    if value.isdigit():
        return f"+{value}"
    raise ValueError("APP_DEFAULT_COUNTRY_CODE must be digits, optionally prefixed with +")


def parse_allowed_recipients(value: str) -> frozenset[str]:
    numbers: set[str] = set()
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        numbers.add(normalize_phone(item, default_country_code=""))
    return frozenset(numbers)


def normalize_phone(raw: str, default_country_code: str = "+91") -> str:
    value = SEPARATOR_RE.sub("", raw.strip())
    if value.startswith("00"):
        value = f"+{value[2:]}"
    elif value.startswith("+"):
        pass
    elif value.isdigit() and default_country_code:
        value = f"{default_country_code}{value}"
    if not PHONE_RE.fullmatch(value):
        raise ValidationError(
            "Enter a valid E.164 phone number, for example +919876543210."
        )
    return value


def selected_channels(payload: dict[str, Any]) -> list[str]:
    channels = payload.get("channels", [])
    if isinstance(channels, str):
        channels = [channels]
    if not isinstance(channels, list):
        raise ValidationError("channels must be a list.")
    normalized = [str(channel).strip().lower() for channel in channels]
    invalid = sorted(set(normalized) - CHANNELS)
    if invalid:
        raise ValidationError(f"Unsupported channel: {', '.join(invalid)}")
    unique = [channel for channel in ("sms", "whatsapp", "call") if channel in normalized]
    if not unique:
        raise ValidationError("Choose at least one channel.")
    return unique


def validate_send_payload(
    payload: dict[str, Any], config: Config
) -> tuple[str, list[str], str]:
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object.")

    consent = payload.get("consent")
    if consent is not True:
        raise ValidationError("Recipient consent is required before sending.")

    phone = normalize_phone(str(payload.get("phone", "")), config.default_country_code)
    channels = selected_channels(payload)
    message = str(payload.get("message", "")).strip()
    if not message:
        message = "This is your requested notification."
    if len(message) > 1000:
        raise ValidationError("Message must be 1000 characters or fewer.")

    if not config.dry_run and not config.allow_any_recipient:
        if not config.allowed_recipients:
            raise ValidationError(
                "Live sending requires APP_ALLOWED_RECIPIENTS or APP_ALLOW_ANY_RECIPIENT=true."
            )
        if phone not in config.allowed_recipients:
            raise ValidationError("This phone number is not in APP_ALLOWED_RECIPIENTS.")

    return phone, channels, message


def check_rate_limit(client_ip: str, phone: str, config: Config) -> None:
    now = time.time()
    window_start = now - config.rate_limit_window_seconds
    keys = (f"ip:{client_ip}", f"phone:{phone}")

    for key in keys:
        RATE_BUCKETS[key] = [stamp for stamp in RATE_BUCKETS.get(key, []) if stamp >= window_start]
        if len(RATE_BUCKETS[key]) >= config.rate_limit_max:
            raise RateLimitError("Rate limit exceeded. Try again later.")

    for key in keys:
        RATE_BUCKETS[key].append(now)


def provider_ready(channel: str, config: Config) -> bool:
    common = bool(config.twilio_account_sid and config.twilio_auth_token)
    if channel == "sms":
        return common and bool(config.twilio_from_sms)
    if channel == "whatsapp":
        return common and bool(config.twilio_from_whatsapp)
    if channel == "call":
        return common and bool(config.twilio_from_call)
    return False


def send_channel(channel: str, phone: str, message: str, config: Config) -> dict[str, Any]:
    if config.dry_run:
        return {
            "channel": channel,
            "status": "dry_run",
            "detail": "APP_DRY_RUN=true; no provider request was sent.",
        }

    if not provider_ready(channel, config):
        raise ProviderError(f"Twilio settings are incomplete for {channel}.")

    if channel == "sms":
        data = {
            "To": phone,
            "From": config.twilio_from_sms,
            "Body": message,
        }
        response = twilio_request("Messages.json", data, config)
    elif channel == "whatsapp":
        data = {
            "To": whatsapp_address(phone),
            "From": whatsapp_address(config.twilio_from_whatsapp),
            "Body": message,
        }
        response = twilio_request("Messages.json", data, config)
    elif channel == "call":
        data = {
            "To": phone,
            "From": config.twilio_from_call,
            "Twiml": config.twilio_call_twiml,
        }
        response = twilio_request("Calls.json", data, config)
    else:
        raise ValidationError(f"Unsupported channel: {channel}")

    return {
        "channel": channel,
        "status": response.get("status", "queued"),
        "sid": response.get("sid"),
    }


def whatsapp_address(phone: str) -> str:
    return phone if phone.startswith("whatsapp:") else f"whatsapp:{phone}"


def twilio_request(path: str, data: dict[str, str], config: Config) -> dict[str, Any]:
    account_sid = urllib.parse.quote(config.twilio_account_sid, safe="")
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/{path}"
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    credentials = f"{config.twilio_account_sid}:{config.twilio_auth_token}".encode(
        "utf-8"
    )
    request = urllib.request.Request(
        url,
        data=encoded,
        headers={
            "Authorization": "Basic "
            + base64.b64encode(credentials).decode("ascii"),
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "consent-messaging-console/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        detail = provider_error_message(body) or exc.reason
        raise ProviderError(f"Twilio rejected the request: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ProviderError(f"Could not reach Twilio: {exc.reason}") from exc


def provider_error_message(body: str) -> str:
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return body[:300]
    message = parsed.get("message") or parsed.get("error")
    return str(message)[:300] if message else body[:300]


def handle_send(payload: dict[str, Any], client_ip: str) -> dict[str, Any]:
    config = Config.from_env()
    phone, channels, message = validate_send_payload(payload, config)
    check_rate_limit(client_ip, phone, config)

    results = [send_channel(channel, phone, message, config) for channel in channels]
    return {
        "ok": True,
        "phone": phone,
        "dryRun": config.dry_run,
        "results": results,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "ConsentMessagingHTTP/1.0"

    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            self.respond_html(render_index())
        elif self.path == "/healthz":
            self.respond_json({"ok": True})
        else:
            self.respond_json({"ok": False, "error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path != "/api/send":
            self.respond_json({"ok": False, "error": "Not found"}, HTTPStatus.NOT_FOUND)
            return

        try:
            payload = self.read_json()
            response = handle_send(payload, self.client_address[0])
            self.respond_json(response)
        except AppError as exc:
            self.respond_json({"ok": False, "error": exc.message}, exc.status)
        except json.JSONDecodeError:
            self.respond_json(
                {"ok": False, "error": "Request body must be valid JSON."},
                HTTPStatus.BAD_REQUEST,
            )

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            raise ValidationError("Request body is required.")
        if length > MAX_REQUEST_BYTES:
            raise ValidationError("Request body is too large.")
        body = self.rfile.read(length).decode("utf-8")
        parsed = json.loads(body)
        if not isinstance(parsed, dict):
            raise ValidationError("Request body must be a JSON object.")
        return parsed

    def respond_json(
        self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK
    ) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def respond_html(self, body: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")


def render_index() -> str:
    config = Config.from_env()
    mode = "Dry run" if config.dry_run else "Live"
    allowed = (
        "any recipient"
        if config.allow_any_recipient
        else f"{len(config.allowed_recipients)} allow-listed recipient(s)"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(APP_NAME)}</title>
  <style>
    :root {{
      color-scheme: light dark;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #0f172a;
      color: #e5e7eb;
    }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
    }}
    main {{
      width: min(760px, 100%);
      background: #111827;
      border: 1px solid #243041;
      border-radius: 20px;
      box-shadow: 0 24px 80px rgb(0 0 0 / 0.35);
      padding: 28px;
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: clamp(28px, 5vw, 44px);
    }}
    p {{
      color: #a7b0c2;
      line-height: 1.6;
    }}
    label {{
      display: block;
      margin: 18px 0 8px;
      font-weight: 700;
    }}
    input[type="tel"], textarea {{
      width: 100%;
      box-sizing: border-box;
      border: 1px solid #334155;
      border-radius: 12px;
      background: #0b1220;
      color: #f8fafc;
      padding: 14px 16px;
      font: inherit;
    }}
    textarea {{
      min-height: 110px;
      resize: vertical;
    }}
    fieldset {{
      border: 1px solid #334155;
      border-radius: 12px;
      margin: 18px 0;
      padding: 12px 16px;
    }}
    legend {{
      padding: 0 8px;
      color: #cbd5e1;
      font-weight: 700;
    }}
    .checks {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
    }}
    .checks label, .consent {{
      display: flex;
      gap: 8px;
      align-items: center;
      margin: 0;
      font-weight: 500;
    }}
    button {{
      margin-top: 18px;
      width: 100%;
      border: 0;
      border-radius: 12px;
      background: linear-gradient(135deg, #22c55e, #0ea5e9);
      color: #07111f;
      cursor: pointer;
      font-weight: 800;
      padding: 14px 18px;
      font-size: 16px;
    }}
    button:disabled {{
      cursor: wait;
      filter: grayscale(0.4);
      opacity: 0.75;
    }}
    .banner {{
      border: 1px solid #31556a;
      background: #0b2535;
      color: #d6f3ff;
      border-radius: 12px;
      padding: 12px 14px;
      margin: 16px 0;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 14px 0 24px;
    }}
    .pill {{
      background: #1f2937;
      border: 1px solid #334155;
      border-radius: 999px;
      color: #cbd5e1;
      padding: 6px 10px;
      font-size: 13px;
    }}
    pre {{
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      border-radius: 12px;
      background: #020617;
      border: 1px solid #1f2937;
      padding: 14px;
      min-height: 74px;
    }}
  </style>
</head>
<body>
  <main>
    <h1>{html.escape(APP_NAME)}</h1>
    <p>Send consent-based notifications by SMS, WhatsApp, or voice call through provider credentials you own.</p>
    <div class="meta">
      <span class="pill">Mode: {html.escape(mode)}</span>
      <span class="pill">Recipients: {html.escape(allowed)}</span>
      <span class="pill">Default country: {html.escape(config.default_country_code)}</span>
    </div>
    <div class="banner">
      This app does not use the decompiled third-party OTP endpoints from <code>a.java</code>.
      Keep <code>APP_DRY_RUN=true</code> until your Twilio account, allow-list, and user consent flow are configured.
    </div>

    <form id="send-form">
      <label for="phone">Phone number</label>
      <input id="phone" name="phone" type="tel" autocomplete="tel" placeholder="+919876543210" required>

      <label for="message">Message for SMS and WhatsApp</label>
      <textarea id="message" name="message" maxlength="1000">This is your requested notification.</textarea>

      <fieldset>
        <legend>Channels</legend>
        <div class="checks">
          <label><input type="checkbox" name="channels" value="sms" checked> SMS</label>
          <label><input type="checkbox" name="channels" value="whatsapp"> WhatsApp</label>
          <label><input type="checkbox" name="channels" value="call"> Call</label>
        </div>
      </fieldset>

      <label class="consent">
        <input id="consent" type="checkbox" required>
        I confirm this recipient asked to receive this message or call.
      </label>

      <button type="submit">Send</button>
    </form>

    <h2>Result</h2>
    <pre id="result">Waiting for a request...</pre>
  </main>

  <script>
    const form = document.querySelector("#send-form");
    const result = document.querySelector("#result");
    const button = form.querySelector("button");

    form.addEventListener("submit", async (event) => {{
      event.preventDefault();
      button.disabled = true;
      result.textContent = "Sending...";

      const channels = [...form.querySelectorAll("input[name='channels']:checked")]
        .map((input) => input.value);
      const payload = {{
        phone: form.phone.value,
        message: form.message.value,
        channels,
        consent: document.querySelector("#consent").checked,
      }};

      try {{
        const response = await fetch("/api/send", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify(payload),
        }});
        const data = await response.json();
        result.textContent = JSON.stringify(data, null, 2);
      }} catch (error) {{
        result.textContent = `Request failed: ${{error}}`;
      }} finally {{
        button.disabled = false;
      }}
    }});
  </script>
</body>
</html>"""


def main() -> None:
    config = Config.from_env()
    server = ThreadingHTTPServer((config.host, config.port), Handler)
    print(f"{APP_NAME} listening on http://{config.host}:{config.port}")
    print(
        "Mode: "
        + ("dry-run; no provider requests will be sent" if config.dry_run else "live")
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
