#!/usr/bin/env python3
"""
Easy Photo Print LX — A right-click photo printing utility for Linux/Nautilus.
Usage: python3 photo_print_app.py image1.jpg image2.jpg ...
"""

import sys
import os
import math
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tempfile
import subprocess

try:
    from PIL import Image, ImageTk, ImageOps
except ImportError:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "Missing Dependency",
        "Pillow is required.\n\nInstall it with:\n"
        "  python3 -m pip install Pillow --break-system-packages"
    )
    sys.exit(1)

# ─── Page size definitions (width × height in pixels at 300 DPI) ─────────────

def _mm_to_px(mm, dpi=300):
    return int(mm * dpi / 25.4)

PAGE_SIZES = {
    "A4          210×297 mm":  (_mm_to_px(210), _mm_to_px(297)),
    "Letter      8.5×11 in":   (_mm_to_px(216), _mm_to_px(279)),
    "A3          297×420 mm":  (_mm_to_px(297), _mm_to_px(420)),
    '4"×6"  102×152 mm':       (_mm_to_px(102), _mm_to_px(152)),
    '5"×7"  127×178 mm':       (_mm_to_px(127), _mm_to_px(178)),
    '6"×8"  152×203 mm':       (_mm_to_px(152), _mm_to_px(203)),
}

PAGE_MARGIN  = _mm_to_px(8)   # 8 mm page margin at 300 DPI
PHOTO_GAP    = _mm_to_px(3)   # 3 mm gap between photos

# (columns, rows) for each layout count
GRID = {1: (1, 1), 2: (1, 2), 4: (2, 2), 8: (2, 4), 16: (4, 4)}

# ─── Colour palette ───────────────────────────────────────────────────────────

C = {
    "bg":        "#1e1e2e",
    "panel":     "#2a2a3e",
    "card":      "#313244",
    "border":    "#45475a",
    "accent":    "#7c6af7",
    "accent_h":  "#9b8fff",
    "text":      "#cdd6f4",
    "dim":       "#7c7f9e",
    "white":     "#ffffff",
    "green":     "#a6e3a1",
}

# ─── Main Application ─────────────────────────────────────────────────────────

