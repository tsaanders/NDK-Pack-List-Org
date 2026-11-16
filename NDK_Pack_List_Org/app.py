"""
NDK Pack List Org
iPad-friendly packing tool with greenhouse sorting and issue tracking.
"""

import os
import re
import json
import uuid
from datetime import datetime
from collections import OrderedDict
from flask import (
    Flask, request, render_template, redirect, url_for,
    jsonify, send_from_directory, flash, session
)
from werkzeug.utils import secure_filename
import pdfplumber
from PIL import Image

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "ndk-pack-list-org-change-me")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

BASE = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE, "uploads")
DATA_DIR = os.path.join(BASE, "data")
IMG_DIR = os.path.join(BASE, "static", "fish_images")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)

GREENHOUSE_PRIORITY = {"D": 1, "G": 2, "X": 3, "B": 4, "A": 5, "T": 6}
ALLOWED_EXT = {"pdf"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def extract_location(sku):
    if not sku:
        return None, 9999
    m = re.search(r"\dG(\d{3})\d", sku)
    if m:
        return "G", int(m.group(1))
    m = re.search(r"\d([DXBAT])(\d{2})\d", sku)
    if m:
        return m.group(1), int(m.group(2))
    return None, 9999


def sort_key(item):
    letter, lot = extract_location(item.get("sku", ""))
    if letter is None:
        return (99, 9999, item.get("sku") or "")
    return (GREENHOUSE_PRIORITY.get(letter, 99), lot, item.get("sku") or "")


def loc_label(sku):
    letter, lot = extract_location(sku)
    if letter == "G":
        return f"G{lot:03d}"
    if letter:
        return f"{letter}{lot:02d}"
    return "POND / PACK"


def parse_fish_size(text, sku=""):
    combined = f"{text or ''} {sku or ''}"
    m = re.search(r"(?:K|BF)(\d{1,2})P?\b", sku or "", re.I)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*[-–to]+\s*(\d+(?:\.\d+)?)\s*[\"”']?", combined)
    if m:
        return max(float(m.group(1)), float(m.group(2)))
    m = re.search(r"(\d+(?:\.\d+)?)\s*[\"”']", combined)
    if m:
        return float(m.group(1))
    return None


def parse_actual_fish_count(sku, product_text, line_qty):
    text = product_text or ""
    try:
        qty = int(str(line_qty).strip())
    except Exception:
        qty = 1
    m = re.search(r"group\s+of\s+(\d+)", text, re.I)
    if m:
        return qty * int(m.group(1))
    m = re.match(r"^(\d+)\s+([A-Z].+)$", (sku or "").strip())
    if m:
        group_from_sku = int(m.group(1))
        if qty == group_from_sku:
            return group_from_sku
        return qty * group_from_sku
    return qty


def process_packing_pdf(pdf_path, session_id):
    """Parse WooCommerce packing list PDF into structured orders with images."""
    orders = OrderedDict()
    current_order_id = None
    img_counter = 0
    session_img_dir = os.path.join(IMG_DIR, session_id)
    os.makedirs(session_img_dir, exist_ok=True)

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            order_match = re.search(r"Packing List for order (\d+)", text)
            if order_match:
                current_order_id = order_match.group(1)
                if current_order_id not in orders:
                    address = method = ""
                    lines = [l.strip() for l in text.splitlines() if l.strip()]
                    for i, line in enumerate(lines):
                        if re.match(r"^[A-Z][a-z]+ [A-Z]", line) and "Next Day" not in line and "Packing" not in line:
                            addr_parts = [line]
                            for j in range(i + 1, min(i + 4, len(lines))):
                                if any(x in lines[j] for x in ["UPS", "Free UPS", "Insulation", "Packaging", "Biodegradable", "Nature Safe"]):
                                    method = lines[j]
                                    break
                                addr_parts.append(lines[j])
                            address = "\n".join(addr_parts)
                            break
                    if not method:
                        for line in lines:
                            if "UPS" in line or "Packaging" in line or "Nature Safe" in line:
                                method = line
                                break
                    orders[current_order_id] = {
                        "order_id": current_order_id,
                        "address": address or "See original",
                        "method": method or "See original",
                        "customer_name": (address or "").split("\n")[0] if address else "Unknown",
                        "items": [],
                    }

            if not current_order_id:
                continue

            words = page.extract_words() or []
            sku_candidates = []
            for w in words:
                txt = w["text"]
                if re.match(r"^[A-Z]{1,4}\d{3,}[A-Z0-9]{3,}$", txt) and len(txt) >= 8:
                    sku_candidates.append({"sku": txt, "top": w["top"], "x0": w["x0"], "qty": "1"})
            for line in text.splitlines():
                m = re.search(r"\b(\d{1,2})\s+([A-Z]{1,4}\d{0,4}[A-Z]{0,6}\d{0,4})\b", line)
                if m:
                    qty_part, code = m.group(1), m.group(2)
                    if len(code) >= 2:
                        sku_candidates.append({
                            "sku": f"{qty_part} {code}",
                            "top": 100,
                            "x0": 50,
                            "qty": "1",
                        })

            desc_map = {}
            lines = text.splitlines()
            for i, line in enumerate(lines):
                for s in sku_candidates:
                    if s["sku"] in line:
                        chunk = " ".join(lines[i : i + 4])
                        desc_map[s["sku"]] = re.sub(r"\s+", " ", chunk)
                        break

            images_info = []
            for img in page.images:
                if img.get("width", 0) > 100 and img.get("height", 0) > 100:
                    try:
                        x0 = max(0, img["x0"] - 1)
                        top = max(0, img["top"] - 1)
                        x1 = min(page.width, img["x1"] + 1)
                        bottom = min(page.height, img["bottom"] + 1)
                        cropped = page.crop((x0, top, x1, bottom))
                        im = cropped.to_image(resolution=120)
                        fname = f"f{img_counter:03d}.png"
                        fpath = os.path.join(session_img_dir, fname)
                        im.save(fpath, format="PNG", optimize=True)
                        images_info.append({"path": fname, "top": img["top"]})
                        img_counter += 1
                    except Exception:
                        pass

            sku_candidates.sort(key=lambda x: x["top"])
            images_info.sort(key=lambda x: x["top"])
            used = set()

            for img_info in images_info:
                best, best_dist = None, 300
                for s in sku_candidates:
                    if s["sku"] in used:
                        continue
                    d = abs(img_info["top"] - s["top"])
                    if d < best_dist:
                        best_dist, best = d, s
                if best:
                    used.add(best["sku"])
                    raw = desc_map.get(best["sku"], "")
                    product = "Fish"
                    m = re.search(r"(?:Imported|A Grade|AA Grade|Premium)[^1]{5,50}", raw)
                    if m:
                        product = m.group(0).strip()[:55]
                    size_in = parse_fish_size(raw, best["sku"])
                    line_qty = best.get("qty", "1")
                    actual = parse_actual_fish_count(best["sku"], raw, line_qty)
                    orders[current_order_id]["items"].append({
                        "sku": best["sku"],
                        "product": product,
                        "qty": line_qty,
                        "actual_fish": actual,
                        "size_inches": size_in,
                        "img": img_info["path"],
                        "location": loc_label(best["sku"]),
                        "issues": {"NIT": False, "Color Change": False, "Sores": False},
                    })

            for s in sku_candidates:
                if s["sku"] not in used:
                    raw = desc_map.get(s["sku"], "")
                    size_in = parse_fish_size(raw, s["sku"])
                    actual = parse_actual_fish_count(s["sku"], raw, s.get("qty", "1"))
                    orders[current_order_id]["items"].append({
                        "sku": s["sku"],
                        "product": s.get("code") or "Fish",
                        "qty": s.get("qty", "1"),
                        "actual_fish": actual,
                        "size_inches": size_in,
                        "img": None,
                        "location": loc_label(s["sku"]),
                        "issues": {"NIT": False, "Color Change": False, "Sores": False},
                    })

    # Sort items within each order
    result = []
    for oid, data in orders.items():
        seen = {}
        for it in data["items"]:
            key = it["sku"]
            if key not in seen or (it.get("img") and not seen[key].get("img")):
                seen[key] = it
        data["items"] = sorted(seen.values(), key=sort_key)
        if data["items"]:
            result.append(data)

    return result


def save_session_data(session_id, orders):
    path = os.path.join(DATA_DIR, f"{session_id}.json")
    with open(path, "w") as f:
        json.dump({"orders": orders, "updated": datetime.now().isoformat()}, f, indent=2)


def load_session_data(session_id):
    path = os.path.join(DATA_DIR, f"{session_id}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


# ---------- Routes ----------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        flash("No file selected")
        return redirect(url_for("index"))
    f = request.files["file"]
    if not f or f.filename == "":
        flash("No file selected")
        return redirect(url_for("index"))
    if not allowed_file(f.filename):
        flash("Please upload a PDF file")
        return redirect(url_for("index"))

    session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    filename = secure_filename(f.filename)
    save_path = os.path.join(UPLOAD_DIR, f"{session_id}_{filename}")
    f.save(save_path)

    try:
        orders = process_packing_pdf(save_path, session_id)
        if not orders:
            flash("No orders found in this PDF. Please upload a WooCommerce packing list.")
            return redirect(url_for("index"))
        save_session_data(session_id, orders)
        return redirect(url_for("packing", session_id=session_id))
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print("UPLOAD ERROR:", tb, flush=True)
        flash(f"Error processing PDF: {type(e).__name__}: {e}")
        return redirect(url_for("index"))


@app.route("/packing/<session_id>")
def packing(session_id):
    data = load_session_data(session_id)
    if not data:
        flash("Session not found. Please upload the packing list again.")
        return redirect(url_for("index"))
    orders = data.get("orders") or []
    # Ensure every item has required fields (defensive for template)
    for order in orders:
        order.setdefault("order_id", "")
        order.setdefault("address", "")
        order.setdefault("method", "")
        order.setdefault("customer_name", "Unknown")
        for item in order.get("items") or []:
            item.setdefault("sku", "")
            item.setdefault("product", "Fish")
            item.setdefault("qty", "1")
            item.setdefault("actual_fish", 1)
            item.setdefault("size_inches", None)
            item.setdefault("img", None)
            item.setdefault("location", "POND / PACK")
            if not isinstance(item.get("issues"), dict):
                item["issues"] = {"NIT": False, "Color Change": False, "Sores": False}
            else:
                for k in ("NIT", "Color Change", "Sores"):
                    item["issues"].setdefault(k, False)
    try:
        return render_template(
            "packing.html",
            session_id=session_id,
            orders=orders,
            img_base=f"/static/fish_images/{session_id}",
        )
    except Exception as e:
        import traceback
        print("PACKING PAGE ERROR:", traceback.format_exc(), flush=True)
        flash(f"Error displaying packing list: {e}")
        return redirect(url_for("index"))


@app.route("/api/issue", methods=["POST"])
def api_issue():
    """Toggle an issue checkbox. Body: {session_id, order_id, item_index, issue, value}"""
    body = request.get_json(force=True)
    session_id = body.get("session_id")
    order_id = str(body.get("order_id"))
    item_index = int(body.get("item_index"))
    issue = body.get("issue")  # NIT | Color Change | Sores
    value = bool(body.get("value"))

    data = load_session_data(session_id)
    if not data:
        return jsonify({"ok": False, "error": "session not found"}), 404

    for order in data["orders"]:
        if order["order_id"] == order_id:
            if 0 <= item_index < len(order["items"]):
                order["items"][item_index]["issues"][issue] = value
                save_session_data(session_id, data["orders"])
                return jsonify({"ok": True})
            break
    return jsonify({"ok": False, "error": "item not found"}), 404


@app.route("/report/<session_id>")
def report(session_id):
    data = load_session_data(session_id)
    if not data:
        flash("Session not found")
        return redirect(url_for("index"))

    rows = []
    for order in data["orders"]:
        for item in order["items"]:
            issues = item.get("issues") or {}
            marked = [k for k, v in issues.items() if v]
            if marked:
                rows.append({
                    "customer": order.get("customer_name", ""),
                    "order_id": order["order_id"],
                    "sku": item.get("sku", ""),
                    "product": item.get("product", ""),
                    "location": item.get("location", ""),
                    "issues": ", ".join(marked),
                })

    return render_template("report.html", session_id=session_id, rows=rows, generated=datetime.now().strftime("%Y-%m-%d %H:%M"))


@app.route("/api/report/<session_id>")
def api_report_json(session_id):
    data = load_session_data(session_id)
    if not data:
        return jsonify([])
    rows = []
    for order in data["orders"]:
        for item in order["items"]:
            issues = item.get("issues") or {}
            marked = [k for k, v in issues.items() if v]
            if marked:
                rows.append({
                    "customer": order.get("customer_name", ""),
                    "order_id": order["order_id"],
                    "sku": item.get("sku", ""),
                    "product": item.get("product", ""),
                    "location": item.get("location", ""),
                    "issues": marked,
                })
    return jsonify(rows)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
