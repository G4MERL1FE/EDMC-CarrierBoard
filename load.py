# load.py - Phase 5c: Post Job with editable carrier fields
import os
import json
import collections.abc
import threading
import time
import tkinter as tk
from tkinter import simpledialog, messagebox, ttk
from queue import Queue, Empty

import requests

DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")
DEBUG_FILE = os.path.join(DESKTOP, "cb_debug.txt")
CACHE_FILE = os.path.join(DESKTOP, "cb_carrier_cache.json")
API_URL = "https://ed-carrier-board.th3-g4mer-l1fe.workers.dev/api/jobs"

data_queue = Queue()
ui_status = None
ui_container = None
ui_root = None

cache = {
    "cmdr": "",
    "carrier_name": "",
    "carrier_callsign": "",
    "system": "",
}


def dbg(msg):
    try:
        with open(DEBUG_FILE, "a") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def load_cache():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k in cache:
            if k in data and data[k]:
                cache[k] = data[k]
        dbg(f"cache loaded: {cache}")
    except FileNotFoundError:
        dbg("no cache file yet")
    except Exception as e:
        dbg(f"load_cache error: {type(e).__name__}: {e}")


def save_cache():
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        dbg(f"save_cache error: {type(e).__name__}: {e}")


def to_plain(obj):
    if isinstance(obj, collections.abc.Mapping):
        return {k: to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_plain(v) for v in obj]
    return obj


def hex_decode(s):
    if not s:
        return ""
    try:
        return bytes.fromhex(s).decode("utf-8").rstrip()
    except Exception:
        return s


# ---------- API ----------

def fetch_jobs():
    try:
        r = requests.get(API_URL, timeout=10)
        if r.ok:
            data_queue.put(("jobs", r.json()))
        else:
            data_queue.put(("error", f"HTTP {r.status_code}"))
    except Exception as e:
        data_queue.put(("error", f"{type(e).__name__}: {e}"))


def delete_job(job_id, pin=None):
    try:
        url = f"{API_URL}?id={job_id}"
        if pin:
            url += f"&pin={pin}"
        r = requests.delete(url, timeout=10)
        if r.ok:
            data_queue.put(("info", "Job completed"))
            fetch_jobs()
        elif r.status_code == 403:
            data_queue.put(("error", "Incorrect PIN"))
        else:
            data_queue.put(("error", f"Delete failed: HTTP {r.status_code}"))
    except Exception as e:
        data_queue.put(("error", f"{type(e).__name__}: {e}"))


def post_job(payload):
    try:
        r = requests.post(API_URL, json=payload, timeout=10)
        if r.ok:
            data_queue.put(("info", "Job posted"))
            fetch_jobs()
        else:
            try:
                body = r.json()
                msg = body.get("error", f"HTTP {r.status_code}")
            except Exception:
                msg = f"HTTP {r.status_code}"
            data_queue.put(("error", f"Post failed: {msg}"))
    except Exception as e:
        data_queue.put(("error", f"{type(e).__name__}: {e}"))


def background_loop():
    while True:
        fetch_jobs()
        time.sleep(300)


# ---------- Post dialog ----------

