#!/usr/bin/env python3
"""Extract SMS / WhatsApp / call OTP endpoints from a.java into webapp/apis.json."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JAVA = ROOT / "a.java"
OUT = ROOT / "webapp" / "apis.json"


def main() -> None:
    text = JAVA.read_text(errors="replace")
    endpoints = []

    for m in re.finditer(r'D\.g\.e\("([^"]+)",\s*"(GET|POST|PUT|DELETE)"', text):
        url, method = m.group(1), m.group(2)
        ctx = text[m.start() : m.start() + 1500]
        body = None
        for pat in (
            r'StringBuilder\("(\{[^"]*)"\)',
            r'StringBuilder\("(api=[^"]*)"\)',
        ):
            bm = re.search(pat, ctx)
            if bm:
                body = bm.group(1)
                break
        ctype = "application/json"
        if "x-www-form-urlencoded" in ctx:
            ctype = "application/x-www-form-urlencoded"
        headers = {
            hm.group(1): hm.group(2)
            for hm in re.finditer(r'eVarE\.a\("([^"]+)",\s*"([^"]+)"\)', ctx)
        }
        cat = "sms"
        if "whatsapp" in url.lower() or (body and "whatsapp" in body.lower()):
            cat = "whatsapp"
        elif "ivr" in url.lower():
            cat = "call"
        endpoints.append(
            {
                "name": url.split("//")[1].split("/")[0],
                "url": url,
                "method": method,
                "bodyTemplate": body,
                "contentType": ctype,
                "headers": headers,
                "category": cat,
            }
        )

    seen = {}
    for e in endpoints:
        seen.setdefault(e["url"], e)

    by_cat = {"sms": [], "whatsapp": [], "call": []}
    for e in seen.values():
        by_cat[e["category"]].append(e)
    for cat in by_cat:
        by_cat[cat] = sorted(by_cat[cat], key=lambda x: x["name"])[:30]

    OUT.write_text(json.dumps(by_cat, indent=2))
    print("Wrote", OUT, {k: len(v) for k, v in by_cat.items()})


if __name__ == "__main__":
    main()
