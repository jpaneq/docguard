"""DocGuard - herramienta local para proteger documentos.

Pestañas:
  1. Marca de agua resistente (tramada, variaciones aleatorias, rasterizada),
     con plantillas, {fecha}/{hora}, vista por página, lote y exportación PDF/JPG/PNG.
  2. Censura real de PDF: seleccionando texto, por búsqueda o detectando datos
     sensibles; con OCR para escaneos y estilo negro/pixelado/difuminado.
  3. Páginas: reordenar, girar, eliminar, extraer y dividir.
  4. Proteger PDF con contraseña (o quitarla).
  5. Comprimir PDF y convertir PDF <-> imágenes.
  6. Limpieza de metadatos (PDF, imágenes, Office).
  7. Unión de PDFs e imágenes.

Todo se procesa en local; ningún archivo sale del equipo.
"""

import os
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

import pymupdf as fitz
from PIL import Image, ImageTk

import core
from core import APP_NAME, ext_of, suffixed

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except Exception:  # la app funciona igual sin arrastrar y soltar
    HAS_DND = False

DOC_TYPES = [("Documentos", "*.pdf *.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp"), ("Todos", "*.*")]
PDF_TYPES = [("PDF", "*.pdf")]


def enable_drop(widget, callback):
    """Permite soltar archivos sobre `widget`; llama a callback(lista_de_rutas)."""
    if HAS_DND:
        widget.drop_target_register(DND_FILES)
        widget.dnd_bind("<<Drop>>", lambda e: callback(list(widget.tk.splitlist(e.data))))


def busy(widget, on=True):
    widget.winfo_toplevel().config(cursor="watch" if on else "")
    widget.update()


def pil_from_page(page, zoom):
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


# --------------------------------------------------------------------------
# Marca de agua
# --------------------------------------------------------------------------

class WatermarkTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=8)
        self.src = None
        self.page_idx = 0
        self.n_pages = 0
        self._cache = {}
        self.color = (200, 0, 0)
        self._job = None
        self._photo = None

        ctrl = ttk.Frame(self, width=270)
        ctrl.pack(side="left", fill="y", padx=(0, 8))
        ctrl.columnconfigure(1, weight=1)
        r = 0

        def row(widget, pady=(6, 0), **kw):
            nonlocal r
            widget.grid(row=r, column=0, columnspan=3, sticky="ew", pady=pady, **kw)
            r += 1

        row(ttk.Button(ctrl, text="Abrir documento…", command=self.open), pady=0)
        self.file_lbl = ttk.Label(ctrl, text="Ningún archivo (puedes arrastrarlo aquí)", wraplength=260)
        row(self.file_lbl, pady=2)

        pf = ttk.Frame(ctrl)
        ttk.Label(pf, text="Plantilla:").pack(side="left")
        self.preset = tk.StringVar()
        self.preset_cb = ttk.Combobox(pf, textvariable=self.preset, state="readonly", width=14)
        self.preset_cb.pack(side="left", fill="x", expand=True, padx=2)
        self.preset_cb.bind("<<ComboboxSelected>>", lambda e: self.apply_preset())
        ttk.Button(pf, text="Guardar", width=7, command=self.save_preset).pack(side="left")
        ttk.Button(pf, text="✕", width=2, command=self.delete_preset).pack(side="left")
        row(pf)

        row(ttk.Label(ctrl, text="Texto de la marca:"))
        self.text = tk.StringVar(value="Solo para uso de XXX – {fecha}")
        row(ttk.Entry(ctrl, textvariable=self.text), pady=0)
        self.text.trace_add("write", lambda *_: self.schedule())
        row(ttk.Label(ctrl, foreground="gray", text="{fecha} y {hora} se rellenan solos."), pady=0)

        self.vars = {}
        for key, label, lo, hi, val in [
            ("angle", "Orientación °", -90, 90, 35),
            ("size", "Tamaño", 10, 150, 40),
            ("gap_x", "Separación ↔", 0, 400, 60),
            ("gap_y", "Separación ↕", 0, 400, 80),
            ("opacity", "Opacidad %", 5, 100, 35),
        ]:
            var = tk.DoubleVar(value=val)
            self.vars[key] = var
            ttk.Label(ctrl, text=label).grid(row=r, column=0, sticky="w", pady=(4, 0))
            ttk.Scale(ctrl, from_=lo, to=hi, variable=var).grid(row=r, column=1, sticky="ew", padx=4)
            val_lbl = ttk.Label(ctrl, text=str(val), width=4)
            val_lbl.grid(row=r, column=2)
            var.trace_add("write", lambda *_, v=var, l=val_lbl: (l.config(text=str(int(v.get()))),
                                                                 self.schedule()))
            r += 1

        self.color_btn = tk.Button(ctrl, text="Color", bg="#c80000", fg="white", command=self.pick_color)
        row(self.color_btn)
        self.hardened = tk.BooleanVar(value=True)
        row(ttk.Checkbutton(ctrl, text="Protección anti-IA (recomendado)", variable=self.hardened,
                            command=self.schedule))

        ef = ttk.Frame(ctrl)
        ttk.Label(ef, text="Exportar como:").pack(side="left")
        self.fmt = tk.StringVar(value="PDF")
        for f in ("PDF", "JPG", "PNG"):
            ttk.Radiobutton(ef, text=f, value=f, variable=self.fmt).pack(side="left")
        row(ef, pady=(10, 0))

        sf = ttk.Frame(ctrl)
        ttk.Label(sf, text="Tamaño px:").pack(side="left")
        self.out_w, self.out_h = tk.StringVar(), tk.StringVar()
        ttk.Entry(sf, textvariable=self.out_w, width=6).pack(side="left")
        ttk.Label(sf, text="×").pack(side="left")
        ttk.Entry(sf, textvariable=self.out_h, width=6).pack(side="left")
        row(sf)
        row(ttk.Label(ctrl, foreground="gray", wraplength=260,
                      text="Vacío = original. Solo uno = mantiene proporción."), pady=0)

        row(ttk.Button(ctrl, text="Guardar con marca de agua…", command=self.save), pady=(12, 0))
        row(ttk.Button(ctrl, text="Aplicar a varios archivos…", command=self.batch))

        right = ttk.Frame(self)
        right.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(right, bg="#444", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.schedule())
        nav = ttk.Frame(right)
        nav.pack(pady=4)
        ttk.Button(nav, text="◀", width=3, command=lambda: self.goto(self.page_idx - 1)).pack(side="left")
        self.page_lbl = ttk.Label(nav, text="–", width=10, anchor="center")
        self.page_lbl.pack(side="left")
        ttk.Button(nav, text="▶", width=3, command=lambda: self.goto(self.page_idx + 1)).pack(side="left")

        for w in (self, self.canvas):
            enable_drop(w, lambda paths: self.load(paths[0]))
        self.refresh_presets()

    # -- parámetros y plantillas --
    def params(self):
        v = {k: var.get() for k, var in self.vars.items()}
        v["opacity"] /= 100.0
        return dict(text=self.text.get(), color=self.color, hardened=self.hardened.get(), **v)

    def settings(self):
        return dict(text=self.text.get(), color=list(self.color), hardened=self.hardened.get(),
                    fmt=self.fmt.get(), width=self.out_w.get(), height=self.out_h.get(),
                    **{k: var.get() for k, var in self.vars.items()})

    def refresh_presets(self):
        self.presets = core.load_presets()
        self.preset_cb["values"] = sorted(self.presets)

    def save_preset(self):
        name = simpledialog.askstring(APP_NAME, "Nombre de la plantilla:", initialvalue=self.preset.get(),
                                      parent=self)
        if not name:
            return
        self.presets[name] = self.settings()
        core.save_presets(self.presets)
        self.refresh_presets()
        self.preset.set(name)

    def delete_preset(self):
        name = self.preset.get()
        if name in self.presets and messagebox.askyesno(APP_NAME, f"¿Borrar la plantilla «{name}»?"):
            del self.presets[name]
            core.save_presets(self.presets)
            self.refresh_presets()
            self.preset.set("")

    def apply_preset(self):
        p = self.presets.get(self.preset.get())
        if not p:
            return
        self.text.set(p.get("text", ""))
        for k, var in self.vars.items():
            if k in p:
                var.set(p[k])
        self.set_color(tuple(p.get("color", self.color)))
        self.hardened.set(p.get("hardened", True))
        self.fmt.set(p.get("fmt", "PDF"))
        self.out_w.set(p.get("width", ""))
        self.out_h.set(p.get("height", ""))
        self.schedule()

    def set_color(self, rgb):
        self.color = tuple(int(c) for c in rgb)
        self.color_btn.config(bg="#%02x%02x%02x" % self.color)

    def pick_color(self):
        rgb, _ = colorchooser.askcolor(color="#%02x%02x%02x" % self.color)
        if rgb:
            self.set_color(rgb)
            self.schedule()

    # -- documento y vista previa --
    def open(self):
        path = filedialog.askopenfilename(filetypes=DOC_TYPES)
        if path:
            self.load(path)

    def load(self, path):
        try:
            n = core.page_count(path)
            core.load_page(path, 0, dpi=30)
        except Exception as ex:
            messagebox.showerror(APP_NAME, f"No se pudo abrir:\n{ex}")
            return
        self.src, self.n_pages, self._cache = path, n, {}
        self.file_lbl.config(text=os.path.basename(path))
        self.goto(0)

    def goto(self, i):
        if not self.src:
            return
        self.page_idx = max(0, min(i, self.n_pages - 1))
        self.page_lbl.config(text=f"{self.page_idx + 1} / {self.n_pages}")
        self.schedule()

    def schedule(self):
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(120, self.render)

    def render(self):
        self._job = None
        if not self.src:
            return
        if self.page_idx not in self._cache:
            self._cache[self.page_idx] = core.load_page(self.src, self.page_idx, dpi=100)[0]
        cw, ch = max(50, self.canvas.winfo_width()), max(50, self.canvas.winfo_height())
        img = self._cache[self.page_idx].copy()
        img.thumbnail((cw - 10, ch - 10))
        wm = core.apply_watermark(img, seed=1000 + self.page_idx, **self.params())
        self._photo = ImageTk.PhotoImage(wm)
        self.canvas.delete("all")
        self.canvas.create_image(cw // 2, ch // 2, image=self._photo)

    # -- exportación --
    def out_size(self):
        try:
            w = int(self.out_w.get()) if self.out_w.get().strip() else None
            h = int(self.out_h.get()) if self.out_h.get().strip() else None
            if (w is not None and w <= 0) or (h is not None and h <= 0):
                raise ValueError
            return True, w, h
        except ValueError:
            messagebox.showerror(APP_NAME, "El tamaño debe ser un número entero de píxeles.")
            return False, None, None

    def save(self):
        if not self.src:
            messagebox.showinfo(APP_NAME, "Primero abre un documento.")
            return
        ok, w, h = self.out_size()
        if not ok:
            return
        ext = "." + self.fmt.get().lower()
        dst = filedialog.asksaveasfilename(
            defaultextension=ext, initialfile=os.path.basename(suffixed(self.src, "marca", ext)),
            filetypes=[(self.fmt.get(), "*" + ext)])
        if not dst:
            return
        if ext_of(dst) != ext:
            dst += ext
        busy(self)
        try:
            paths = core.export_watermarked(self.src, dst, self.params(), w, h)
            messagebox.showinfo(APP_NAME, "Guardado:\n" + "\n".join(paths))
        except Exception as ex:
            messagebox.showerror(APP_NAME, f"Error al guardar:\n{ex}")
        finally:
            busy(self, False)

    def batch(self):
        ok, w, h = self.out_size()
        if not ok:
            return
        files = filedialog.askopenfilenames(filetypes=DOC_TYPES, title="Archivos a marcar")
        if not files:
            return
        folder = filedialog.askdirectory(title="Carpeta de destino")
        if not folder:
            return
        ext = "." + self.fmt.get().lower()
        done, errors = 0, []
        busy(self)
        for f in files:
            dst = os.path.join(folder, os.path.basename(suffixed(f, "marca", ext)))
            try:
                core.export_watermarked(f, dst, self.params(), w, h)
                done += 1
            except Exception as ex:
                errors.append(f"{os.path.basename(f)}: {ex}")
        busy(self, False)
        msg = f"{done} archivo(s) guardados en:\n{folder}"
        if errors:
            msg += "\n\nErrores:\n" + "\n".join(errors)
        messagebox.showinfo(APP_NAME, msg)


# --------------------------------------------------------------------------
# Censura
# --------------------------------------------------------------------------

class RedactTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=8)
        self.doc = None
        self.src = None
        self.page_no = 0
        self.zoom = 1.3
        self.marks = {}      # nº página -> [[fitz.Rect], ...] (un grupo por acción, para deshacer)
        self.ocr_words = {}  # nº página -> [(Rect, palabra)] reconocidas por OCR
        self._photo = None
        self._start = None

        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Button(bar, text="Abrir PDF/imagen…", command=self.open).pack(side="left")
        ttk.Button(bar, text="◀", width=3, command=lambda: self.goto(self.page_no - 1)).pack(side="left", padx=(10, 0))
        self.page_lbl = ttk.Label(bar, text="–", width=10, anchor="center")
        self.page_lbl.pack(side="left")
        ttk.Button(bar, text="▶", width=3, command=lambda: self.goto(self.page_no + 1)).pack(side="left")
        ttk.Button(bar, text="−", width=3, command=lambda: self.set_zoom(self.zoom / 1.2)).pack(side="left", padx=(10, 0))
        ttk.Button(bar, text="+", width=3, command=lambda: self.set_zoom(self.zoom * 1.2)).pack(side="left")
        self.mode = tk.StringVar(value="text")
        ttk.Radiobutton(bar, text="Seleccionar texto", value="text", variable=self.mode).pack(side="left", padx=(12, 0))
        ttk.Radiobutton(bar, text="Área libre", value="area", variable=self.mode).pack(side="left")
        ttk.Button(bar, text="Reconocer texto (OCR)", command=self.run_ocr_all).pack(side="right")

        bar2 = ttk.Frame(self)
        bar2.pack(fill="x", pady=6)
        ttk.Label(bar2, text="Buscar:").pack(side="left")
        self.search = tk.StringVar()
        ent = ttk.Entry(bar2, textvariable=self.search, width=18)
        ent.pack(side="left", padx=4)
        ent.bind("<Return>", lambda e: self.search_mark())
        ttk.Button(bar2, text="Marcar todo", command=self.search_mark).pack(side="left")
        ttk.Button(bar2, text="Detectar datos sensibles…", command=self.detect).pack(side="left", padx=(8, 0))
        ttk.Button(bar2, text="Deshacer", command=self.undo).pack(side="left", padx=(8, 0))
        ttk.Button(bar2, text="Limpiar página", command=self.clear_page).pack(side="left")
        ttk.Button(bar2, text="Aplicar censura y guardar…", command=self.save).pack(side="right")
        self.style = tk.StringVar(value="Cuadro negro")
        ttk.Combobox(bar2, textvariable=self.style, values=list(core.REDACT_STYLES), state="readonly",
                     width=13).pack(side="right", padx=4)
        ttk.Label(bar2, text="Estilo:").pack(side="right")

        wrap = ttk.Frame(self)
        wrap.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(wrap, bg="#444", highlightthickness=0, cursor="crosshair")
        vs = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        hs = ttk.Scrollbar(wrap, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        vs.pack(side="right", fill="y")
        hs.pack(side="bottom", fill="x")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.status = ttk.Label(self, foreground="gray",
                                text="Arrastra sobre el texto para marcarlo (o suelta aquí un archivo). "
                                     "La censura elimina el texto y los píxeles subyacentes.")
        self.status.pack(anchor="w")
        enable_drop(self.canvas, lambda paths: self.load(paths[0]))

    # -- documento --
    def open(self):
        path = filedialog.askopenfilename(filetypes=DOC_TYPES)
        if path:
            self.load(path)

    def load(self, path):
        try:
            doc = core.open_as_pdf(path)
        except Exception as ex:
            messagebox.showerror(APP_NAME, f"No se pudo abrir:\n{ex}")
            return
        if self.doc:
            self.doc.close()
        self.doc, self.src, self.marks, self.ocr_words = doc, path, {}, {}
        self.goto(0)

    def goto(self, n):
        if not self.doc:
            return
        self.page_no = max(0, min(n, len(self.doc) - 1))
        self.render()

    def set_zoom(self, z):
        self.zoom = max(0.3, min(z, 5))
        self.render()

    @property
    def page(self):
        return self.doc[self.page_no]

    def to_canvas(self, rect):
        return rect * self.page.rotation_matrix * fitz.Matrix(self.zoom, self.zoom)

    def to_page(self, x0, y0, x1, y1):
        r = fitz.Rect(x0, y0, x1, y1).normalize() * fitz.Matrix(1 / self.zoom, 1 / self.zoom)
        return r * self.page.derotation_matrix

    def render(self):
        if not self.doc:
            return
        img = pil_from_page(self.page, self.zoom)
        self._photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self._photo, anchor="nw")
        self.canvas.config(scrollregion=(0, 0, img.width, img.height))
        for r in (r for g in self.marks.get(self.page_no, []) for r in g):
            c = self.to_canvas(r)
            self.canvas.create_rectangle(c.x0, c.y0, c.x1, c.y1, fill="black", stipple="gray50", outline="red")
        extra = " · texto por OCR" if self.page_no in self.ocr_words else ""
        self.page_lbl.config(text=f"{self.page_no + 1} / {len(self.doc)}")
        self.status.config(text=f"Página {self.page_no + 1}{extra}")

    # -- texto y OCR --
    def words(self, pno):
        native = core.native_words(self.doc[pno])
        return native if native else self.ocr_words.get(pno, [])

    def pages_without_text(self):
        return [i for i in range(len(self.doc))
                if i not in self.ocr_words and not core.native_words(self.doc[i])]

    def run_ocr(self, pages):
        if not core.ocr_available():
            messagebox.showerror(APP_NAME, "El OCR no está disponible en esta instalación.")
            return
        busy(self)
        try:
            for k, i in enumerate(pages, 1):
                self.status.config(text=f"Reconociendo texto… página {i + 1} ({k}/{len(pages)})")
                self.update()
                self.ocr_words[i] = core.ocr_page_words(self.doc[i])
        except Exception as ex:
            messagebox.showerror(APP_NAME, f"Error en el OCR:\n{ex}")
        finally:
            busy(self, False)
            self.render()

    def run_ocr_all(self):
        if not self.doc:
            return
        pages = self.pages_without_text()
        if not pages:
            messagebox.showinfo(APP_NAME, "Todas las páginas ya tienen texto seleccionable.")
            return
        self.run_ocr(pages)
        n = sum(len(self.ocr_words.get(i, [])) for i in pages)
        messagebox.showinfo(APP_NAME, f"OCR terminado: {n} palabras reconocidas en {len(pages)} página(s).")

    def offer_ocr(self, pages):
        if pages and core.ocr_available() and messagebox.askyesno(
                APP_NAME, f"{len(pages)} página(s) no tienen texto (parecen escaneadas).\n"
                          "¿Reconocer el texto con OCR? Puede tardar unos segundos por página."):
            self.run_ocr(pages)

    # -- selección --
    def on_press(self, e):
        if not self.doc:
            return
        x, y = self.canvas.canvasx(e.x), self.canvas.canvasy(e.y)
        self._start = (x, y)
        self._rect_id = self.canvas.create_rectangle(x, y, x, y, outline="#0af", width=2, dash=(4, 2))

    def on_drag(self, e):
        if self._start:
            self.canvas.coords(self._rect_id, *self._start, self.canvas.canvasx(e.x), self.canvas.canvasy(e.y))

    def on_release(self, e):
        if not self._start:
            return
        x0, y0 = self._start
        x1, y1 = self.canvas.canvasx(e.x), self.canvas.canvasy(e.y)
        self._start = None
        sel = self.to_page(x0, y0, x1, y1)
        if sel.width < 1 or sel.height < 1:
            self.render()
            return
        new = []
        if self.mode.get() == "text":
            if not self.words(self.page_no):
                self.offer_ocr([self.page_no])
            new = [r for r, _ in self.words(self.page_no) if r.intersects(sel)]
            if not new:
                messagebox.showinfo(APP_NAME, "No se ha encontrado texto en esa zona.\n"
                                              "Puedes usar el modo 'Área libre'.")
        else:
            new = [sel]
        if new:
            self.marks.setdefault(self.page_no, []).append(new)
        self.render()

    def undo(self):
        lst = self.marks.get(self.page_no)
        if lst:
            lst.pop()
            self.render()

    def clear_page(self):
        self.marks.pop(self.page_no, None)
        self.render()

    def search_mark(self):
        term = self.search.get().strip()
        if not self.doc or not term:
            return
        count = 0
        low = term.lower()
        for i, page in enumerate(self.doc):
            hits = page.search_for(term)
            hits += [r for r, w in self.ocr_words.get(i, []) if low in w.lower()]
            if hits:
                self.marks.setdefault(i, []).append(hits)
                count += len(hits)
        self.render()
        messagebox.showinfo(APP_NAME, f"{count} coincidencia(s) marcadas.")

    def detect(self):
        if not self.doc:
            return
        self.offer_ocr(self.pages_without_text())
        found = {}  # tipo -> [(página, [rects])]
        for i in range(len(self.doc)):
            for kind, groups in core.detect_sensitive(self.words(i)).items():
                found.setdefault(kind, []).extend((i, g) for g in groups)
        if not found:
            messagebox.showinfo(APP_NAME, "No se han encontrado datos sensibles.")
            return
        dlg = tk.Toplevel(self)
        dlg.title("Datos sensibles encontrados")
        dlg.transient(self.winfo_toplevel())
        ttk.Label(dlg, text="Marca los tipos que quieres censurar:", padding=10).pack(anchor="w")
        checks = {}
        for kind, items in found.items():
            var = tk.BooleanVar(value=kind != "Fecha")
            checks[kind] = var
            ttk.Checkbutton(dlg, text=f"{kind}  ({len(items)})", variable=var).pack(anchor="w", padx=20)

        def apply():
            n = 0
            for kind, var in checks.items():
                if var.get():
                    for pno, rects in found[kind]:
                        self.marks.setdefault(pno, []).append(rects)
                        n += 1
            dlg.destroy()
            self.render()
            self.status.config(text=f"{n} dato(s) marcados. Revisa las páginas antes de guardar.")

        ttk.Button(dlg, text="Marcar seleccionados", command=apply).pack(pady=10)
        dlg.grab_set()

    def save(self):
        if not self.doc:
            return
        marks = {p: [r for g in gs for r in g] for p, gs in self.marks.items()}
        if not any(marks.values()):
            messagebox.showinfo(APP_NAME, "No hay nada marcado para censurar.")
            return
        dst = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=PDF_TYPES,
                                           initialfile=os.path.basename(suffixed(self.src, "censurado", ".pdf")))
        if not dst:
            return
        busy(self)
        try:
            core.redact_pdf(self.doc, marks, dst, core.REDACT_STYLES[self.style.get()])
            messagebox.showinfo(APP_NAME, f"Guardado:\n{dst}")
        except Exception as ex:
            messagebox.showerror(APP_NAME, f"Error al guardar:\n{ex}")
        finally:
            busy(self, False)


