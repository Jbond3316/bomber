# OTP API Console (from `a.java`)

This repo contains decompiled Android logic in `a.java` (package `com.nextbomb.pro`) and a small web app that exposes the same HTTP OTP flows through a browser.

## What `a.java` does

| Switch case | Service class | Channel in the app |
|-------------|---------------|-------------------|
| `case 3` | `CSService` | Mixed OTP / login APIs |
| `case 4` | `MSService` | SMS OTP |
| `case 5` | `TOAService` | WhatsApp-oriented OTP |
| `case 6` | `VSService` | Voice / IVR call OTP |

The Java code fires many third-party `send-otp` / `whatsapp` / `IVR` endpoints with a random `X-Forwarded-For` IP and the target phone number (`str2` / `str4`).

## Web app

```bash
cd webapp
npm install
npm start
```

Open http://localhost:3000 — enter a 10-digit Indian mobile, then use **SMS**, **WhatsApp**, or **Call / IVR**. The server proxies requests using `webapp/apis.json` (auto-extracted from `a.java`).

### API

- `GET /api/catalog` — list endpoints per channel
- `POST /api/send` — body: `{ "type": "sms"|"whatsapp"|"call", "phone": "9876543210", "index": 0, "all": false }`

## Regenerate `apis.json`

```bash
python3 scripts/extract_apis.py   # or re-run the extraction block in project history
```

## Note

Most endpoints belong to real companies and require cookies, tokens, or CAPTCHA. This project is for analyzing the decompiled client; many calls will fail from a server or browser without the original session material.
