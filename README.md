# Consent Messaging Web App

This repository contains a large decompiled `a.java` file. The code appears to
trigger many unrelated third-party OTP endpoints for SMS, WhatsApp, and call
flows. This implementation does not reuse those endpoints.

Instead, `app.py` is a single-file web app for consent-based messaging through a
Twilio account you own. It supports:

- Phone-number input from a browser form
- SMS, WhatsApp, and voice-call actions
- Dry-run mode by default
- Recipient consent checkbox
- E.164 phone validation
- In-memory rate limiting
- Optional recipient allow-list for live sending

## Run locally

```bash
python3 app.py
```

Open <http://127.0.0.1:8000>. By default `APP_DRY_RUN=true`, so no external
provider request is sent.

## Enable live sending

Set provider credentials and keep an allow-list unless you have implemented your
own production consent and abuse controls:

```bash
export APP_DRY_RUN=false
export APP_ALLOWED_RECIPIENTS="+919876543210,+15551234567"

export TWILIO_ACCOUNT_SID="AC..."
export TWILIO_AUTH_TOKEN="..."
export TWILIO_FROM_SMS="+15550001111"
export TWILIO_FROM_WHATSAPP="+14155238886"
export TWILIO_FROM_CALL="+15550001111"

python3 app.py
```

For a voice call, Twilio receives the XML in `TWILIO_CALL_TWIML`. If unset, the
app uses a short default spoken message.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `HOST` | `127.0.0.1` | Bind address |
| `PORT` | `8000` | HTTP port |
| `APP_DRY_RUN` | `true` | Do not send provider requests |
| `APP_ALLOWED_RECIPIENTS` | empty | Comma-separated E.164 numbers allowed for live sends |
| `APP_ALLOW_ANY_RECIPIENT` | `false` | Allow live sends to any number |
| `APP_DEFAULT_COUNTRY_CODE` | `+91` | Prefix for local phone input |
| `APP_RATE_WINDOW_SECONDS` | `3600` | Rate-limit window |
| `APP_RATE_LIMIT_MAX` | `5` | Max requests per IP and phone per window |

## Tests

```bash
python3 -m unittest
```