# --------------------------------------------------------------------------
# Páginas
# --------------------------------------------------------------------------

class PagesTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=8)
        self.src = None
        self.doc = None
        self.items = []  # [[índice_original, giro_extra]]
        self._photo = None

        left = ttk.Frame(self)
        left.pack(side="left", fill="y")
        ttk.Button(left, text="Abrir PDF…", command=self.open).pack(fill="x")
        self.file_lbl = ttk.Label(left, text="Ningún archivo", wraplength=220)
        self.file_lbl.pack(fill="x", pady=4)
        self.lb = tk.Listbox(left, selectmode="extended", width=28, height=22)
        self.lb.pack(fill="y", expand=True)
        self.lb.bind("<<ListboxSelect>>", lambda e: self.preview())
        enable_drop(self.lb, lambda p: self.load(p[0]))

        side = ttk.Frame(self)
        side.pack(side="left", fill="y", padx=8)
        for text, cmd in [("Subir", lambda: self.move(-1)), ("Bajar", lambda: self.move(1)),
                          ("Girar ⟲ 90°", lambda: self.rotate(-90)), ("Girar ⟳ 90°", lambda: self.rotate(90)),
                          ("Eliminar", self.delete), (None, None),
                          ("Guardar PDF…", self.save), ("Extraer seleccionadas…", self.extract),
                          ("Dividir: una por archivo…", self.split_each), ("Dividir por rangos…", self.split_ranges)]:
            if text is None:
                ttk.Separator(side).pack(fill="x", pady=10)
            else:
                ttk.Button(side, text=text, command=cmd).pack(fill="x", pady=2)

        self.canvas = tk.Canvas(self, bg="#444", highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.preview())
        enable_drop(self.canvas, lambda p: self.load(p[0]))

    def open(self):
        path = filedialog.askopenfilename(filetypes=DOC_TYPES)
        if path:
            self.load(path)

    def load(self, path):
        try:
            doc = core.open_as_pdf(path)
        except Exception as ex:
            messagebox.showerror(APP_NAME, f"No se pudo abrir:\n{ex}")
            return
        if self.doc:
            self.doc.close()
        self.src, self.doc = path, doc
        self.items = [[i, 0] for i in range(len(doc))]
        self.file_lbl.config(text=f"{os.path.basename(path)} ({len(doc)} págs.)")
        self.refresh()
        self.lb.selection_set(0)
        self.preview()

    def refresh(self, select=()):
        self.lb.delete(0, "end")
        for idx, rot in self.items:
            self.lb.insert("end", f"Página {idx + 1}" + (f"   (girada {rot}°)" if rot else ""))
        for i in select:
            self.lb.selection_set(i)

    def sel(self):
        return list(self.lb.curselection())

    def preview(self):
        s = self.sel()
        self.canvas.delete("all")
        if not self.doc or not s:
            return
        idx, rot = self.items[s[0]]
        cw, ch = max(50, self.canvas.winfo_width()), max(50, self.canvas.winfo_height())
        img = pil_from_page(self.doc[idx], 1.0).rotate(-rot, expand=True)
        img.thumbnail((cw - 10, ch - 10))
        self._photo = ImageTk.PhotoImage(img)
        self.canvas.create_image(cw // 2, ch // 2, image=self._photo)

    def move(self, d):
        s = self.sel()
        if not s or min(s) + d < 0 or max(s) + d >= len(self.items):
            return
        for i in (s if d < 0 else reversed(s)):
            self.items[i], self.items[i + d] = self.items[i + d], self.items[i]
        self.refresh([i + d for i in s])

    def rotate(self, deg):
        s = self.sel()
        for i in s:
            self.items[i][1] = (self.items[i][1] + deg) % 360
        self.refresh(s)
        self.preview()

    def delete(self):
        s = self.sel()
        if s and len(s) < len(self.items):
            for i in reversed(s):
                del self.items[i]
            self.refresh()
            self.preview()

    def _ask_save(self, suffix):
        return filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=PDF_TYPES,
                                            initialfile=os.path.basename(suffixed(self.src, suffix, ".pdf")))

    def _done(self, paths):
        messagebox.showinfo(APP_NAME, f"{len(paths)} archivo(s) guardados:\n" + "\n".join(paths[:10]) +
                            ("\n…" if len(paths) > 10 else ""))

    def save(self):
        if self.doc:
            dst = self._ask_save("editado")
            if dst:
                core.save_pages(self.src, self.items, dst)
                self._done([dst])

    def extract(self):
        s = self.sel()
        if self.doc and s:
            dst = self._ask_save("extracto")
            if dst:
                core.save_pages(self.src, [self.items[i] for i in s], dst)
                self._done([dst])

    def _split(self, groups, names):
        folder = filedialog.askdirectory(title="Carpeta de destino")
        if not folder:
            return
        base = os.path.splitext(os.path.basename(self.src))[0]
        paths = []
        for g, name in zip(groups, names):
            dst = os.path.join(folder, f"{base}_{name}.pdf")
            core.save_pages(self.src, [self.items[i] for i in g], dst)
            paths.append(dst)
        self._done(paths)

    def split_each(self):
        if self.doc:
            n = len(self.items)
            self._split([[i] for i in range(n)], [f"p{i + 1}" for i in range(n)])

    def split_ranges(self):
        if not self.doc:
            return
        spec = simpledialog.askstring(APP_NAME, "Rangos de páginas (según el orden actual).\n"
                                                "Ejemplo: 1-3, 4-6, 7-", parent=self)
        if not spec:
            return
        try:
            groups = core.parse_ranges(spec, len(self.items))
        except ValueError as ex:
            messagebox.showerror(APP_NAME, str(ex))
            return
        self._split(groups, [f"{g[0] + 1}-{g[-1] + 1}" if len(g) > 1 else f"{g[0] + 1}" for g in groups])


