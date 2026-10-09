"""Parsers over retained source bytes.

Workbook cells are read straight from the xlsx XML so numbers keep the exact
decimal text Google Sheets wrote (no float round-trip). PDF pages are parsed
from their text layer; every record keeps a page/row locator.
"""
import datetime as dt
import json


def _jload(path):
    """json.load on a path, closing the file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)
import re
import zipfile
import xml.etree.ElementTree as ET
from decimal import Decimal

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"

REQUIRED_TABS = ["People", "Trips", "Merchant payments", "FX", "Caps", "Budget",
                 "Review ledger", "Review packets", "Finance activity", "Travel cancellations"]
HEADER_ROW = 5  # rows 1-4 hold the tab title, source marker and notes


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# ---------------------------------------------------------------- workbook

def _col_index(ref):
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_xlsx(path):
    """Return {tab: {"notes": [...], "header": [...], "rows": [{"_row": n, col: text}]}}."""
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            shared.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
            .iter(REL_NS + "Relationship")}
    out = {}
    for sh in wb.find("m:sheets", NS):
        name = sh.get("name")
        target = rels[sh.get("{%s}id" % NS["r"])]
        target = target.lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        grid = {}
        for row in ET.fromstring(z.read(target)).iter("{%s}row" % NS["m"]):
            rn = int(row.get("r"))
            for c in row.findall("m:c", NS):
                t, v = c.get("t"), c.find("m:v", NS)
                if t == "s" and v is not None:
                    val = shared[int(v.text)]
                elif t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter("{%s}t" % NS["m"]))
                elif t == "b" and v is not None:
                    val = "TRUE" if v.text == "1" else "FALSE"
                else:
                    val = v.text if v is not None else None
                if val is not None and val != "":
                    grid.setdefault(rn, {})[_col_index(c.get("r"))] = val
        header_cells = grid.get(HEADER_ROW, {})
        header = [header_cells[i] for i in sorted(header_cells)]
        rows = []
        for rn in sorted(r for r in grid if r > HEADER_ROW):
            cells = grid[rn]
            rec = {"_row": rn}
            for i, h in enumerate(header):
                rec[h] = cells.get(i)
            rows.append(rec)
        notes = [grid.get(r, {}).get(0) for r in range(1, HEADER_ROW)]
        out[name] = {"notes": notes, "header": header, "rows": rows}
    return out


EXCEL_EPOCH = dt.datetime(1899, 12, 30)


def serial_date(s):
    if s is None:
        return None
    return (EXCEL_EPOCH + dt.timedelta(days=int(Decimal(s)))).date()


def serial_utc(s):
    """Workbook times are UTC (tab notes); keep second precision."""
    if s is None:
        return None
    d = Decimal(s)
    whole = int(d)
    secs = int(((d - whole) * 86400).to_integral_value())
    return (EXCEL_EPOCH + dt.timedelta(days=whole, seconds=secs)).replace(tzinfo=dt.timezone.utc)


def dec(s):
    return None if s is None else Decimal(s)


def intval(s):
    if s is None:
        return None
    d = Decimal(s)
    if d != d.to_integral_value():
        raise ValueError("non-integer value %r" % s)
    return int(d)


def lines_of(s):
    return [] if s is None else [x for x in s.split("\n") if x.strip()]


# ---------------------------------------------------------------- policy

def parse_policy(path):
    doc = _jload(path)
    blocks = doc["recordMap"].get("block", {})

    def val(bid):
        b = blocks.get(bid, {}).get("value", {})
        return b.get("value", b) if isinstance(b, dict) else {}

    root = val(doc["page_id"])
    if not root:
        raise ValueError("policy page block missing")
    title = "".join(x[0] for x in root.get("properties", {}).get("title", []))
    texts, missing = [], []
    for i, bid in enumerate(root.get("content", []), 1):
        b = val(bid)
        if not b or "type" not in b:
            missing.append(bid)
            continue
        texts.append({"block_id": bid, "index": i, "type": b["type"],
                      "text": "".join(x[0] for x in b.get("properties", {}).get("title", []))})
    edited = root.get("last_edited_time")
    edited_iso = (dt.datetime.fromtimestamp(edited / 1000, dt.timezone.utc).isoformat().replace("+00:00", "Z")
                  if edited else None)
    m = re.search(r"POL-\d{4}\.\d+", title)
    clock = re.search(r"Case clock: (\d{4}-\d{2}-\d{2}), ([A-Za-z_/]+)", " ".join(t["text"] for t in texts))
    return {"title": title, "policy_revision": m.group(0) if m else None, "version": root.get("version"),
            "last_edited_iso": edited_iso, "blocks": texts, "missing_blocks": missing,
            "case_clock_date": clock.group(1) if clock else None,
            "case_clock_tz": clock.group(2) if clock else None}


# ---------------------------------------------------------------- PDFs

def pdf_pages(path):
    from pypdf import PdfReader
    pages = [p.extract_text() or "" for p in PdfReader(path).pages]
    declared = []
    for t in pages:
        m = re.search(r"Page (\d+) of (\d+)", t)
        declared.append((int(m.group(1)), int(m.group(2))) if m else None)
    return pages, declared


def _field(text, key):
    m = re.search(r"^%s: ?(.*)$" % re.escape(key), text, re.M)
    return m.group(1).strip() if m else None


EXC_KEYS = ["Authorizing Finance officer", "Applies to claim", "Applies to revision", "Expense reference",
            "Allowed original amount", "Covered issues", "Travel cancellation reference", "Exception reason"]


def parse_claim_pages(path, source_id):
    pages, _ = pdf_pages(path)
    out = []
    for pno, text in enumerate(pages, 1):
        c = {"source_id": source_id, "locator": "page %d" % pno,
             "claim_id": _field(text, "Claim reference"), "revision": int(_field(text, "Revision")),
             "arrival_batch": int(_field(text, "Arrival batch")), "employee": _field(text, "Employee"),
             "trip_id": _field(text, "Trip reference"), "trip_revision": int(_field(text, "Trip revision")),
             "submitted": dt.date.fromisoformat(_field(text, "Submitted date")),
             "binder_status": _field(text, "Status"), "claim_reason": _field(text, "Claim reason"),
             "related": [x.strip() for x in (_field(text, "Related earlier claims") or "None").split(",")
                         if x.strip() and x.strip() != "None"]}
        table = text.split("\nCurrency\n", 1)[1].split("\nFinance exception", 1)[0]
        toks = table.split()
        if len(toks) % 6:
            raise ValueError("%s page %d: expense table not in 6-column rows" % (source_id, pno))
        c["lines"] = []
        for i in range(0, len(toks), 6):
            n, cost, rref, first, amt, cur = toks[i:i + 6]
            if int(n) != i // 6 + 1:
                raise ValueError("%s page %d: line numbering broken" % (source_id, pno))
            c["lines"].append({"line": int(n), "cost_id": cost, "receipt_ref": rref,
                               "first_submitted": dt.date.fromisoformat(first), "amount": Decimal(amt),
                               "amount_text": amt, "currency": cur})
        exc_text = text.split("\nFinance exception", 1)[1]
        if exc_text.lstrip().startswith(": Not supplied"):
            c["exception"] = None
        else:
            body = exc_text.split("\n", 1)[1]
            ex, key = {}, None
            for ln in body.split("\n"):
                m = re.match(r"^(%s): ?(.*)$" % "|".join(map(re.escape, EXC_KEYS)), ln)
                if m:
                    key = m.group(1)
                    ex[key] = m.group(2).strip()
                elif key and ln.strip():
                    ex[key] += " " + ln.strip()  # text-layer line wrap inside a value
            c["exception"] = {
                "actor": ex.get("Authorizing Finance officer"), "claim_id": ex.get("Applies to claim"),
                "revision": int(ex["Applies to revision"]) if ex.get("Applies to revision") else None,
                "cost_id": ex.get("Expense reference"),
                "allowed_original": Decimal(ex["Allowed original amount"]) if ex.get("Allowed original amount") else None,
                "covered_issues": [] if ex.get("Covered issues") in (None, "None") else
                [x.strip().lower().replace(" ", "_") for x in ex["Covered issues"].split(",")],
                "travel_cancellation_id": ex.get("Travel cancellation reference"),
                "reason": ex.get("Exception reason"), "locator": "page %d, Finance exception" % pno}
        out.append(c)
    return out


def parse_receipts(path, source_id):
    pages, _ = pdf_pages(path)
    out = []
    for pno, text in enumerate(pages, 1):
        for chunk in text.split("Receipt reference: ")[1:]:
            chunk = "Receipt reference: " + chunk
            out.append({"source_id": source_id, "locator": "page %d" % pno,
                        "receipt_ref": _field(chunk, "Receipt reference"),
                        "cost_id": _field(chunk, "Expense reference"), "employee": _field(chunk, "Employee"),
                        "trip_id": _field(chunk, "Trip reference"), "category": _field(chunk, "Category"),
                        "currency": _field(chunk, "Currency"), "gross": Decimal(_field(chunk, "Gross amount")),
                        "units": _field(chunk, "Documented units"), "description": _field(chunk, "Description"),
                        "issued": _field(chunk, "Issued date")})
    return out
