"""CarrierBoard EDMC plugin.

Community jobs and trade opportunities in EDMC.
"""
from __future__ import annotations

import collections.abc
import json
import logging
import os
import threading
from datetime import datetime, timezone
from queue import Empty, Queue
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)
VERSION = "1.0.3"

BASE_URL = "https://carrierboard.738294016.xyz"
JOBS_API_URL = f"{BASE_URL}/api/jobs"
SCANNER_API_URL = f"{BASE_URL}/api/scanner/opportunities"
REFRESH_SECONDS = 300
REQUEST_TIMEOUT = (3.05, 12)
STALE_WARNING_HOURS = 12

# CarrierBoard black-and-orange visual theme.
UI_BLACK = "#080808"
CARD_BLACK = "#0b0b0b"
ORANGE = "#ff941a"
ORANGE_TEXT = "#ffb347"
ORANGE_MUTED = "#d98a2b"
ORANGE_WARNING = "#ff6a00"
TAB_BORDER_INACTIVE = "#70420d"

ui_status: tk.Label | None = None
ui_container_jobs: tk.Frame | None = None
ui_container_scanner: tk.Frame | None = None
ui_root: tk.Misc | None = None
plugin_dir: str | None = None
cache_file: str | None = None
scanner_filter_var: tk.StringVar | None = None

_data_queue: Queue[tuple[str, Any]] = Queue()
_stop_event = threading.Event()
_background_thread: threading.Thread | None = None
_refresh_lock = threading.Lock()
_cache_lock = threading.RLock()

cache: dict[str, str] = {
    "cmdr": "",
    "carrier_name": "",
    "carrier_callsign": "",
    "system": "",
}
_jobs: list[dict[str, Any]] = []
_scanner_routes: list[dict[str, Any]] = []


def _queue_status(kind: str, message: str) -> None:
    _data_queue.put((kind, message))


def _cache_path() -> str:
    if cache_file:
        return cache_file
    return os.path.join(os.path.expanduser("~"), "carrierboard_cache.json")