# --------------------------------------------------------------------------
# Proteger con contraseña
# --------------------------------------------------------------------------

class ProtectTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=16)
        self.src = None
        ttk.Button(self, text="Abrir PDF o imagen…", command=self.open).grid(row=0, column=0, sticky="w")
        self.file_lbl = ttk.Label(self, text="Ningún archivo (puedes arrastrarlo aquí)")
        self.file_lbl.grid(row=0, column=1, columnspan=2, sticky="w", padx=8)

        box = ttk.LabelFrame(self, text="Poner contraseña", padding=12)
        box.grid(row=1, column=0, columnspan=3, sticky="ew", pady=12)
        self.pw1, self.pw2, self.owner = tk.StringVar(), tk.StringVar(), tk.StringVar()
        for r, (label, var) in enumerate([("Contraseña para abrir:", self.pw1), ("Repetir contraseña:", self.pw2),
                                          ("Contraseña de propietario (opcional):", self.owner)]):
            ttk.Label(box, text=label).grid(row=r, column=0, sticky="w", pady=3)
            ttk.Entry(box, textvariable=var, show="•", width=30).grid(row=r, column=1, sticky="w", padx=8)
        self.p_print, self.p_copy, self.p_edit = tk.BooleanVar(value=True), tk.BooleanVar(), tk.BooleanVar()
        ttk.Checkbutton(box, text="Permitir imprimir", variable=self.p_print).grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Checkbutton(box, text="Permitir copiar texto", variable=self.p_copy).grid(row=4, column=0, sticky="w")
        ttk.Checkbutton(box, text="Permitir modificar", variable=self.p_edit).grid(row=5, column=0, sticky="w")
        ttk.Label(box, foreground="gray", wraplength=520,
                  text="Cifrado AES-256. La contraseña de propietario permite cambiar los permisos; "
                       "si la dejas vacía se genera una aleatoria.").grid(row=6, column=0, columnspan=2, sticky="w", pady=6)
        ttk.Button(box, text="Proteger y guardar…", command=self.protect).grid(row=7, column=0, sticky="w")

        box2 = ttk.LabelFrame(self, text="Quitar contraseña", padding=12)
        box2.grid(row=2, column=0, columnspan=3, sticky="ew")
        self.pw_rm = tk.StringVar()
        ttk.Label(box2, text="Contraseña actual:").grid(row=0, column=0, sticky="w")
        ttk.Entry(box2, textvariable=self.pw_rm, show="•", width=30).grid(row=0, column=1, padx=8)
        ttk.Button(box2, text="Quitar y guardar…", command=self.unprotect).grid(row=0, column=2)
        enable_drop(self, lambda p: self.load(p[0]))

    def open(self):
        path = filedialog.askopenfilename(filetypes=DOC_TYPES)
        if path:
            self.load(path)

    def load(self, path):
        self.src = path
        self.file_lbl.config(text=os.path.basename(path))

    def protect(self):
        if not self.src:
            return messagebox.showinfo(APP_NAME, "Primero abre un archivo.")
        if not self.pw1.get():
            return messagebox.showerror(APP_NAME, "Escribe una contraseña.")
        if self.pw1.get() != self.pw2.get():
            return messagebox.showerror(APP_NAME, "Las contraseñas no coinciden.")
        dst = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=PDF_TYPES,
                                           initialfile=os.path.basename(suffixed(self.src, "protegido", ".pdf")))
        if not dst:
            return
        try:
            core.encrypt_pdf(self.src, dst, self.pw1.get(), self.owner.get(),
                             self.p_print.get(), self.p_copy.get(), self.p_edit.get())
            messagebox.showinfo(APP_NAME, f"Guardado:\n{dst}")
        except Exception as ex:
            messagebox.showerror(APP_NAME, f"Error:\n{ex}")

    def unprotect(self):
        if not self.src:
            return messagebox.showinfo(APP_NAME, "Primero abre un archivo.")
        dst = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=PDF_TYPES,
                                           initialfile=os.path.basename(suffixed(self.src, "sin_clave", ".pdf")))
        if not dst:
            return
        try:
            core.decrypt_pdf(self.src, dst, self.pw_rm.get())
            messagebox.showinfo(APP_NAME, f"Guardado:\n{dst}")
        except Exception as ex:
            messagebox.showerror(APP_NAME, f"Error:\n{ex}")