class PhotoPrintApp:
    PREVIEW_W = 330
    PREVIEW_H = 430
    THUMB_SZ  = 68
    SETTINGS_W = 300

    def __init__(self, root: tk.Tk, image_paths: list):
        self.root = root
        self.image_paths = [p for p in image_paths if os.path.isfile(p)]

        if not self.image_paths:
            messagebox.showerror("Easy Photo Print LX", "No valid image files were provided.")
            root.destroy()
            return

        # ── State variables ──────────────────────────────────────────────────
        default_layout   = 4 if len(self.image_paths) > 1 else 1
        self._printers   = self._get_printers()
        self.v_layout    = tk.IntVar(value=default_layout)
        self.v_pagesize  = tk.StringVar(value=list(PAGE_SIZES.keys())[0])
        self.v_orient    = tk.StringVar(value=self._detect_orientation())
        self.v_fit       = tk.StringVar(value="Fit")
        self.v_copies    = tk.IntVar(value=1)
        self.v_printer   = tk.StringVar(value=self._printers[0] if self._printers else "(default)")
        self.v_status    = tk.StringVar(value="")

        self._thumb_refs = []   # prevent GC of PhotoImage objects
        self._preview_img = None

        self._build_window()
        self._build_ui()
        self._update_preview()
        self._fit_and_center()   # size window to exactly fit all widgets

    # ── Photo aspect ratio helpers ────────────────────────────────────────────

    def _photo_aspect_ratio(self) -> float:
        """Return the median aspect ratio (w/h) of the selected photos,
        honouring EXIF orientation tags."""
        ratios = []
        for path in self.image_paths[:10]:
            try:
                with Image.open(path) as img:
                    img = ImageOps.exif_transpose(img)
                    ratios.append(img.width / img.height)
            except Exception:
                pass
        if not ratios:
            return 1.0
        ratios.sort()
        return ratios[len(ratios) // 2]

    def _cell_ratio(self, cols: int, rows: int, pw: int, ph: int) -> float:
        """Aspect ratio of a single grid cell given page dimensions."""
        cw = (pw - 2 * PAGE_MARGIN - max(0, cols - 1) * PHOTO_GAP) / cols
        ch = (ph - 2 * PAGE_MARGIN - max(0, rows - 1) * PHOTO_GAP) / rows
        return cw / max(ch, 1)

    def _best_fit_error(self, cols: int, rows: int, pw: int, ph: int, photo_ar: float) -> float:
        """Log-ratio error between the best grid orientation and the photo ratio."""
        r1 = self._cell_ratio(cols, rows, pw, ph)
        r2 = self._cell_ratio(rows, cols, pw, ph)
        e1 = abs(math.log(max(r1, 0.01) / max(photo_ar, 0.01)))
        e2 = abs(math.log(max(r2, 0.01) / max(photo_ar, 0.01)))
        return min(e1, e2)

    # ── Orientation auto-detection ────────────────────────────────────────────

    def _detect_orientation(self) -> str:
        """Pick the page orientation whose grid cells best match the photos.

        This considers both grid orientations (cols×rows and rows×cols) for
        each page orientation, choosing whichever combination minimises the
        log-ratio error between cell shape and photo aspect ratio."""
        photo_ar  = self._photo_aspect_ratio()
        layout    = 4 if len(self.image_paths) > 1 else 1
        cols, rows = GRID[layout]
        page_w, page_h = list(PAGE_SIZES.values())[0]   # default page (A4)

        err_portrait  = self._best_fit_error(cols, rows, page_w, page_h,  photo_ar)
        err_landscape = self._best_fit_error(cols, rows, page_h, page_w,  photo_ar)
        return "Portrait" if err_portrait <= err_landscape else "Landscape"

    # ── Printer detection ─────────────────────────────────────────────────────

    @staticmethod
    def _get_printers() -> list:
        """Return list of printer names from CUPS (lpstat -e)."""
        try:
            r = subprocess.run(["lpstat", "-e"],
                               capture_output=True, text=True, timeout=4)
            names = [p.strip() for p in r.stdout.splitlines() if p.strip()]
            return names if names else []
        except Exception:
            return []

    # ── Window setup ──────────────────────────────────────────────────────────

    def _build_window(self):
        self.root.title("Easy Photo Print LX")
        self.root.configure(bg=C["bg"])
        self.root.resizable(True, False)
        # Geometry is set later in _fit_and_center once all widgets exist

    def _fit_and_center(self):
        """Resize window to exactly fit its content, then centre on screen."""
        self.root.update_idletasks()
        w = self.root.winfo_reqwidth()
        h = self.root.winfo_reqheight()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = self.root

        # Title row ────────────────────────────────────────────────────────────
        hdr = tk.Frame(root, bg=C["bg"])
        hdr.pack(fill="x", padx=20, pady=(16, 8))

        tk.Label(hdr, text="Easy Photo Print LX", font=("Helvetica", 17, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(side="left")
        n = len(self.image_paths)
        tk.Label(hdr, text=f"  {n} photo{'s' if n != 1 else ''} selected",
                 font=("Helvetica", 10), bg=C["bg"], fg=C["dim"]).pack(side="left", pady=2)

        # Divider ──────────────────────────────────────────────────────────────
        tk.Frame(root, bg=C["border"], height=1).pack(fill="x", padx=20)

        # Main body — use grid so both columns are guaranteed their minimum widths
        body = tk.Frame(root, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=20, pady=12)
        body.grid_columnconfigure(0, minsize=self.PREVIEW_W, weight=0)
        body.grid_columnconfigure(1, minsize=self.SETTINGS_W, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._build_left(body)
        self._build_right(body)

    def _build_left(self, parent):
        left = tk.Frame(parent, bg=C["bg"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))

        # Preview canvas ───────────────────────────────────────────────────────
        canvas_frame = tk.Frame(left, bg=C["card"], bd=0,
                                 highlightthickness=1, highlightbackground=C["border"])
        canvas_frame.pack()

        self.canvas = tk.Canvas(canvas_frame,
                                width=self.PREVIEW_W, height=self.PREVIEW_H,
                                bg=C["card"], highlightthickness=0)
        self.canvas.pack()

        # Thumbnail strip ──────────────────────────────────────────────────────
        tk.Label(left, text="SELECTED PHOTOS", font=("Helvetica", 8, "bold"),
                 bg=C["bg"], fg=C["dim"]).pack(anchor="w", pady=(10, 4))

        strip = tk.Frame(left, bg=C["bg"])
        strip.pack(anchor="w")

        for i, path in enumerate(self.image_paths[:7]):
            try:
                img = Image.open(path).convert("RGB")
                img.thumbnail((self.THUMB_SZ, self.THUMB_SZ), Image.LANCZOS)
                tk_img = ImageTk.PhotoImage(img)
                self._thumb_refs.append(tk_img)

                cell = tk.Frame(strip, bg=C["card"], width=self.THUMB_SZ + 4,
                                height=self.THUMB_SZ + 4)
                cell.pack_propagate(False)
                cell.pack(side="left", padx=2)
                tk.Label(cell, image=tk_img, bg=C["card"]).pack(expand=True)
            except Exception:
                pass

        if len(self.image_paths) > 7:
            tk.Label(strip,
                     text=f"+{len(self.image_paths) - 7}\nmore",
                     font=("Helvetica", 9), bg=C["bg"], fg=C["dim"],
                     justify="center").pack(side="left", padx=6)

    def _build_right(self, parent):
        right = tk.Frame(parent, bg=C["bg"])
        right.grid(row=0, column=1, sticky="nsew")

        # ── Layout ────────────────────────────────────────────────────────────
        self._label(right, "PHOTOS PER PAGE")
        layout_row = tk.Frame(right, bg=C["bg"])
        layout_row.pack(fill="x", pady=(0, 14))

        for val in [1, 2, 4, 8, 16]:
            b = tk.Radiobutton(
                layout_row, text=f" {val} ",
                variable=self.v_layout, value=val,
                indicatoron=False,
                font=("Helvetica", 12, "bold"),
                bg=C["card"], fg=C["text"],
                selectcolor=C["accent"],
                activebackground=C["accent_h"],
                activeforeground=C["white"],
                relief="flat", bd=0,
                padx=6, pady=6,
                cursor="hand2",
                command=self._update_preview,
            )
            b.pack(side="left", padx=2)

        # ── Page size ─────────────────────────────────────────────────────────
        self._label(right, "PAGE SIZE")

        style = ttk.Style()
        style.theme_use("default")
        style.configure("PP.TCombobox",
                        fieldbackground=C["card"], background=C["card"],
                        foreground=C["text"], arrowcolor=C["text"],
                        bordercolor=C["border"], selectbackground=C["accent"],
                        selectforeground=C["white"], padding=6)
        style.map("PP.TCombobox",
                  fieldbackground=[("readonly", C["card"])],
                  foreground=[("readonly", C["text"])],
                  background=[("readonly", C["card"])])

        self.combo = ttk.Combobox(
            right,
            textvariable=self.v_pagesize,
            values=list(PAGE_SIZES.keys()),
            state="readonly",
            style="PP.TCombobox",
            font=("Helvetica", 10),
            width=24,
        )
        self.combo.pack(anchor="w", pady=(0, 14))
        self.combo.bind("<<ComboboxSelected>>", lambda _: self._update_preview())

        # ── Orientation ───────────────────────────────────────────────────────
        self._label(right, "ORIENTATION")
        orient_row = tk.Frame(right, bg=C["bg"])
        orient_row.pack(fill="x", pady=(0, 14))

        for val, icon in [("Portrait", "▯  Portrait"), ("Landscape", "▭  Landscape")]:
            b = tk.Radiobutton(
                orient_row, text=icon,
                variable=self.v_orient, value=val,
                indicatoron=False,
                font=("Helvetica", 10),
                bg=C["card"], fg=C["text"],
                selectcolor=C["accent"],
                activebackground=C["accent_h"],
                activeforeground=C["white"],
                relief="flat", bd=0,
                padx=10, pady=6,
                cursor="hand2",
                command=self._update_preview,
            )
            b.pack(side="left", padx=2)

        # ── Photo fit ─────────────────────────────────────────────────────────
        self._label(right, "PHOTO FIT")
        fit_row = tk.Frame(right, bg=C["bg"])
        fit_row.pack(fill="x", pady=(0, 14))

        for val, label, tip in [
            ("Fit",  "⬜  Fit",  "Show full photo with white border"),
            ("Fill", "⬛  Fill", "Crop to fill cell (no border)"),
        ]:
            b = tk.Radiobutton(
                fit_row, text=label,
                variable=self.v_fit, value=val,
                indicatoron=False,
                font=("Helvetica", 10),
                bg=C["card"], fg=C["text"],
                selectcolor=C["accent"],
                activebackground=C["accent_h"],
                activeforeground=C["white"],
                relief="flat", bd=0,
                padx=10, pady=6,
                cursor="hand2",
                command=self._update_preview,
            )
            b.pack(side="left", padx=2)

        # ── Copies ────────────────────────────────────────────────────────────
        self._label(right, "COPIES")
        copies_row = tk.Frame(right, bg=C["bg"])
        copies_row.pack(fill="x", pady=(0, 20))

        def dec():
            self.v_copies.set(max(1, self.v_copies.get() - 1))
        def inc():
            self.v_copies.set(min(99, self.v_copies.get() + 1))

        for txt, cmd in [("  −  ", dec), ("  +  ", inc)]:
            side = "left" if txt.strip() == "−" else "right"
            tk.Button(copies_row, text=txt, font=("Helvetica", 13),
                      bg=C["card"], fg=C["text"],
                      activebackground=C["accent"], activeforeground=C["white"],
                      relief="flat", cursor="hand2", bd=0,
                      command=cmd).pack(side=side)

        tk.Label(copies_row, textvariable=self.v_copies,
                 font=("Helvetica", 14, "bold"),
                 bg=C["bg"], fg=C["text"], width=4, anchor="center"
                 ).pack(side="left", expand=True)

        # ── Printer ───────────────────────────────────────────────────────────
        self._label(right, "PRINTER")
        if self._printers:
            style.configure("PP.TCombobox",
                            fieldbackground=C["card"], background=C["card"],
                            foreground=C["text"], arrowcolor=C["text"],
                            bordercolor=C["border"], selectbackground=C["accent"],
                            selectforeground=C["white"], padding=6)
            self.printer_combo = ttk.Combobox(
                right,
                textvariable=self.v_printer,
                values=self._printers,
                state="readonly",
                style="PP.TCombobox",
                font=("Helvetica", 10),
                width=24,
            )
            self.printer_combo.pack(anchor="w", pady=(0, 14))
        else:
            tk.Label(right, text="No printers found (CUPS)",
                     font=("Helvetica", 9), bg=C["bg"], fg=C["dim"]
                     ).pack(anchor="w", pady=(0, 14))

        # ── Spacer ────────────────────────────────────────────────────────────
        tk.Frame(right, bg=C["bg"]).pack(expand=True, fill="y")

        # ── Print button ──────────────────────────────────────────────────────
        self.print_btn = tk.Button(
            right,
            text="  Print",
            font=("Helvetica", 13, "bold"),
            bg=C["accent"], fg=C["white"],
            activebackground=C["accent_h"],
            activeforeground=C["white"],
            relief="flat", bd=0, cursor="hand2",
            padx=0, pady=12,
            command=self._do_print,
        )
        self.print_btn.pack(fill="x", pady=(0, 4))

        # Save to PDF button ───────────────────────────────────────────────────
        self.save_btn = tk.Button(
            right,
            text="  Save as PDF",
            font=("Helvetica", 10),
            bg=C["card"], fg=C["dim"],
            activebackground=C["border"],
            activeforeground=C["text"],
            relief="flat", bd=0, cursor="hand2",
            padx=0, pady=8,
            command=self._do_save_pdf,
        )
        self.save_btn.pack(fill="x", pady=(0, 4))

        # Status label ─────────────────────────────────────────────────────────
        tk.Label(right, textvariable=self.v_status,
                 font=("Helvetica", 9), bg=C["bg"], fg=C["dim"],
                 wraplength=self.SETTINGS_W - 10, justify="center"
                 ).pack(pady=2)

    def _label(self, parent, text):
        tk.Label(parent, text=text,
                 font=("Helvetica", 8, "bold"),
                 bg=C["bg"], fg=C["dim"]).pack(anchor="w", pady=(6, 4))

    # ── Preview rendering ─────────────────────────────────────────────────────

    def _update_preview(self, *_):
        try:
            pages = self._compose_all_pages(preview_dpi=36)
            img   = pages[0]                          # always show page 1
            n_pages = len(pages)

            pw = self.PREVIEW_W - 24
            ph = self.PREVIEW_H - 24
            img.thumbnail((pw, ph), Image.LANCZOS)

            self._preview_img = ImageTk.PhotoImage(img)

            cx = self.PREVIEW_W // 2
            cy = self.PREVIEW_H // 2
            ox = cx - img.width  // 2
            oy = cy - img.height // 2

            self.canvas.delete("all")
            self.canvas.create_rectangle(
                ox + 5, oy + 5, ox + img.width + 5, oy + img.height + 5,
                fill="#0d0d1a", outline=""
            )
            self.canvas.create_image(ox, oy, anchor="nw", image=self._preview_img)

            # Page count badge
            if n_pages > 1:
                self.canvas.create_text(
                    self.PREVIEW_W - 8, self.PREVIEW_H - 8,
                    text=f"Page 1 of {n_pages}",
                    anchor="se", fill=C["dim"], font=("Helvetica", 8)
                )
        except Exception as e:
            self.canvas.delete("all")
            self.canvas.create_text(
                self.PREVIEW_W // 2, self.PREVIEW_H // 2,
                text=f"Preview unavailable\n{e}",
                fill=C["dim"], font=("Helvetica", 9), justify="center"
            )

    # ── Image composition ─────────────────────────────────────────────────────

    def _compose_all_pages(self, preview_dpi=300) -> list:
        """Return a list of PIL Images — one per page.

        Photos are chunked in groups of (cols × rows); each chunk becomes
        one page so all selected photos are printed, not just the first slot.
        """
        size_key = self.v_pagesize.get()
        w_px, h_px = PAGE_SIZES[size_key]

        scale  = preview_dpi / 300
        w_px   = max(1, int(w_px   * scale))
        h_px   = max(1, int(h_px   * scale))
        margin = max(1, int(PAGE_MARGIN * scale))
        gap    = max(1, int(PHOTO_GAP   * scale))

        if self.v_orient.get() == "Landscape":
            w_px, h_px = h_px, w_px

        cols, rows = GRID[self.v_layout.get()]

        # Auto-swap cols↔rows to best match photo aspect ratio
        photo_ar = self._photo_aspect_ratio()
        r1 = self._cell_ratio(cols, rows, w_px, h_px)
        r2 = self._cell_ratio(rows, cols, w_px, h_px)
        if abs(math.log(max(r2, 0.01) / max(photo_ar, 0.01))) < \
           abs(math.log(max(r1, 0.01) / max(photo_ar, 0.01))):
            cols, rows = rows, cols

        usable_w = w_px - 2 * margin - (cols - 1) * gap
        usable_h = h_px - 2 * margin - (rows - 1) * gap
        cell_w   = max(1, usable_w // cols)
        cell_h   = max(1, usable_h // rows)

        # Load all images, apply EXIF and normalise orientation to match cells
        cell_is_portrait = cell_h > cell_w
        imgs = []
        for p in self.image_paths:
            try:
                img = Image.open(p).convert("RGB")
                img = ImageOps.exif_transpose(img)
                if (img.height > img.width) != cell_is_portrait:
                    img = img.rotate(90, expand=True)
                imgs.append(img)
            except Exception:
                pass

        if not imgs:
            return [Image.new("RGB", (w_px, h_px), "white")]

        fill_mode = self.v_fit.get() == "Fill"
        slots     = cols * rows
        pages     = []

        # One page per chunk of photos
        for chunk_start in range(0, max(len(imgs), 1), slots):
            chunk = imgs[chunk_start: chunk_start + slots]
            page  = Image.new("RGB", (w_px, h_px), "white")

            for i, src in enumerate(chunk):
                row = i // cols
                col = i % cols
                x   = margin + col * (cell_w + gap)
                y   = margin + row * (cell_h + gap)

                if fill_mode:
                    placed = self._fill(src, cell_w, cell_h)
                    page.paste(placed, (x, y))
                else:
                    placed = self._fit(src, cell_w, cell_h)
                    page.paste(placed,
                               (x + (cell_w - placed.width)  // 2,
                                y + (cell_h - placed.height) // 2))
            pages.append(page)

        return pages

    @staticmethod
    def _fit(img: Image.Image, w: int, h: int) -> Image.Image:
        copy = img.copy()
        copy.thumbnail((w, h), Image.LANCZOS)
        return copy

    @staticmethod
    def _fill(img: Image.Image, w: int, h: int) -> Image.Image:
        ir = img.width / img.height
        cr = w / h
        if ir > cr:
            nh = h
            nw = int(nh * ir)
        else:
            nw = w
            nh = int(nw / ir)
        r = img.resize((nw, nh), Image.LANCZOS)
        xo = (nw - w) // 2
        yo = (nh - h) // 2
        return r.crop((xo, yo, xo + w, yo + h))

    # ── Actions ───────────────────────────────────────────────────────────────

    def _do_print(self):
        self._set_busy("Preparing print job…")
        self.root.update()

        try:
            pages = self._compose_all_pages(preview_dpi=300)

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                tmp = f.name

            # Save all pages into a single multi-page PDF
            pages[0].save(tmp, "PDF", resolution=300,
                          save_all=True, append_images=pages[1:])

            printer  = self.v_printer.get()
            copies   = self.v_copies.get()
            cmd      = ["lp", "-n", str(copies)]
            if printer and printer != "(default)":
                cmd += ["-d", printer]
            cmd.append(tmp)

            result = subprocess.run(cmd, capture_output=True, text=True)
            os.unlink(tmp)

            if result.returncode == 0:
                n  = len(pages)
                job = result.stdout.strip()
                self.v_status.set(f"✓  {job}")
                self._set_idle()
                messagebox.showinfo(
                    "Photo Print",
                    f"Sent {n} page{'s' if n > 1 else ''} to printer!\n\n{job}"
                )
            else:
                raise RuntimeError(result.stderr.strip() or "lp command returned an error")

        except FileNotFoundError:
            self._set_idle()
            self.v_status.set("❌  CUPS / lp not found")
            messagebox.showerror(
                "Printer Not Found",
                "The 'lp' print command was not found.\n\n"
                "Install CUPS with:\n  sudo apt install cups\n\n"
                "Then add your printer via:\n  http://localhost:631"
            )
        except Exception as e:
            self._set_idle()
            self.v_status.set(f"❌  {e}")
            messagebox.showerror("Print Error", str(e))

    def _do_save_pdf(self):
        path = filedialog.asksaveasfilename(
            title="Save as PDF",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile="photos.pdf",
        )
        if not path:
            return

        self._set_busy("Generating PDF…")
        self.root.update()

        try:
            pages = self._compose_all_pages(preview_dpi=300)
            pages[0].save(path, "PDF", resolution=300,
                          save_all=True, append_images=pages[1:])
            n = len(pages)
            self.v_status.set(f"✓  Saved {n} page{'s' if n > 1 else ''} → {os.path.basename(path)}")
            self._set_idle()
            messagebox.showinfo("Saved", f"PDF saved ({n} page{'s' if n > 1 else ''}):\n{path}")
        except Exception as e:
            self._set_idle()
            self.v_status.set(f"❌  {e}")
            messagebox.showerror("Save Error", str(e))

    def _set_busy(self, msg):
        self.print_btn.config(state="disabled", text=msg)
        self.save_btn.config(state="disabled")

    def _set_idle(self):
        self.print_btn.config(state="normal", text="  Print")
        self.save_btn.config(state="normal")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    paths = sys.argv[1:]

    if not paths:
        # No files passed — open file picker
        picker = tk.Tk()
        picker.withdraw()
        paths = list(filedialog.askopenfilenames(
            title="Select photos to print",
            filetypes=[
                ("Images", "*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.webp *.gif"),
                ("All files", "*.*"),
            ],
        ))
        picker.destroy()
        if not paths:
            sys.exit(0)

    root = tk.Tk()
    PhotoPrintApp(root, paths)
    root.mainloop()


if __name__ == "__main__":
    main()