def load_cache() -> None:
    try:
        with open(_cache_path(), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError("cache must contain a JSON object")
        with _cache_lock:
            for key in cache:
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    cache[key] = value
    except FileNotFoundError:
        LOGGER.debug("No CarrierBoard cache found yet")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        LOGGER.warning("Could not load CarrierBoard cache: %s", exc)


def save_cache() -> None:
    path = _cache_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with _cache_lock:
            temporary_path = f"{path}.tmp"
            with open(temporary_path, "w", encoding="utf-8") as handle:
                json.dump(cache, handle, indent=2, ensure_ascii=False)
            os.replace(temporary_path, path)
    except OSError as exc:
        LOGGER.warning("Could not save CarrierBoard cache: %s", exc)


def to_plain(obj: Any) -> Any:
    if isinstance(obj, collections.abc.Mapping):
        return {key: to_plain(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_plain(value) for value in obj]
    return obj


def hex_decode(value: Any) -> str:
    if not value:
        return ""
    try:
        return bytes.fromhex(str(value)).decode("utf-8").rstrip()
    except (ValueError, UnicodeDecodeError, TypeError):
        return str(value)


def _list_from_payload(payload: Any, key: str) -> list[dict[str, Any]]:
    """Normalise API responses and reject unexpected shapes before rendering."""
    if isinstance(payload, list):
        result = payload
    elif isinstance(payload, dict) and isinstance(payload.get(key), list):
        result = payload[key]
    else:
        raise ValueError(f"API response did not contain a list of {key}")
    if not all(isinstance(item, dict) for item in result):
        raise ValueError(f"API response contained an invalid {key} entry")
    return result


def fetch_jobs() -> None:
    try:
        response = requests.get(JOBS_API_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        jobs = _list_from_payload(response.json(), "jobs")
        _data_queue.put(("jobs", jobs))
    except (requests.RequestException, ValueError) as exc:
        _data_queue.put(("error", f"Community jobs: {exc}"))


def fetch_scanner_opportunities() -> None:
    try:
        response = requests.get(SCANNER_API_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("API response was not an object")
        routes = _list_from_payload(payload, "routes")
        _data_queue.put(("scanner", {
            "routes": routes,
            "generated_at_utc": payload.get("generated_at_utc"),
            "notice": payload.get("notice"),
        }))
    except (requests.RequestException, ValueError) as exc:
        _data_queue.put(("error", f"Trade opportunities: {exc}"))


def refresh_all() -> None:
    """Fetch both feeds in a worker thread; never block EDMC's UI thread."""
    if not _refresh_lock.acquire(blocking=False):
        _queue_status("info", "Refresh already in progress…")
        return

    def worker() -> None:
        try:
            fetch_jobs()
            fetch_scanner_opportunities()
        finally:
            _refresh_lock.release()

    threading.Thread(target=worker, name="CarrierBoard-refresh", daemon=True).start()


def delete_job(job_id: Any, pin: str | None = None) -> None:
    try:
        params: dict[str, Any] = {"id": job_id}
        if pin is not None:
            params["pin"] = pin
        response = requests.delete(JOBS_API_URL, params=params, timeout=REQUEST_TIMEOUT)
        if response.ok:
            _queue_status("info", "Job completed; refreshing board…")
            refresh_all()
        elif response.status_code == 403:
            _queue_status("error", "Incorrect PIN")
        else:
            _queue_status("error", f"Complete job failed: HTTP {response.status_code}")
    except requests.RequestException as exc:
        _queue_status("error", f"Could not complete job: {exc}")


def post_job(payload: dict[str, Any]) -> None:
    try:
        response = requests.post(JOBS_API_URL, json=payload, timeout=REQUEST_TIMEOUT)
        if response.ok:
            _queue_status("info", "Job posted; refreshing board…")
            refresh_all()
        else:
            try:
                body = response.json()
                message = body.get("error", f"HTTP {response.status_code}") if isinstance(body, dict) else f"HTTP {response.status_code}"
            except ValueError:
                message = f"HTTP {response.status_code}"
            _queue_status("error", f"Post failed: {message}")
    except requests.RequestException as exc:
        _queue_status("error", f"Could not post job: {exc}")


def background_loop() -> None:
    while not _stop_event.is_set():
        if not _stop_event.is_set():
            refresh_all()
        if _stop_event.wait(REFRESH_SECONDS):
            break


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        return default


def _format_credits(value: Any) -> str:
    return f"{_safe_int(value):,} Cr"


def _route_value(route: dict[str, Any], key: str, default: Any = "") -> Any:
    value = route.get(key, default)
    return default if value is None else value


def _market_age_hours(timestamp: Any) -> float | None:
    if not isinstance(timestamp, str) or not timestamp.strip():
        return None
    try:
        stamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds() / 3600
        return age if age >= 0 else None
    except (ValueError, TypeError, OverflowError):
        return None


def _format_age(age: float | None) -> str:
    return "age unknown" if age is None else f"{age:.1f}h ago"


# ---------- Post dialog ----------
def open_post_dialog() -> None:
    if ui_root is None:
        return

    dlg = tk.Toplevel(ui_root)
    dlg.title("Post Carrier Job")
    dlg.transient(ui_root)
    dlg.grab_set()
    dlg.resizable(False, False)
    pad = {"padx": 8, "pady": 3}
    row = 0

    def add_label(text: str) -> None:
        nonlocal row
        ttk.Label(dlg, text=text, anchor="w").grid(row=row, column=0, sticky="w", **pad)

    add_label("Action")
    action_var = tk.StringVar(value="LOADING")
    ttk.Combobox(dlg, textvariable=action_var, values=["LOADING", "UNLOADING"],
                 state="readonly", width=28).grid(row=row, column=1, sticky="we", **pad)
    row += 1

    fields: list[tuple[str, tk.StringVar, bool]] = [
        ("Commodity", tk.StringVar(), False),
        ("Quantity (tons)", tk.StringVar(), False),
        ("Price / ton (Cr)", tk.StringVar(), False),
        ("Carrier Name", tk.StringVar(value=cache["carrier_name"]), False),
        ("Carrier Callsign", tk.StringVar(value=cache["carrier_callsign"]), False),
        ("System", tk.StringVar(value=cache["system"]), False),
        ("Station", tk.StringVar(), False),
        ("PIN (optional)", tk.StringVar(), True),
        ("Notes (optional)", tk.StringVar(), False),
    ]
    vars_by_name: dict[str, tk.StringVar] = {}
    for label, variable, masked in fields:
        add_label(label)
        entry = ttk.Entry(dlg, textvariable=variable, width=30, show="*" if masked else "")
        entry.grid(row=row, column=1, sticky="we", **pad)
        vars_by_name[label] = variable
        row += 1

    error_var = tk.StringVar()
    ttk.Label(dlg, textvariable=error_var, foreground="#c0392b", wraplength=340).grid(
        row=row, column=0, columnspan=2, sticky="we", padx=8, pady=(4, 0)
    )
    row += 1

    def on_post() -> None:
        value = {label: variable.get().strip() for label, variable, _masked in fields}
        commodity = value["Commodity"]
        carrier_name = value["Carrier Name"]
        carrier_callsign = value["Carrier Callsign"]
        system = value["System"]
        station = value["Station"]
        if not commodity or not carrier_name or not carrier_callsign or not system or not station:
            error_var.set("Commodity, carrier name/callsign, system and station are required.")
            return
        try:
            quantity = int(value["Quantity (tons)"])
            price = int(value["Price / ton (Cr)"])
            if quantity <= 0 or price <= 0:
                raise ValueError
        except ValueError:
            error_var.set("Quantity and price must be positive whole numbers.")
            return

        with _cache_lock:
            cache["carrier_name"] = carrier_name
            cache["carrier_callsign"] = carrier_callsign
            cache["system"] = system
        save_cache()
        payload = {
            "discord_username": cache["cmdr"] or "EDMC User",
            "action_type": action_var.get().strip(),
            "carrier_name": carrier_name,
            "carrier_callsign": carrier_callsign,
            "system_name": system,
            "station_name": station,
            "commodity": commodity,
            "total_quantity": quantity,
            "profit_per_ton": price,
            "pad_size": "L",
            "notes": value["Notes (optional)"],
            "pin": value["PIN (optional)"],
        }
        # Never log the payload: it contains the optional job PIN.
        threading.Thread(target=post_job, args=(payload,), name="CarrierBoard-post", daemon=True).start()
        dlg.destroy()

    button_frame = ttk.Frame(dlg)
    button_frame.grid(row=row, column=0, columnspan=2, pady=(8, 10))
    ttk.Button(button_frame, text="Cancel", command=dlg.destroy, width=10).pack(side="left", padx=4)
    ttk.Button(button_frame, text="Post Job", command=on_post, width=10).pack(side="left", padx=4)
    dlg.update_idletasks()
    width, height = dlg.winfo_width(), dlg.winfo_height()
    screen_w, screen_h = dlg.winfo_screenwidth(), dlg.winfo_screenheight()
    dlg.geometry(f"+{(screen_w - width) // 2}+{(screen_h - height) // 3}")


# ---------- Scrollable tab helpers ----------
def _scrollable_frame(parent: tk.Misc, height: int = 300) -> tk.Frame:
    outer = ttk.Frame(parent)
    # EDMC can run with a light native ttk theme while Tk Canvas keeps a dark
    # default. When the list is short, the exposed canvas used to show as a
    # black rectangle below the cards. Match it to the active TFrame colour.
    frame_background = ttk.Style().lookup("TFrame", "background") or "SystemButtonFace"
    canvas = tk.Canvas(
        outer,
        height=height,
        bg=frame_background,
        highlightthickness=0,
        borderwidth=0,
    )
    scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    content = ttk.Frame(canvas)
    window_id = canvas.create_window((0, 0), window=content, anchor="nw")

    def update_scroll_region(_event: Any = None) -> None:
        canvas.configure(scrollregion=canvas.bbox("all"))

    def fit_content(event: Any) -> None:
        canvas.itemconfigure(window_id, width=event.width)

    content.bind("<Configure>", update_scroll_region)
    canvas.bind("<Configure>", fit_content)
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    outer.pack(fill="both", expand=True)
    return content


def _clear_children(widget: tk.Misc | None) -> None:
    if widget is None:
        return
    for child in widget.winfo_children():
        child.destroy()


def _make_card(parent: tk.Misc, title: str) -> tk.Frame:
    """Build a high-contrast black card with a visible orange outline."""
    card = tk.Frame(
        parent,
        bg=CARD_BLACK,
        bd=0,
        highlightthickness=1,
        highlightbackground=ORANGE,
        highlightcolor=ORANGE,
    )
    card.pack(fill="x", expand=True, padx=5, pady=4)
    tk.Label(
        card,
        text=title,
        bg=CARD_BLACK,
        fg=ORANGE,
        anchor="w",
        font=("TkDefaultFont", 9, "bold"),
    ).pack(fill="x", padx=8, pady=(6, 3))
    body = tk.Frame(card, bg=CARD_BLACK)
    body.pack(fill="x", padx=8, pady=(0, 7))
    return body


def _card_label(
    parent: tk.Misc,
    text: str,
    *,
    bold: bool = False,
    color: str = ORANGE_TEXT,
    pady: tuple[int, int] | int = 0,
) -> tk.Label:
    """Add orange, readable text to a black card body."""
    font = ("TkDefaultFont", 9, "bold") if bold else ("TkDefaultFont", 9)
    label = tk.Label(
        parent,
        text=text,
        bg=CARD_BLACK,
        fg=color,
        anchor="w",
        justify="left",
        font=font,
    )
    label.pack(anchor="w", fill="x", pady=pady)
    return label


def on_complete_click(job: dict[str, Any]) -> None:
    if ui_root is None:
        return
    job_id = job.get("id")
    if job_id is None:
        _queue_status("error", "This job has no ID and cannot be completed.")
        return
    if job.get("has_pin"):
        pin = simpledialog.askstring(
            "PIN Required",
            f"'{job.get('commodity', 'job')}' is PIN protected.\nEnter the deletion PIN:",
            parent=ui_root,
            show="*",
        )
        if pin is None or not pin.strip():
            return
        pin = pin.strip()
    else:
        confirmed = messagebox.askyesno(
            "Complete Job",
            f"Mark '{job.get('commodity', 'job')}' at {job.get('system_name', '?')} as completed?",
            parent=ui_root,
        )
        if not confirmed:
            return
        pin = None
    threading.Thread(target=delete_job, args=(job_id, pin), name="CarrierBoard-complete", daemon=True).start()


def render_jobs(jobs: list[dict[str, Any]]) -> None:
    _clear_children(ui_container_jobs)
    if ui_container_jobs is None:
        return
    if not jobs:
        tk.Label(
            ui_container_jobs, text="No active community jobs.",
            bg=CARD_BLACK, fg=ORANGE_TEXT, padx=10, pady=10, anchor="w",
        ).pack(fill="x", padx=5, pady=4)
        return
    for job in jobs:
        action = str(job.get("action_type", "JOB")).upper()
        commodity = str(job.get("commodity", "Unknown commodity"))
        profit = _safe_int(job.get("profit_per_ton"))
        card = _make_card(ui_container_jobs, f"{action} · {commodity}")
        _card_label(card, f"{job.get('system_name', '?')} · {job.get('station_name', '?')}")
        _card_label(card, f"Carrier: {job.get('carrier_name', '?')} ({job.get('carrier_callsign', '?')})")
        _card_label(
            card,
            f"Quantity: {_safe_int(job.get('total_quantity')):,} t    ·    Price/profit: {_format_credits(profit)}/t",
            pady=(2, 4),
        )
        bottom = tk.Frame(card, bg=CARD_BLACK)
        bottom.pack(fill="x", pady=(2, 0))
        if job.get("has_pin"):
            tk.Label(bottom, text="PIN protected", bg=CARD_BLACK, fg=ORANGE_MUTED, anchor="w").pack(side="left")
        tk.Button(
            bottom,
            text="Complete",
            command=lambda item=job: on_complete_click(item),
            bg=UI_BLACK,
            fg=ORANGE,
            activebackground="#241300",
            activeforeground="#ffb04a",
            relief="solid",
            bd=1,
            highlightthickness=1,
            highlightbackground=ORANGE,
            highlightcolor=ORANGE,
            padx=10,
            pady=2,
            cursor="hand2",
        ).pack(side="right")


def render_scanner_routes(routes: list[dict[str, Any]], filter_text: str = "") -> None:
    _clear_children(ui_container_scanner)
    if ui_container_scanner is None:
        return
    search = filter_text.casefold().strip()
    visible: list[dict[str, Any]] = []
    for route in routes:
        loading = route.get("loading") if isinstance(route.get("loading"), dict) else {}
        unloading = route.get("unloading") if isinstance(route.get("unloading"), dict) else {}
        haystack = " ".join(str(value) for value in (
            route.get("commodity", ""), loading.get("system", ""), loading.get("station", ""),
            unloading.get("system", ""), unloading.get("station", ""),
        )).casefold()
        if search in haystack:
            visible.append(route)

    if not visible:
        text = "No trade opportunities match this filter." if search else "No trade opportunities available. The live feed may need a fresh snapshot."
        tk.Label(
            ui_container_scanner, text=text, bg=CARD_BLACK, fg=ORANGE_TEXT,
            padx=10, pady=10, wraplength=460, justify="left", anchor="w",
        ).pack(fill="x", padx=5, pady=4)
        return

    for route in visible:
        loading = route.get("loading") if isinstance(route.get("loading"), dict) else {}
        unloading = route.get("unloading") if isinstance(route.get("unloading"), dict) else {}
        commodity = str(route.get("commodity", "Unknown commodity")).strip().title()
        buy = _safe_int(loading.get("buy_price"))
        sell = _safe_int(unloading.get("sell_price"))
        margin = _safe_int(route.get("profit_per_tonne", route.get("profit_per_ton", sell - buy)))
        volume = _safe_int(route.get("estimated_available_volume_tonnes", route.get("estimated_available_volume", 0)))
        total = _safe_int(route.get("estimated_total_profit", margin * volume))
        load_age = _market_age_hours(loading.get("market_timestamp"))
        unload_age = _market_age_hours(unloading.get("market_timestamp"))
        known_ages = [age for age in (load_age, unload_age) if age is not None]
        oldest_age = max(known_ages) if known_ages else None
        freshness_label = f"Oldest market report: {_format_age(oldest_age)}"
        if oldest_age is not None and oldest_age >= STALE_WARNING_HOURS:
            freshness_label += " · CHECK IN-GAME"
        rank = route.get("rank")
        prefix = f"#{rank} · " if rank is not None else ""
        card = _make_card(ui_container_scanner, f"{prefix}{commodity}")
        _card_label(card, f"BUY  {_format_credits(buy)}/t  ·  {loading.get('station', '?')} ({loading.get('system', '?')})")
        _card_label(card, f"SELL {_format_credits(sell)}/t  ·  {unloading.get('station', '?')} ({unloading.get('system', '?')})")
        _card_label(card, f"Margin: {_format_credits(margin)}/t    ·    Est. volume: {volume:,} t", pady=(3, 0))
        _card_label(card, f"Est. total profit: {_format_credits(total)}", bold=True, color=ORANGE)
        age_color = ORANGE_WARNING if oldest_age is not None and oldest_age >= STALE_WARNING_HOURS else ORANGE_MUTED
        _card_label(card, freshness_label, color=age_color, pady=(2, 0))


def _apply_scanner_filter(*_args: Any) -> None:
    value = scanner_filter_var.get() if scanner_filter_var is not None else ""
    render_scanner_routes(_scanner_routes, value)


def poll_ui() -> None:
    global _jobs, _scanner_routes
    if ui_status is None:
        return
    try:
        while True:
            kind, payload = _data_queue.get_nowait()
            if kind == "jobs":
                _jobs = payload
                render_jobs(_jobs)
                ui_status.configure(text=f"Community: {len(_jobs)} jobs · Trade opportunities: {len(_scanner_routes)} routes")
            elif kind == "scanner":
                _scanner_routes = payload.get("routes", [])
                render_scanner_routes(_scanner_routes, scanner_filter_var.get() if scanner_filter_var else "")
                notice = payload.get("notice")
                if notice:
                    ui_status.configure(text=f"Scanner notice: {notice}")
                else:
                    generated = payload.get("generated_at_utc")
                    suffix = f" · Snapshot {generated}" if generated else ""
                    ui_status.configure(text=f"Community: {len(_jobs)} jobs · Trade opportunities: {len(_scanner_routes)} routes{suffix}")
            elif kind == "info":
                ui_status.configure(text=str(payload))
            elif kind == "error":
                ui_status.configure(text=str(payload))
    except Empty:
        pass
    except tk.TclError:
        return
    try:
        ui_status.after(500, poll_ui)
    except tk.TclError:
        pass


def on_refresh() -> None:
    _queue_status("info", "Refreshing community jobs and trade opportunities…")
    refresh_all()


# ---------- EDMC hooks ----------
def plugin_start3(directory: str) -> str:
    global plugin_dir, cache_file, _background_thread
    plugin_dir = directory
    cache_file = os.path.join(directory, "carrierboard_cache.json")
    _stop_event.clear()
    load_cache()
    if _background_thread is None or not _background_thread.is_alive():
        _background_thread = threading.Thread(target=background_loop, name="CarrierBoard-background", daemon=True)
        _background_thread.start()
    LOGGER.info("CarrierBoard plugin started")
    return "CarrierBoard"


def plugin_app(parent: tk.Misc) -> tk.Frame:
    global ui_status, ui_container_jobs, ui_container_scanner, ui_root, scanner_filter_var
    ui_root = parent
    outer = ttk.Frame(parent)
    header = ttk.Frame(outer)
    header.pack(fill="x", padx=4, pady=(4, 4))
    ui_status = ttk.Label(header, text="CarrierBoard: connecting…", anchor="w")
    ui_status.pack(side="left", fill="x", expand=True)
    ttk.Button(header, text="Refresh", command=on_refresh).pack(side="right", padx=(4, 0))

    # Custom tab strip: EDMC's native ttk theme can render Notebook tabs in
    # fixed platform colours. Tk buttons let us keep the requested black/orange
    # treatment consistently across Windows themes.
    tab_strip = tk.Frame(outer, bg="#080808", padx=5, pady=4)
    tab_strip.pack(fill="x", padx=4, pady=(0, 0))
    content_area = ttk.Frame(outer)
    content_area.pack(fill="both", expand=True, padx=4, pady=(0, 4))

    jobs_tab = ttk.Frame(content_area, padding=2)
    scanner_tab = ttk.Frame(content_area, padding=2)

    # Keep job creation visible in the Community Jobs tab. The dialog already
    # exists, but without a button wired to it users have no way to post jobs.
    jobs_toolbar = ttk.Frame(jobs_tab)
    jobs_toolbar.pack(fill="x", padx=5, pady=(4, 2))
    ttk.Label(jobs_toolbar, text="Share a carrier job with the community").pack(
        side="left", padx=(2, 8)
    )
    tk.Button(
        jobs_toolbar,
        text="＋ Post Job",
        command=open_post_dialog,
        bg=UI_BLACK,
        fg=ORANGE,
        activebackground="#241300",
        activeforeground="#ffb04a",
        relief="solid",
        bd=1,
        highlightthickness=1,
        highlightbackground=ORANGE,
        highlightcolor=ORANGE,
        padx=10,
        pady=3,
        cursor="hand2",
        font=("TkDefaultFont", 9, "bold"),
    ).pack(side="right")
    ui_container_jobs = _scrollable_frame(jobs_tab, height=270)

    scanner_toolbar = ttk.Frame(scanner_tab)
    scanner_toolbar.pack(fill="x", padx=5, pady=(4, 2))
    ttk.Label(scanner_toolbar, text="Filter by commodity, system or station:").pack(side="left", padx=(0, 6))
    scanner_filter_var = tk.StringVar()
    filter_entry = ttk.Entry(scanner_toolbar, textvariable=scanner_filter_var, width=22)
    filter_entry.pack(side="left", fill="x", expand=True)
    scanner_filter_var.trace_add("write", _apply_scanner_filter)
    ui_container_scanner = _scrollable_frame(scanner_tab, height=270)
    ttk.Label(scanner_tab, text="Routes over 12h old are highlighted for in-game verification; older than 24h are filtered by the API.").pack(anchor="w", padx=7, pady=(1, 4))

    tab_buttons: dict[str, tk.Button] = {}
    tab_borders: dict[str, tk.Frame] = {}
    tab_frames = {"jobs": jobs_tab, "scanner": scanner_tab}

    def make_tab_button(key: str, label: str) -> None:
        # A wrapper frame creates a reliable orange outline on Windows/Tk themes.
        border = tk.Frame(tab_strip, bg=TAB_BORDER_INACTIVE, padx=1, pady=1, bd=0)
        button = tk.Button(
            border,
            text=label,
            command=lambda selected=key: select_tab(selected),
            bg=UI_BLACK,
            fg=ORANGE,
            activebackground="#241300",
            activeforeground="#ffb04a",
            relief="flat",
            bd=0,
            padx=10,
            pady=5,
            cursor="hand2",
            font=("TkDefaultFont", 9),
        )
        button.pack()
        border.pack(side="left", padx=(0, 5))
        tab_borders[key] = border
        tab_buttons[key] = button

    def select_tab(selected: str) -> None:
        for key, frame in tab_frames.items():
            frame.pack_forget()
            active = key == selected
            tab_borders[key].configure(bg=ORANGE if active else TAB_BORDER_INACTIVE)
            tab_buttons[key].configure(
                bg=UI_BLACK,
                fg=ORANGE if not active else "#ffb04a",
                activebackground="#241300",
                activeforeground="#ffb04a",
                font=("TkDefaultFont", 9, "bold" if active else "normal"),
            )
        tab_frames[selected].pack(fill="both", expand=True)

    make_tab_button("jobs", "Community Jobs")
    make_tab_button("scanner", "Trade Opportunities")
    select_tab("jobs")

    poll_ui()
    return outer


def capi_fleetcarrier(data: Any) -> None:
    """Cache carrier metadata when EDMC provides it through CAPI."""
    try:
        plain = to_plain(data)
        if not isinstance(plain, dict):
            return
        name = plain.get("name", {}) or {}
        callsign = name.get("callsign", "") if isinstance(name, dict) else ""
        carrier_name = hex_decode(name.get("vanityName", "") or "") if isinstance(name, dict) else ""
        system_name = plain.get("currentStarSystem", "")
        with _cache_lock:
            if callsign:
                cache["carrier_callsign"] = str(callsign)
            if carrier_name:
                cache["carrier_name"] = carrier_name
            if system_name:
                cache["system"] = str(system_name)
        save_cache()
    except Exception:
        LOGGER.exception("Could not process fleet carrier CAPI data")


def journal_entry(cmdr: str, is_beta: bool, system: str, station: str, entry: dict[str, Any], state: dict[str, Any]) -> None:
    """Remember commander and initial system values from the journal."""
    changed = False
    with _cache_lock:
        if cmdr and cmdr != cache["cmdr"]:
            cache["cmdr"] = cmdr
            changed = True
        if system and not cache["system"]:
            cache["system"] = system
            changed = True
    if changed:
        save_cache()


def plugin_stop() -> None:
    global _background_thread
    _stop_event.set()
    thread = _background_thread
    if thread is not None and thread.is_alive() and thread is not threading.current_thread():
        thread.join(timeout=2)
    _background_thread = None
    LOGGER.info("CarrierBoard plugin stopped")