# --------------------------------------------------------------------------
# Pestañas con lista de archivos
# --------------------------------------------------------------------------

class FileListTab(ttk.Frame):
    types = DOC_TYPES

    def __init__(self, master, intro, reorder):
        super().__init__(master, padding=8)
        ttk.Label(self, text=intro, wraplength=760).pack(anchor="w", pady=(0, 6))
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        self.lb = tk.Listbox(body, selectmode="extended")
        self.lb.pack(side="left", fill="both", expand=True)
        self.paths = []
        side = ttk.Frame(body)
        side.pack(side="left", fill="y", padx=8)
        ttk.Button(side, text="Añadir…", command=self.add).pack(fill="x")
        ttk.Button(side, text="Quitar", command=self.remove).pack(fill="x", pady=4)
        if reorder:
            ttk.Button(side, text="Subir", command=lambda: self.move(-1)).pack(fill="x")
            ttk.Button(side, text="Bajar", command=lambda: self.move(1)).pack(fill="x", pady=4)
        self.side = side
        enable_drop(self.lb, self.add_paths)

    def refresh(self):
        self.lb.delete(0, "end")
        for p in self.paths:
            self.lb.insert("end", os.path.basename(p))

    def add_paths(self, paths):
        self.paths.extend(p for p in paths if os.path.isfile(p))
        self.refresh()

    def add(self):
        self.add_paths(filedialog.askopenfilenames(filetypes=self.types))

    def remove(self):
        for i in reversed(self.lb.curselection()):
            del self.paths[i]
        self.refresh()

    def move(self, d):
        sel = self.lb.curselection()
        if len(sel) != 1:
            return
        i, j = sel[0], sel[0] + d
        if 0 <= j < len(self.paths):
            self.paths[i], self.paths[j] = self.paths[j], self.paths[i]
            self.refresh()
            self.lb.selection_set(j)

    def run_each(self, func, label):
        """Ejecuta func(ruta, carpeta) para cada archivo y muestra un resumen."""
        if not self.paths:
            return messagebox.showinfo(APP_NAME, "Añade algún archivo a la lista.")
        folder = filedialog.askdirectory(title="Carpeta de destino")
        if not folder:
            return
        lines, errors = [], []
        busy(self)
        for p in self.paths:
            try:
                lines.append(func(p, folder))
            except Exception as ex:
                errors.append(f"{os.path.basename(p)}: {ex}")
        busy(self, False)
        msg = f"{label}: {len(lines)} archivo(s).\n" + "\n".join(l for l in lines if l)
        if errors:
            msg += "\n\nErrores:\n" + "\n".join(errors)
        messagebox.showinfo(APP_NAME, msg)


