"""Fresh reads of the five native sources, retained byte-for-byte.

Every read records what was attempted (URL, route, locator, UTC time) and what
was observed (bytes, SHA-256, HTTP validators, native version where the source
exposes one). Completeness is checked against the source's own structure; a
successful HTTP response is never treated as proof of complete access.
"""
import datetime as dt
import hashlib
import json
import os
import shutil
import urllib.error
import urllib.request

from . import parse

NOTION_HOST = "https://private-pecorino-70e.notion.site"
NOTION_PAGE_ID = "3d80b700-541e-81ed-93eb-d386abc1dcb0"
SHEET_ID = "1338nvKD6rgAdLgGRhYCMMlQyDNLK0sE8pvFWrZAaaxg"

# The five native locations given by the operations lead in interview 1.
SOURCES = [
    {
        "key": "policy",
        "url": NOTION_HOST + "/Project-D-Alderbridge-travel-reimbursement-policy-POL-2026-1-3d80b700541e81ed93ebd386abc1dcb0",
        "route": "notion public page API loadCachedPageChunkV2 (page " + NOTION_PAGE_ID + ")",
        "file": "policy/notion-page-chunk.json",
    },
    {
        "key": "registers",
        "url": "https://docs.google.com/spreadsheets/d/" + SHEET_ID + "/edit",
        "route": "Google Sheets export?format=xlsx",
        "fetch_url": "https://docs.google.com/spreadsheets/d/" + SHEET_ID + "/export?format=xlsx",
        "file": "registers/travel-registers.xlsx",
    },
    {
        "key": "initial-claims",
        "url": "https://drive.google.com/file/d/13sRj6s_kMeP1hsYGstWWmfkb6SCN1YOS/view",
        "route": "Google Drive download (drive.usercontent.google.com)",
        "fetch_url": "https://drive.usercontent.google.com/download?id=13sRj6s_kMeP1hsYGstWWmfkb6SCN1YOS&export=download",
        "file": "binders/initial-claim-binder.pdf",
    },
    {
        "key": "claim-updates",
        "url": "https://drive.google.com/file/d/16829RwrGrMCK9oq5TnWuytFewGk_8xQP/view",
        "route": "Google Drive download (drive.usercontent.google.com)",
        "fetch_url": "https://drive.usercontent.google.com/download?id=16829RwrGrMCK9oq5TnWuytFewGk_8xQP&export=download",
        "file": "binders/claim-updates-binder.pdf",
    },
    {
        "key": "receipts",
        "url": "https://drive.google.com/file/d/1Ynn1VLH-faRIy91xy95rOWwCBhy5mjjM/view",
        "route": "Google Drive download (drive.usercontent.google.com)",
        "fetch_url": "https://drive.usercontent.google.com/download?id=1Ynn1VLH-faRIy91xy95rOWwCBhy5mjjM&export=download",
        "file": "binders/receipt-binder.pdf",
    },
]

REQUIRED_TABS = parse.REQUIRED_TABS
UA = "travel-expense-claim-skill/1.0 (+fresh source read)"


def utcnow():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(path):
    with open(path, "rb") as f:
        return sha256_bytes(f.read())


def _http(url, data=None, headers=None, timeout=60):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
        hdr = {k.lower(): v for k, v in r.headers.items()}
        return r.status, hdr, body


def _validators(hdr):
    v = {k: hdr[k] for k in ("etag", "last-modified") if k in hdr}
    return v


def _fetch_notion():
    """Load every block of the policy page, following the cursor until exhausted."""
    api = NOTION_HOST + "/api/v3/loadCachedPageChunkV2"
    record_map, cursor, chunks = {}, {"stack": []}, 0
    hdr = {}
    while True:
        body = json.dumps({"page": {"id": NOTION_PAGE_ID}, "limit": 200, "cursor": cursor,
                           "verticalColumns": False}).encode()
        status, hdr, raw = _http(api, data=body, headers={"content-type": "application/json"})
        doc = json.loads(raw)
        for table, rows in doc.get("recordMap", {}).items():
            if isinstance(rows, dict):
                record_map.setdefault(table, {}).update(rows)
        chunks += 1
        cursors = doc.get("cursors") or []
        if not cursors or chunks >= 20:
            break
        cursor = cursors[0]
    payload = {"page_id": NOTION_PAGE_ID, "chunks": chunks, "recordMap": record_map}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1).encode(), hdr


