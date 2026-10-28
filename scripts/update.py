#!/usr/bin/env python3
"""Refresh class data for 北基宜花金馬分署 from 職業訓練整合網.

The list comes from the same search API the site's own page calls. Each class
then gets its detail page read for enrollment numbers: 在職 classes use the
在職訓練網 page, 職前 classes use the 職前訓練網 page. Standard library only,
so it runs on a bare GitHub Actions runner.
"""
import datetime as dt
import html
import json
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "classes.json"
API = "https://course.taiwanjobs.gov.tw/api/Course/paging"
BRANCH = "北基宜花"  # same TrainingUnit value the site's search box sends
MONTHS_AHEAD = 4  # the site's default window: this month plus four more
TZ = dt.timezone(dt.timedelta(hours=8))
UA = "Mozilla/5.0 (class-dashboard refresh)"


CHAIN = Path(__file__).resolve().parent / "its_chain.pem"


def ssl_context():
    """Verify certificates as usual, plus the extra intermediate certificates
    that its.taiwanjobs.gov.tw forgets to send (see scripts/its_chain.pem)."""
    context = ssl.create_default_context()
    if CHAIN.exists():
        context.load_verify_locations(cafile=str(CHAIN))
    return context


def fetch(url, body=None, content_type=None, retries=3):
    headers = {"User-Agent": UA}
    if content_type:
        headers["Content-Type"] = content_type
    context = ssl_context()
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30, context=context) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code < 500 or attempt == retries:
                raise
        except urllib.error.URLError:
            if attempt == retries:
                raise
        time.sleep(5 * attempt)  # back off before retrying a slow or failing server


def search_window(today):
    year, month = today.year, today.month
    end_year, end_month = year, month + MONTHS_AHEAD
    while end_month > 12:
        end_month -= 12
        end_year += 1
    return year, month, end_year, end_month


def search_rows(today):
    y1, m1, y2, m2 = search_window(today)
    form = {
        "Limit": 200,
        "Offset": 0,
        "SourceType": "",
        "TrainingStartDateYear": y1,
        "TrainingStartDateMonth": m1,
        "TrainingEndDateYear": y2,
        "TrainingEndDateMonth": m2,
        "TrainingUnit": BRANCH,
        "Search": "",
        "RegisterStatus": "",
        "TrainingPeriod": 1,
        "sourcePrimaryKey": "",
        "Sort": "RegisterStartDateTime",
        "Order": "desc",
    }
    body = urllib.parse.urlencode(form).encode()
    data = json.loads(fetch(API, body, "application/x-www-form-urlencoded"))
    return (y1, m1, y2, m2), data["total"], data["rows"]


def page_text(markup):
    """Flatten an HTML page to one line per visible text block."""
    markup = re.sub(r"(?is)<(script|style).*?</\1>", " ", markup)
    markup = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|li|td|th|h\d)>", "\n", markup)
    text = html.unescape(re.sub(r"<[^>]+>", " ", markup))
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def grab(text, label):
    match = re.search(re.escape(label) + r"[：:]\s*([^\n]*)", text)
    return match.group(1).strip() if match else None


def to_int(value):
    match = re.search(r"\d+", value or "")
    return int(match.group()) if match else None


def parse_ojt(text):
    """在職訓練網 detail page."""
    return {
        "quota": to_int(grab(text, "訓練學員數")),
        "enrolled": to_int(grab(text, "報名人數")),
        "hours": to_int(grab(text, "訓練時數")),
        "exam": grab(text, "甄試日期"),
        "time": grab(text, "上課時間"),
        "contact": grab(text, "聯絡窗口"),
        "phone": grab(text, "聯絡電話"),
    }


def value_after(text, label):
    """职前訓練網 puts each value on the line after its label."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line == label:
            for nxt in lines[i + 1:i + 3]:
                if nxt and nxt != label:
                    return nxt
    return None


def roc_date(value):
    """115/12/30 (民國) -> 2026/12/30."""
    match = re.match(r"(\d+)/(\d+)/(\d+)", value or "")
    if not match:
        return value
    year, month, day_ = (int(x) for x in match.groups())
    return f"{year + 1911}/{month:02d}/{day_:02d}"


def parse_its(text):
    """職前訓練網 detail page."""
    return {
        "quota": to_int(grab(text, "一般訓練學員數")),
        "enrolled": to_int(grab(text, "目前一般訓練報名人數")),
        "hours": to_int(value_after(text, "訓練時數")),
        "exam": roc_date(value_after(text, "甄試日期")),
        "time": value_after(text, "訓練時段"),
        "contact": value_after(text, "聯絡窗口"),
        "phone": value_after(text, "聯絡電話"),
    }


def day(stamp):
    return (stamp or "")[:10] or None


def build(row):
    url = row.get("Url") or ""
    rec = {
        "id": row["ID"],
        "code": row.get("SourcePrimaryKey"),
        "source": row.get("CourseTypeName"),
        "plan": row.get("PlanName"),
        "name": row.get("Name"),
        "category": row.get("Category"),
        "location": row.get("CourseLocation") or row.get("Address"),
        "city": row.get("CityName"),
        "regStart": day(row.get("RegisterStartDateTime")),
        "regEnd": day(row.get("RegisterEndDateTime")),
        "trainStart": day(row.get("TrainingStartDateTime")),
        "trainEnd": day(row.get("TrainingEndDateTime")),
        "url": url,
        "quota": None,
        "enrolled": None,
        "hours": None,
        "exam": None,
        "time": None,
        "contact": None,
        "phone": None,
        "error": None,
    }
    try:
        parser = parse_ojt if "ojt.wda.gov.tw" in url else parse_its
        rec.update(parser(page_text(fetch(url))))
    except Exception as exc:  # keep the class even if its detail page fails
        rec["error"] = str(exc)[:200]
        print(f"detail page failed: {url}: {rec['error']}", file=sys.stderr)
    time.sleep(0.5)  # be polite to the government servers
    return rec


def main():
    now = dt.datetime.now(TZ)
    window, total, rows = search_rows(now.date())
    rows = [r for r in rows if BRANCH in (r.get("BranchName") or "")]
    if not rows:
        sys.exit("search returned no classes; keeping the previous data file")
    if total != len(rows):
        print(f"warning: API total {total} but {len(rows)} rows for {BRANCH}", file=sys.stderr)

    classes = sorted((build(r) for r in rows), key=lambda c: c["regStart"] or "")
    failed = [c["name"] for c in classes if c["error"]]
    if len(failed) == len(classes):
        sys.exit("every detail page failed; keeping the previous data file")

    out = {
        "updatedAt": now.isoformat(timespec="minutes"),
        "window": "{}/{:02d} – {}/{:02d}".format(window[0], window[1], window[2], window[3]),
        "count": len(classes),
        "failed": failed,
        "classes": classes,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(classes)} classes to {OUT} (failed detail pages: {len(failed)})")


if __name__ == "__main__":
    main()
