#!/usr/bin/env python3
"""
WiFi Direct Legacy AP - dark glassmorphism GUI front-end for WiFiDirectLegacyAP.py

Pure tkinter (stdlib) + qrcode/Pillow for the QR popup. Icons are embedded,
pre-rasterized PNGs (see icons_data.py / THIRD_PARTY_LICENSES.md) - no SVG
renderer needed at runtime.
"""

import base64
import io
import random
import string
import threading
import tkinter as tk
from tkinter import font as tkfont

import qrcode
from PIL import Image, ImageTk

from icons_data import ICONS

# ---------------------------------------------------------------------------
# Palette (dark mode only, no light mode switch)
# ---------------------------------------------------------------------------
WINDOW_BG     = "#0a0b0f"
CARD_BG       = "#15171e"
CARD_BORDER   = "#262a35"
FIELD_BG      = "#1c1f29"
FIELD_BORDER  = "#2e3240"
FIELD_FOCUS   = "#3a3f52"
TEXT_PRIMARY  = "#e9eaf0"
TEXT_SECOND   = "#888ea3"
TEXT_MUTED    = "#5b6070"
ACCENT        = "#22d3ee"
ACCENT_DIM    = "#0e2a30"
DANGER        = "#ff5c7a"

BTN_OFF_BG     = "#1b1e27"
BTN_OFF_BORDER = "#343946"

W, H = 420, 660

SSID_PREFIX_WORDS = [
    "PC", "LAPTOP", "DESK", "HOME", "NODE", "HUB", "LINK", "ZONE",
]
PASSWORD_ALPHABET = (
    string.ascii_uppercase + string.ascii_lowercase + string.digits
    + "!@#$%^&*()-_=+"
)


def generate_random_ssid():
    """Mimics the DIRECT-xx-name format Windows itself auto-generates for
    WiFi Direct legacy access points when no SSID is supplied."""
    tag = "".join(random.choices(string.ascii_uppercase + string.digits, k=2))
    name = random.choice(SSID_PREFIX_WORDS) + "".join(
        random.choices(string.digits, k=4)
    )
    return "DIRECT-%s-%s" % (tag, name)


def generate_random_password(length=14):
    """Single random passphrase: letters, digits and common US-keyboard signs."""
    return "".join(random.choices(PASSWORD_ALPHABET, k=length))