def _check(key, path):
    """Return (completeness, missing_scope, version, pieces) for retained bytes."""
    if key == "policy":
        pol = parse.parse_policy(path)
        missing = pol["missing_blocks"]
        version = "notion-block-version:%s; last_edited_time:%s" % (pol["version"], pol["last_edited_iso"])
        return ("partial" if missing else "complete",
                ("missing Notion blocks: " + ", ".join(missing)) if missing else None, version,
                [{"suffix": "", "locator": "Notion page %s, %d content blocks, title '%s'" % (
                    NOTION_PAGE_ID, len(pol["blocks"]), pol["title"])}])
    if key == "registers":
        tabs = parse.read_xlsx(path)
        pieces, missing = [], []
        for t in REQUIRED_TABS:
            if t not in tabs or not tabs[t]["header"]:
                missing.append(t)
                continue
            canon = json.dumps({"notes": tabs[t]["notes"], "header": tabs[t]["header"], "rows": tabs[t]["rows"]},
                               ensure_ascii=False, sort_keys=True).encode()
            pieces.append({"suffix": ":" + parse.slug(t),
                           "locator": "tab '%s', header row 5, data rows 6-%d (%d rows)" % (
                               t, 5 + len(tabs[t]["rows"]), len(tabs[t]["rows"])),
                           "content_sha256": sha256_bytes(canon)})
        return ("partial" if missing else "complete",
                ("missing tabs: " + ", ".join(missing)) if missing else None, None, pieces)
    pages, declared = parse.pdf_pages(path)
    gaps = [i for i, d in enumerate(declared, 1) if d is None or d[0] != i or d[1] != len(pages)]
    missing = None
    if gaps:
        missing = "page footers inconsistent with 'Page X of %d' on pages %s" % (len(pages), gaps[:20])
    return ("partial" if gaps else "complete", missing, None,
            [{"suffix": "", "locator": "PDF pages 1-%d (footer 'Page X of %d' verified)" % (len(pages), len(pages))}])


def capture_fresh(run_dir):
    """Attempt a fresh read of all five native locations into run_dir/sources/."""
    files = []
    for s in SOURCES:
        observed_at = utcnow()
        rel = os.path.join("sources", s["file"])
        dest = os.path.join(run_dir, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        base = {"native_url": s["url"], "route": s["route"], "observed_at": observed_at}
        try:
            if s["key"] == "policy":
                body, hdr = _fetch_notion()
            else:
                status, hdr, body = _http(s["fetch_url"])
                if s["key"] == "registers" and not body.startswith(b"PK"):
                    raise ValueError("export did not return an xlsx workbook")
                if s["key"] != "registers" and not body.startswith(b"%PDF"):
                    raise ValueError("download did not return a PDF (got %r...)" % body[:40])
            with open(dest, "wb") as f:
                f.write(body)
            files.append(_entry(s, rel, dest, base, _validators(hdr)))
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as e:
            files.append(_unavailable(s, base, "%s: %s" % (type(e).__name__, e)))
    return files


def capture_replay(run_dir, prior_dir, prior_sources):
    """Offline replay: reuse the earlier run's retained bytes, never claiming fresh access."""
    files, copied = [], set()
    for f in prior_sources["files"]:
        f = dict(f)
        if f["path"] and f["path"] not in copied:
            src = os.path.join(prior_dir, f["path"])
            dst = os.path.join(run_dir, f["path"])
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
            copied.add(f["path"])
        if f["path"] and sha256_file(os.path.join(run_dir, f["path"])) != f["sha256"]:
            f.update(status="unavailable", error="retained prior bytes do not match recorded sha256",
                     path=None, sha256=None, version=None)
        f["replayed_from_run"] = prior_sources["run_id"]
        files.append(f)
    return files


def _entry(s, rel, dest, base, validators):
    digest = sha256_file(dest)
    try:
        completeness, missing, version, pieces = _check(s["key"], dest)
    except Exception as e:  # unparseable bytes are retained but not usable
        return [dict(source_id=s["key"], path=rel, sha256=digest, status="read",
                     error="retained but unparseable: %s: %s" % (type(e).__name__, e),
                     url=base["native_url"], locator="entire file", observed_at=base["observed_at"],
                     version=None, completeness="unusable", missing_scope="entire source",
                     route=base["route"], http_validators=validators)]
    if version is None:
        version = ("http:" + json.dumps(validators, sort_keys=True)) if validators else None
    out = []
    for p in pieces:
        out.append(dict(source_id=s["key"] + p["suffix"], path=rel, sha256=digest, status="read",
                        error=None, url=base["native_url"], locator=p["locator"],
                        observed_at=base["observed_at"], version=version, completeness=completeness,
                        missing_scope=missing, route=base["route"], http_validators=validators))
        if "content_sha256" in p:
            # Sheets rebuilds the xlsx on every export, so byte hashes differ for identical cells;
            # this hash over the tab's canonical cell text identifies the content itself.
            out[-1]["content_sha256"] = p["content_sha256"]
    if s["key"] == "registers" and missing:
        for t in missing.replace("missing tabs: ", "").split(", "):
            out.append(dict(source_id="registers:" + parse.slug(t), path=None, sha256=None,
                            status="unavailable", error="tab not present in export", url=base["native_url"],
                            locator="tab '%s'" % t, observed_at=base["observed_at"], version=None,
                            completeness="missing", missing_scope="tab '%s'" % t, route=base["route"],
                            http_validators=validators))
    return out


def _unavailable(s, base, err):
    if s["key"] == "registers":
        ids = [("registers:" + parse.slug(t), "tab '%s'" % t) for t in REQUIRED_TABS]
    else:
        ids = [(s["key"], "entire source")]
    return [dict(source_id=i, path=None, sha256=None, status="unavailable", error=err,
                 url=base["native_url"], locator=loc, observed_at=base["observed_at"], version=None,
                 completeness="missing", missing_scope=loc, route=base["route"], http_validators={})
            for i, loc in ids]


def flatten(entries):
    out = []
    for e in entries:
        out.extend(e if isinstance(e, list) else [e])
    return out