class ToolsTab(FileListTab):
    def __init__(self, master):
        super().__init__(master, "Comprime PDFs para enviarlos por email, convierte las páginas de un PDF "
                                 "en imágenes o cada imagen en un PDF. Añade o arrastra archivos a la lista.",
                         reorder=False)
        s = self.side
        ttk.Separator(s).pack(fill="x", pady=10)
        ttk.Label(s, text="Compresión:").pack(anchor="w")
        self.level = tk.StringVar(value="Media")
        ttk.Combobox(s, textvariable=self.level, values=list(core.COMPRESS_LEVELS), state="readonly",
                     width=18).pack(fill="x")
        ttk.Button(s, text="Comprimir PDFs…", command=self.compress).pack(fill="x", pady=4)
        ttk.Separator(s).pack(fill="x", pady=10)
        ttk.Label(s, text="PDF → imágenes:").pack(anchor="w")
        f = ttk.Frame(s)
        f.pack(fill="x")
        self.img_fmt = tk.StringVar(value="png")
        ttk.Combobox(f, textvariable=self.img_fmt, values=["png", "jpg"], state="readonly", width=5).pack(side="left")
        self.dpi = tk.IntVar(value=200)
        ttk.Spinbox(f, from_=72, to=600, increment=50, textvariable=self.dpi, width=5).pack(side="left", padx=4)
        ttk.Label(f, text="ppp").pack(side="left")
        ttk.Button(s, text="Convertir a imágenes…", command=self.to_images).pack(fill="x", pady=4)
        ttk.Separator(s).pack(fill="x", pady=10)
        ttk.Button(s, text="Imágenes → PDF (uno por archivo)…", command=self.to_pdf).pack(fill="x")

    def compress(self):
        def job(p, folder):
            if ext_of(p) != ".pdf":
                raise ValueError("no es un PDF")
            dst = os.path.join(folder, os.path.basename(suffixed(p, "comprimido")))
            before, after = core.compress_pdf(p, dst, self.level.get())
            return f"{os.path.basename(p)}: {before / 1024:.0f} KB → {after / 1024:.0f} KB"
        self.run_each(job, "Comprimidos")

    def to_images(self):
        def job(p, folder):
            if ext_of(p) != ".pdf":
                raise ValueError("no es un PDF")
            n = len(core.pdf_to_images(p, folder, self.img_fmt.get(), int(self.dpi.get())))
            return f"{os.path.basename(p)}: {n} imagen(es)"
        self.run_each(job, "Convertidos")

    def to_pdf(self):
        def job(p, folder):
            dst = os.path.join(folder, os.path.splitext(os.path.basename(p))[0] + ".pdf")
            core.merge_files([p], dst)
            return os.path.basename(dst)
        self.run_each(job, "Convertidos")