def round_rect(canvas, x1, y1, x2, y2, r, **kwargs):
    points = [
        x1 + r, y1,
        x2 - r, y1,
        x2, y1,
        x2, y1 + r,
        x2, y2 - r,
        x2, y2,
        x2 - r, y2,
        x1 + r, y2,
        x1, y2,
        x1, y2 - r,
        x1, y1 + r,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def blend(hex_a, hex_b, t):
    """Linear blend between two #rrggbb colors, t in [0,1]."""
    a = tuple(int(hex_a[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(hex_b[i:i + 2], 16) for i in (1, 3, 5))
    c = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return "#%02x%02x%02x" % c


def load_icon(name):
    """Decode one of the embedded base64 PNG icons into a Tk PhotoImage."""
    raw = base64.b64decode(ICONS[name])
    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    return ImageTk.PhotoImage(img)


class RoundedEntry:
    """A tk.Entry with a canvas-drawn rounded background behind it."""

    def __init__(self, canvas, x, y, w, h, r=14, show=None, placeholder="",
                 icon_reserve=0, on_change=None):
        self.canvas = canvas
        self.rect = round_rect(canvas, x, y, x + w, y + h, r,
                                fill=FIELD_BG, outline=FIELD_BORDER, width=1)
        self.var = tk.StringVar()
        self.entry = tk.Entry(
            canvas, textvariable=self.var, show=show,
            font=("Segoe UI", 12), bg=FIELD_BG, fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY, relief="flat",
            highlightthickness=0, bd=0,
        )
        pad = 14
        self.window = canvas.create_window(
            x + pad, y + h / 2, anchor="w",
            width=w - pad * 2 - icon_reserve,
            window=self.entry,
        )
        self.entry.bind("<FocusIn>", lambda e: canvas.itemconfig(self.rect, outline=FIELD_FOCUS))
        self.entry.bind("<FocusOut>", lambda e: canvas.itemconfig(self.rect, outline=FIELD_BORDER))
        self._placeholder = placeholder
        self._show = show
        self._placeholder_active = False
        if placeholder:
            self._set_placeholder()
            self.entry.bind("<FocusIn>", self._on_focus_in, add="+")
            self.entry.bind("<FocusOut>", self._on_focus_out, add="+")
        if on_change is not None:
            self.var.trace_add("write", lambda *a: on_change())

    def _set_placeholder(self):
        self._placeholder_active = True
        self.entry.configure(show="")
        self.var.set(self._placeholder)
        self.entry.configure(fg=TEXT_MUTED)

    def _on_focus_in(self, e):
        if self._placeholder_active:
            self.var.set("")
            self.entry.configure(fg=TEXT_PRIMARY, show=self._show or "")
            self._placeholder_active = False

    def _on_focus_out(self, e):
        if not self.var.get():
            self._set_placeholder()

    def get(self):
        if self._placeholder_active:
            return ""
        return self.var.get()

    def set(self, value):
        self._placeholder_active = False
        self.entry.configure(fg=TEXT_PRIMARY, show=self._show or "")
        self.var.set(value)
        if not value:
            self._set_placeholder()

    def set_show(self, show):
        self._show = show
        if not self._placeholder_active:
            self.entry.configure(show=show)


class IconButton:
    """Small round icon button drawn on a canvas, using a PhotoImage icon."""

    def __init__(self, canvas, cx, cy, radius, photo, on_click=None):
        self.canvas = canvas
        self.cx, self.cy, self.radius = cx, cy, radius
        self.photo = photo
        self.bg = canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                                      fill=FIELD_BG, outline=FIELD_BORDER, width=1)
        self.icon_item = canvas.create_image(cx, cy, image=photo)
        self._on_click = on_click
        for item in (self.bg, self.icon_item):
            canvas.tag_bind(item, "<Button-1>", self._click)
            canvas.tag_bind(item, "<Enter>", self._enter)
            canvas.tag_bind(item, "<Leave>", self._leave)

    def set_icon(self, photo):
        self.photo = photo
        self.canvas.itemconfig(self.icon_item, image=photo)

    def _click(self, event):
        if self._on_click:
            self._on_click()

    def _enter(self, event):
        self.canvas.itemconfig(self.bg, fill=FIELD_FOCUS)
        self.canvas.config(cursor="hand2")

    def _leave(self, event):
        self.canvas.itemconfig(self.bg, fill=FIELD_BG)
        self.canvas.config(cursor="")


class QrPopup:
    """Tooltip-like borderless popup showing a WiFi QR code. Stays open and
    refreshes its image in place while the person keeps hovering and typing."""

    def __init__(self, root):
        self.root = root
        self.top = None
        self.img_label = None
        self.photo = None

    @staticmethod
    def _wifi_qr_image(ssid, password):
        def esc(s):
            for ch in ("\\", ";", ",", ":", '"'):
                s = s.replace(ch, "\\" + ch)
            return s

        data = "WIFI:T:WPA;S:%s;P:%s;;" % (esc(ssid), esc(password))
        qr = qrcode.QRCode(border=1, box_size=6)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0a0b0f", back_color="#e9eaf0").convert("RGB")
        return img.resize((160, 160), Image.NEAREST)

    def show(self, x_root, y_root, ssid, password):
        self.hide()

        top = tk.Toplevel(self.root)
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.configure(bg=CARD_BORDER)

        frame = tk.Frame(top, bg=CARD_BG, padx=14, pady=14,
                          highlightbackground=CARD_BORDER, highlightthickness=1)
        frame.pack(padx=2, pady=2)

        self.photo = ImageTk.PhotoImage(self._wifi_qr_image(ssid, password))
        self.img_label = tk.Label(frame, image=self.photo, bg=CARD_BG, bd=0)
        self.img_label.pack()

        tk.Label(frame, text="Scan to auto-connect", bg=CARD_BG,
                 fg=TEXT_SECOND, font=("Segoe UI", 9)).pack(pady=(8, 0))

        top.update_idletasks()
        tw = top.winfo_width()
        top.geometry("+%d+%d" % (int(x_root - tw / 2), int(y_root - top.winfo_height() - 14)))

        self.top = top

    def update(self, ssid, password):
        if self.top is None or self.img_label is None:
            return
        self.photo = ImageTk.PhotoImage(self._wifi_qr_image(ssid, password))
        self.img_label.configure(image=self.photo)

    def hide(self):
        if self.top is not None:
            self.top.destroy()
            self.top = None
            self.img_label = None


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("WiFi Direct AP")
        self.root.geometry("%dx%d" % (W, H))
        self.root.resizable(False, False)
        self.root.configure(bg=WINDOW_BG)

        self.icons = {name: load_icon(name) for name in (
            "power_off", "power_on", "power_error", "eye", "eye_off",
            "qr_code", "shuffle",
        )}

        self.is_on = False
        self.ap = None
        self.qr_popup = QrPopup(root)

        self.canvas = tk.Canvas(root, width=W, height=H, bg=WINDOW_BG,
                                 highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        self._build_card()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # -- layout ------------------------------------------------------------
    def _build_card(self):
        margin = 24
        round_rect(self.canvas, margin, margin, W - margin, H - margin, 28,
                    fill=CARD_BG, outline=CARD_BORDER, width=1)

        title_font = tkfont.Font(family="Segoe UI", size=15, weight="bold")
        self.canvas.create_text(W / 2, margin + 38, text="WiFi Direct AP",
                                 fill=TEXT_PRIMARY, font=title_font)
        self.canvas.create_text(W / 2, margin + 62, text="Legacy access point broadcaster",
                                 fill=TEXT_MUTED, font=("Segoe UI", 9))

        # -- power button --
        self.pb_cx, self.pb_cy, self.pb_r = W / 2, 190, 62
        self.glow_items = []
        self._draw_glow(on=False)

        self.pb_circle = self.canvas.create_oval(
            self.pb_cx - self.pb_r, self.pb_cy - self.pb_r,
            self.pb_cx + self.pb_r, self.pb_cy + self.pb_r,
            fill=BTN_OFF_BG, outline=BTN_OFF_BORDER, width=2,
        )
        self.pb_icon = self.canvas.create_image(self.pb_cx, self.pb_cy,
                                                  image=self.icons["power_off"])

        for item in (self.pb_circle, self.pb_icon):
            self.canvas.tag_bind(item, "<Button-1>", lambda e: self.toggle())
            self.canvas.tag_bind(item, "<Enter>", lambda e: self.canvas.config(cursor="hand2"))
            self.canvas.tag_bind(item, "<Leave>", lambda e: self.canvas.config(cursor=""))

        self.status_text = self.canvas.create_text(
            W / 2, self.pb_cy + self.pb_r + 26, text="OFF",
            fill=TEXT_MUTED, font=("Segoe UI", 11, "bold"),
        )
        self.status_sub = self.canvas.create_text(
            W / 2, self.pb_cy + self.pb_r + 46, text="Tap to start broadcasting",
            fill=TEXT_MUTED, font=("Segoe UI", 9),
        )

        # -- fields --
        fy = 386
        fx = margin + 22
        fw = W - (margin + 22) * 2
        fh = 46
        icon_gap = 40  # per icon button reserved on the right edge

        self.canvas.create_text(fx, fy - 14, text="SSID", anchor="w",
                                 fill=TEXT_SECOND, font=("Segoe UI", 9, "bold"))
        self.ssid_entry = RoundedEntry(
            self.canvas, fx, fy, fw, fh, r=14, placeholder="Network name",
            icon_reserve=icon_gap, on_change=self._on_fields_changed,
        )
        ssid_shuffle_cx = fx + fw - 24
        ssid_shuffle_cy = fy + fh / 2
        self.ssid_shuffle_btn = IconButton(
            self.canvas, ssid_shuffle_cx, ssid_shuffle_cy, 15,
            self.icons["shuffle"], on_click=self._randomize_ssid,
        )

        py = fy + fh + 34
        self.canvas.create_text(fx, py - 14, text="PASSWORD", anchor="w",
                                 fill=TEXT_SECOND, font=("Segoe UI", 9, "bold"))
        self.pass_entry = RoundedEntry(
            self.canvas, fx, py, fw, fh, r=14, show="\u2022",
            placeholder="Passphrase", icon_reserve=icon_gap * 2,
            on_change=self._on_fields_changed,
        )
        self.pw_hidden = True
        eye_cx = fx + fw - 58
        eye_cy = py + fh / 2
        self.eye_btn = IconButton(
            self.canvas, eye_cx, eye_cy, 15, self.icons["eye_off"],
            on_click=self._toggle_password_visibility,
        )
        pw_shuffle_cx = fx + fw - 24
        pw_shuffle_cy = py + fh / 2
        self.pw_shuffle_btn = IconButton(
            self.canvas, pw_shuffle_cx, pw_shuffle_cy, 15,
            self.icons["shuffle"], on_click=self._randomize_password,
        )

        # -- QR button (icon only) --
        qy = py + fh + 46
        self.qr_cx, self.qr_cy = W / 2, qy
        self.qr_btn = IconButton(
            self.canvas, self.qr_cx, self.qr_cy, 24, self.icons["qr_code"],
        )
        for item in (self.qr_btn.bg, self.qr_btn.icon_item):
            self.canvas.tag_bind(item, "<Enter>", self._on_qr_enter, add="+")
            self.canvas.tag_bind(item, "<Leave>", self._on_qr_leave, add="+")
        self.canvas.create_text(
            W / 2, qy + 36, text="Hover for QR code",
            fill=TEXT_MUTED, font=("Segoe UI", 8),
        )

        self.canvas.create_text(
            W / 2, H - margin - 20,
            text="Windows only \u00b7 requires a WiFi Direct capable adapter",
            fill=TEXT_MUTED, font=("Segoe UI", 8),
        )

    def _draw_glow(self, on):
        for item in self.glow_items:
            self.canvas.delete(item)
        self.glow_items = []
        if not on:
            return
        # Static (non-animated) halo: concentric rings blending toward the
        # accent color, widest/dimmest first so the button stays on top.
        rings = 5
        max_extra = 46
        for i in range(rings, 0, -1):
            t = i / rings
            extra = max_extra * t
            color = blend(CARD_BG, ACCENT, (1 - t) * 0.9 + 0.05)
            item = self.canvas.create_oval(
                self.pb_cx - self.pb_r - extra, self.pb_cy - self.pb_r - extra,
                self.pb_cx + self.pb_r + extra, self.pb_cy + self.pb_r + extra,
                fill=color, outline="",
            )
            self.glow_items.append(item)
        for item in self.glow_items:
            self.canvas.tag_lower(item)
        self.canvas.tag_raise(self.pb_circle)
        self.canvas.tag_raise(self.pb_icon)

    # -- interactions --------------------------------------------------
    def _toggle_password_visibility(self):
        self.pw_hidden = not self.pw_hidden
        self.pass_entry.set_show("" if not self.pw_hidden else "\u2022")
        self.eye_btn.set_icon(self.icons["eye"] if not self.pw_hidden else self.icons["eye_off"])

    def _randomize_ssid(self):
        self.ssid_entry.set(generate_random_ssid())

    def _randomize_password(self):
        self.pass_entry.set(generate_random_password())

    def _current_wifi_creds(self):
        ssid = self.ssid_entry.get() or "MyNetwork"
        password = self.pass_entry.get()
        return ssid, password

    def _on_fields_changed(self):
        if self.qr_popup.top is not None:
            ssid, password = self._current_wifi_creds()
            self.qr_popup.update(ssid, password)

    def _on_qr_enter(self, event):
        ssid, password = self._current_wifi_creds()
        x_root = self.canvas.winfo_rootx() + int(self.qr_cx)
        y_root = self.canvas.winfo_rooty() + int(self.qr_cy) - self.qr_btn.radius
        self.qr_popup.show(x_root, y_root, ssid, password)

    def _on_qr_leave(self, event):
        self.qr_popup.hide()

    def toggle(self):
        if self.is_on:
            self._stop()
        else:
            self._start()

    def _set_status(self, text, sub, color):
        self.canvas.itemconfig(self.status_text, text=text, fill=color)
        self.canvas.itemconfig(self.status_sub, text=sub, fill=TEXT_MUTED)

    def _start(self):
        ssid = self.ssid_entry.get()
        password = self.pass_entry.get()
        self._set_status("STARTING\u2026", "Bringing up the access point", ACCENT)
        self.canvas.itemconfig(self.pb_circle, fill=blend(BTN_OFF_BG, ACCENT, 0.15))

        def worker():
            try:
                from WiFiDirectLegacyAP import WiFiDirectAP
                ap = WiFiDirectAP()
                actual_ssid, actual_password = ap.start(
                    ssid=ssid or None, password=password or None,
                )
                self.root.after(0, self._on_started, ap, actual_ssid, actual_password)
            except Exception as exc:
                self.root.after(0, self._on_error, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_started(self, ap, ssid, password):
        self.ap = ap
        self.is_on = True
        self.ssid_entry.set(ssid)
        self.pass_entry.set(password)
        self.canvas.itemconfig(self.pb_circle, fill=ACCENT_DIM, outline=ACCENT)
        self.canvas.itemconfig(self.pb_icon, image=self.icons["power_on"])
        self._draw_glow(on=True)
        self._set_status("ON", "Broadcasting \u00b7 %s" % ssid, ACCENT)

    def _on_error(self, message):
        self.is_on = False
        self.canvas.itemconfig(self.pb_circle, fill=BTN_OFF_BG, outline=DANGER)
        self.canvas.itemconfig(self.pb_icon, image=self.icons["power_error"])
        self._set_status("ERROR", message[:46], DANGER)

    def _stop(self):
        ap = self.ap

        def worker():
            try:
                if ap is not None:
                    ap.stop()
            except Exception:
                pass
            self.root.after(0, self._on_stopped)

        threading.Thread(target=worker, daemon=True).start()

    def _on_stopped(self):
        self.ap = None
        self.is_on = False
        self.canvas.itemconfig(self.pb_circle, fill=BTN_OFF_BG, outline=BTN_OFF_BORDER)
        self.canvas.itemconfig(self.pb_icon, image=self.icons["power_off"])
        self._draw_glow(on=False)
        self._set_status("OFF", "Tap to start broadcasting", TEXT_MUTED)

    def _on_close(self):
        try:
            if self.ap is not None:
                self.ap.stop()
        except Exception:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