def open_post_dialog():
    dlg = tk.Toplevel(ui_root)
    dlg.title("Post Carrier Job")
    dlg.transient(ui_root)
    dlg.grab_set()
    dlg.resizable(False, False)

    pad = {"padx": 8, "pady": 3}
    row = 0

    def add_label(text):
        nonlocal row
        tk.Label(dlg, text=text, anchor="w").grid(row=row, column=0, sticky="w", **pad)

    add_label("Action")
    action_var = tk.StringVar(value="LOADING")
    ttk.Combobox(dlg, textvariable=action_var, values=["LOADING", "UNLOADING"],
                 state="readonly", width=28).grid(row=row, column=1, sticky="we", **pad)
    row += 1

    add_label("Commodity")
    commodity_var = tk.StringVar()
    tk.Entry(dlg, textvariable=commodity_var, width=30).grid(row=row, column=1, sticky="we", **pad)
    row += 1

    add_label("Quantity (tons)")
    qty_var = tk.StringVar()
    tk.Entry(dlg, textvariable=qty_var, width=30).grid(row=row, column=1, sticky="we", **pad)
    row += 1

    add_label("Price / ton (CR)")
    price_var = tk.StringVar()
    tk.Entry(dlg, textvariable=price_var, width=30).grid(row=row, column=1, sticky="we", **pad)
    row += 1

    add_label("Carrier Name")
    carrier_name_var = tk.StringVar(value=cache["carrier_name"])
    tk.Entry(dlg, textvariable=carrier_name_var, width=30).grid(row=row, column=1, sticky="we", **pad)
    row += 1

    add_label("Carrier Callsign")
    carrier_callsign_var = tk.StringVar(value=cache["carrier_callsign"])
    tk.Entry(dlg, textvariable=carrier_callsign_var, width=30).grid(row=row, column=1, sticky="we", **pad)
    row += 1

    add_label("System")
    system_var = tk.StringVar(value=cache["system"])
    tk.Entry(dlg, textvariable=system_var, width=30).grid(row=row, column=1, sticky="we", **pad)
    row += 1

    add_label("Station")
    station_var = tk.StringVar(value=cache["carrier_callsign"])
    tk.Entry(dlg, textvariable=station_var, width=30).grid(row=row, column=1, sticky="we", **pad)
    row += 1

    add_label("PIN (optional)")
    pin_var = tk.StringVar()
    tk.Entry(dlg, textvariable=pin_var, width=30, show="*").grid(row=row, column=1, sticky="we", **pad)
    row += 1

    add_label("Notes (optional)")
    notes_var = tk.StringVar()
    tk.Entry(dlg, textvariable=notes_var, width=30).grid(row=row, column=1, sticky="we", **pad)
    row += 1

    error_label = tk.Label(dlg, text="", fg="red", anchor="w", wraplength=320)
    error_label.grid(row=row, column=0, columnspan=2, sticky="we", padx=8, pady=(4, 0))
    row += 1

    def on_cancel():
        dlg.destroy()

    def on_post():
        error_label.config(text="")
        action = action_var.get().strip()
        commodity = commodity_var.get().strip()
        qty_str = qty_var.get().strip()
        price_str = price_var.get().strip()
        carrier_name = carrier_name_var.get().strip()
        carrier_callsign = carrier_callsign_var.get().strip()
        system = system_var.get().strip()
        station = station_var.get().strip()
        pin = pin_var.get().strip()
        notes = notes_var.get().strip()

        if not commodity:
            error_label.config(text="Commodity is required"); return
        if not carrier_name:
            error_label.config(text="Carrier Name is required"); return
        if not carrier_callsign:
            error_label.config(text="Carrier Callsign is required"); return
        if not system:
            error_label.config(text="System is required"); return
        if not station:
            error_label.config(text="Station is required"); return

        try:
            qty = int(qty_str)
            if qty <= 0: raise ValueError
        except ValueError:
            error_label.config(text="Quantity must be a positive number"); return

        try:
            price = int(price_str)
            if price <= 0: raise ValueError
        except ValueError:
            error_label.config(text="Price must be a positive number"); return

        # Update cache with whatever the user provided, save for next time
        cache["carrier_name"] = carrier_name
        cache["carrier_callsign"] = carrier_callsign
        cache["system"] = system
        save_cache()

        payload = {
            "discord_username": cache["cmdr"] or "EDMC User",
            "action_type": action,
            "carrier_name": carrier_name,
            "carrier_callsign": carrier_callsign,
            "system_name": system,
            "station_name": station,
            "commodity": commodity,
            "total_quantity": qty,
            "profit_per_ton": price,
            "pad_size": "L",
            "notes": notes,
            "pin": pin,
        }

        dbg(f"posting: {json.dumps(payload)}")
        threading.Thread(target=post_job, args=(payload,), daemon=True).start()
        dlg.destroy()

    btn_frame = tk.Frame(dlg)
    btn_frame.grid(row=row, column=0, columnspan=2, pady=(8, 10))
    tk.Button(btn_frame, text="Cancel", command=on_cancel, width=10).pack(side="left", padx=4)
    tk.Button(btn_frame, text="Post Job", command=on_post, width=10).pack(side="left", padx=4)

    dlg.update_idletasks()
    w, h = dlg.winfo_width(), dlg.winfo_height()
    sw, sh = dlg.winfo_screenwidth(), dlg.winfo_screenheight()
    dlg.geometry(f"+{(sw - w) // 2}+{(sh - h) // 3}")


# ---------- Jobs UI ----------

def clear_children(widget):
    for child in widget.winfo_children():
        child.destroy()


def on_complete_click(job):
    job_id = job.get("id")
    if job.get("has_pin"):
        pin = simpledialog.askstring(
            "PIN Required",
            f"'{job.get('commodity')}' is PIN protected.\nEnter the deletion PIN:",
            parent=ui_root, show="*",
        )
        if pin is None or not pin.strip():
            return
        pin = pin.strip()
    else:
        if not messagebox.askyesno(
            "Complete Job",
            f"Mark '{job.get('commodity')}' at {job.get('system_name')} as completed?",
            parent=ui_root,
        ):
            return
        pin = None
    threading.Thread(target=delete_job, args=(job_id, pin), daemon=True).start()