class SanitizeTab(FileListTab):
    types = [("Soportados", "*.pdf *.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp *.gif "
                            "*.docx *.xlsx *.pptx *.odt *.ods *.odp"), ("Todos", "*.*")]

    def __init__(self, master):
        super().__init__(master, "Elimina metadatos (autor, software, fechas, GPS/EXIF, XMP, JavaScript, "
                                 "adjuntos y miniaturas en PDF). Se guarda una copia con el sufijo _limpio.",
                         reorder=False)
        ttk.Button(self.side, text="Limpiar todo…", command=self.run).pack(fill="x", pady=(16, 0))

    def run(self):
        def job(p, folder):
            core.sanitize_file(p, os.path.join(folder, os.path.basename(suffixed(p, "limpio"))))
            return ""
        self.run_each(job, "Limpiados")


class MergeTab(FileListTab):
    def __init__(self, master):
        super().__init__(master, "Une varios PDFs (y/o imágenes) en un único PDF, en el orden de la lista.",
                         reorder=True)
        ttk.Button(self.side, text="Unir y guardar…", command=self.run).pack(fill="x", pady=(16, 0))

    def run(self):
        if len(self.paths) < 2:
            return messagebox.showinfo(APP_NAME, "Añade al menos dos archivos.")
        dst = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=PDF_TYPES, initialfile="unido.pdf")
        if not dst:
            return
        try:
            core.merge_files(self.paths, dst)
            messagebox.showinfo(APP_NAME, f"Guardado:\n{dst}")
        except Exception as ex:
            messagebox.showerror(APP_NAME, f"Error al unir:\n{ex}")