def render_jobs(jobs):
    clear_children(ui_container)
    if not jobs:
        tk.Label(ui_container, text="No active jobs", fg="gray", anchor="w").pack(fill="x", padx=6, pady=6)
        return
    for j in jobs:
        row = tk.Frame(ui_container, bd=1, relief="solid")
        row.pack(fill="x", padx=4, pady=2)
        line1 = tk.Frame(row)
        line1.pack(fill="x", padx=4, pady=(4, 0))
        action = str(j.get("action_type", "?"))
        commodity = str(j.get("commodity", "?"))
        profit = int(j.get("profit_per_ton", 0) or 0)
        tk.Label(line1, text=f"[{action}]", width=11, anchor="w", fg="#ff8800").pack(side="left")
        tk.Label(line1, text=commodity, anchor="w").pack(side="left", expand=True, fill="x")
        tk.Label(line1, text=f"+{profit:,} CR/t", fg="green").pack(side="right")
        tk.Label(row, text=f"  {j.get('system_name','?')} - {j.get('station_name','?')}", anchor="w").pack(fill="x", padx=4)
        bottom = tk.Frame(row)
        bottom.pack(fill="x", padx=4, pady=(0, 4))
        pin_tag = " [PIN]" if j.get("has_pin") else ""
        tk.Label(
            bottom,
            text=f"  {j.get('carrier_name','?')} ({j.get('carrier_callsign','?')})  |  "
                 f"{int(j.get('total_quantity', 0) or 0):,}t{pin_tag}",
            anchor="w", fg="#aaa",
        ).pack(side="left")
        tk.Button(bottom, text="Complete", command=lambda job=j: on_complete_click(job)).pack(side="right")


def poll_ui():
    if ui_status is None:
        return
    try:
        while True:
            kind, payload = data_queue.get_nowait()
            if kind == "jobs":
                ui_status.config(text=f"CarrierBoard: {len(payload)} job(s)")
                render_jobs(payload)
            elif kind in ("info", "error"):
                ui_status.config(text=f"CarrierBoard: {payload}")
    except Empty:
        pass
    ui_status.after(500, poll_ui)


def on_refresh():
    threading.Thread(target=fetch_jobs, daemon=True).start()


# ---------- EDMC hooks ----------

def plugin_start3(plugin_dir):
    dbg("--- plugin_start3 called ---")
    load_cache()
    threading.Thread(target=background_loop, daemon=True).start()
    return "CarrierBoard"


def plugin_app(parent):
    global ui_status, ui_container, ui_root
    ui_root = parent
    outer = tk.Frame(parent)
    header = tk.Frame(outer)
    header.pack(fill="x", padx=4, pady=(4, 2))
    ui_status = tk.Label(header, text="CarrierBoard: loading...", anchor="w")
    ui_status.pack(side="left", fill="x", expand=True)
    tk.Button(header, text="Post Job", command=open_post_dialog).pack(side="right", padx=(4, 0))
    tk.Button(header, text="Refresh", command=on_refresh).pack(side="right")

    canvas = tk.Canvas(outer, height=220, highlightthickness=0)
    scrollbar = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    ui_container = tk.Frame(canvas)
    ui_container.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=ui_container, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
    ui_status.after(500, poll_ui)
    dbg("plugin_app: UI built")
    return outer


def capi_fleetcarrier(data):
    """Optional: if EDMC does fire the CAPI hook, cache the values."""
    try:
        plain = to_plain(data)
        name = plain.get("name", {}) or {}
        cs = name.get("callsign", "")
        vn = hex_decode(name.get("vanityName", "") or "")
        sys_name = plain.get("currentStarSystem", "")
        if cs:
            cache["carrier_callsign"] = cs
        if vn:
            cache["carrier_name"] = vn
        if sys_name:
            cache["system"] = sys_name
        save_cache()
        dbg(f"capi_fleetcarrier cached: {cache}")
    except Exception as e:
        dbg(f"capi_fleetcarrier error: {type(e).__name__}: {e}")


def journal_entry(cmdr, is_beta, system, station, entry, state):
    try:
        event = entry.get("event") if entry else None
        changed = False
        if cmdr and cmdr != cache["cmdr"]:
            cache["cmdr"] = cmdr
            changed = True
        if system and system != cache["system"] and not cache["system"]:
            # Only auto-fill system if we don't have one from user
            cache["system"] = system
            changed = True
        if changed:
            save_cache()
    except Exception as e:
        dbg(f"journal_entry error: {type(e).__name__}: {e}")


def plugin_stop():
    dbg("plugin_stop called")