def build(root):
    root.title(APP_NAME)
    root.geometry("1180x820")
    icon = core.resource_path("icon.png")
    if os.path.exists(icon):
        root._icon = ImageTk.PhotoImage(Image.open(icon).resize((128, 128)))
        root.iconphoto(True, root._icon)
    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)
    tabs = [(WatermarkTab, "Marca de agua"), (RedactTab, "Censurar"), (PagesTab, "Páginas"),
            (ProtectTab, "Contraseña"), (ToolsTab, "Comprimir y convertir"),
            (SanitizeTab, "Limpiar metadatos"), (MergeTab, "Unir PDFs")]
    for cls, name in tabs:
        nb.add(cls(nb), text=name)
    return nb


def selftest():
    """Comprueba el núcleo sin abrir la ventana (útil tras compilar): DocGuard --selftest"""
    import tempfile
    doc = fitz.open()
    doc.new_page().insert_text((50, 80), "DNI 12345678Z", fontsize=14)
    pix = doc[0].get_pixmap(dpi=200)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    core.apply_watermark(img, "test {fecha}")
    with tempfile.TemporaryDirectory() as tmp:
        scan = os.path.join(tmp, "scan.png")
        img.save(scan)
        with core.open_as_pdf(scan) as sd:
            found = core.detect_sensitive(core.ocr_page_words(sd[0]))
    ok = "DNI / NIE" in found
    print("selftest", "OK" if ok else f"FALLO: {found}", "| arrastrar y soltar:", HAS_DND)
    return ok


def main():
    import sys
    if "--selftest" in sys.argv:
        sys.exit(0 if selftest() else 1)
    root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
    build(root)
    root.mainloop()


if __name__ == "__main__":
    main()
