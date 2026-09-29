"""DocGuard - herramienta local para proteger documentos.

Funciones:
  1. Marca de agua resistente (tramada, con variaciones aleatorias y rasterizada).
  2. Censura real de PDF seleccionando texto (o áreas) con cuadros negros.
  3. Limpieza de metadatos (PDF, imágenes, documentos Office).
  4. Unión de PDFs (e imágenes) en un único PDF.

Todo se procesa en local; ningún archivo sale del equipo.
"""

import io
import math
import os
import random
import sys
import zipfile
from functools import lru_cache
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageTk

APP_NAME = "DocGuard"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp", ".gif"}
OFFICE_EXTS = {".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp"}
RENDER_DPI = 200

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


@lru_cache(maxsize=64)
def get_font(size):
    size = max(6, int(size))
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    return ImageFont.load_default(size=size)


def ext_of(path):
    return os.path.splitext(path)[1].lower()


def suffixed(path, suffix, new_ext=None):
    base, ext = os.path.splitext(path)
    return f"{base}_{suffix}{new_ext or ext}"


# --------------------------------------------------------------------------
# Carga de documentos como imágenes
# --------------------------------------------------------------------------

def load_pages(path, dpi=RENDER_DPI):
    """Devuelve una lista de (PIL.Image RGB, (ancho_pt, alto_pt) o None)."""
    if ext_of(path) == ".pdf":
        pages = []
        with fitz.open(path) as doc:
            for page in doc:
                pix = page.get_pixmap(dpi=dpi, alpha=False)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                pages.append((img, (page.rect.width, page.rect.height)))
        return pages
    img = Image.open(path)
    img = ImageOps.exif_transpose(img).convert("RGB")
    return [(img, None)]


# --------------------------------------------------------------------------
# Marca de agua
# --------------------------------------------------------------------------

def apply_watermark(img, text, angle=35, size=40, gap_x=60, gap_y=80,
                    opacity=0.35, color=(200, 0, 0), hardened=True, seed=1):
    """Aplica una marca de agua en mosaico.

    Los tamaños se expresan en milésimas del ancho de la imagen, así la vista
    previa y el resultado final se ven igual a cualquier resolución.
    Con `hardened` se añaden variaciones aleatorias (posición, opacidad,
    tamaño), líneas onduladas entrelazadas y ruido, lo que dificulta mucho
    que herramientas de IA puedan eliminar la marca limpiamente.
    """
    rnd = random.Random(seed)
    base = img.convert("RGBA")
    W, H = base.size
    s = W / 1000.0
    diag = int(math.hypot(W, H)) + 4
    layer = Image.new("RGBA", (diag, diag), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    font = get_font(size * s)
    l, t, r, b = draw.textbbox((0, 0), text, font=font)
    tw, th = r - l, b - t
    step_x = tw + max(1, gap_x * s)
    step_y = th + max(1, gap_y * s)
    a_max = int(255 * opacity)

    row = 0
    y = -step_y
    while y < diag + step_y:
        x = -step_x + (step_x / 2 if row % 2 else 0)
        while x < diag + step_x:
            jx = jy = 0
            f = font
            alpha = a_max
            if hardened:
                jx = rnd.uniform(-0.05, 0.05) * step_x
                jy = rnd.uniform(-0.25, 0.25) * th
                alpha = int(a_max * rnd.uniform(0.7, 1.0))
                f = get_font(size * s * rnd.uniform(0.9, 1.1))
            draw.text((x + jx, y + jy), text, font=f, fill=color + (alpha,),
                      stroke_width=max(1, int(s)) if hardened else 0,
                      stroke_fill=(255, 255, 255, alpha // 3) if hardened else None)
            x += step_x
        if hardened:
            # Línea ondulada entre filas: rompe patrones regulares fáciles de borrar.
            ly = y + th + (step_y - th) / 2
            amp = max(2.0, (step_y - th) * 0.3)
            period = max(20.0, step_x / 2)
            phase = rnd.uniform(0, math.tau)
            pts = [(px, ly + amp * math.sin(px / period * math.tau + phase))
                   for px in range(0, diag, max(2, int(3 * s)))]
            draw.line(pts, fill=color + (int(a_max * 0.45),), width=max(1, int(1.5 * s)))
        y += step_y
        row += 1

    layer = layer.rotate(angle, resample=Image.BICUBIC)
    left, top = (diag - W) // 2, (diag - H) // 2
    layer = layer.crop((left, top, left + W, top + H))
    out = Image.alpha_composite(base, layer).convert("RGB")

    if hardened:
        noise = Image.effect_noise((W, H), 24).convert("RGB")
        out = Image.blend(out, noise, 0.035)
    return out


def fit_size(img, width=None, height=None):
    """Redimensiona a width x height píxeles. Si solo se da uno, mantiene la proporción."""
    if not width and not height:
        return img
    w = width or round(img.width * height / img.height)
    h = height or round(img.height * width / img.width)
    return img.resize((max(1, int(w)), max(1, int(h))), Image.LANCZOS)


def export_watermarked(src, dst, params, width=None, height=None):
    """Exporta con marca de agua. El formato sale de la extensión de `dst`
    (.pdf, .png, .jpg). Si el origen tiene varias páginas y se exporta como
    imagen, se guarda un archivo por página (_p1, _p2...). Devuelve las rutas."""
    pages = load_pages(src)
    fmt = ext_of(dst)
    marked = [(apply_watermark(fit_size(img, width, height), seed=1000 + i, **params), size_pt)
              for i, (img, size_pt) in enumerate(pages)]
    if fmt == ".pdf":
        out = fitz.open()
        for wm, size_pt in marked:
            buf = io.BytesIO()
            wm.save(buf, "JPEG", quality=90)
            if size_pt is None or width or height:
                size_pt = (wm.width * 72 / RENDER_DPI, wm.height * 72 / RENDER_DPI)
            page = out.new_page(width=size_pt[0], height=size_pt[1])
            page.insert_image(page.rect, stream=buf.getvalue())
        out.set_metadata({})
        out.save(dst, garbage=4, deflate=True)
        out.close()
        return [dst]
    paths = []
    for i, (wm, _) in enumerate(marked):
        path = dst if len(marked) == 1 else suffixed(dst, f"p{i + 1}")
        if fmt in (".jpg", ".jpeg"):
            wm.save(path, "JPEG", quality=92)
        else:
            wm.save(path, "PNG")
        paths.append(path)
    return paths


# --------------------------------------------------------------------------
# Limpieza de metadatos
# --------------------------------------------------------------------------

EMPTY_CORE = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/'
    'metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" '
    'xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/'
    'dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"/>'
)
EMPTY_ODF_META = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<office:document-meta xmlns:office="urn:oasis:names:tc:opendocument:xmlns:'
    'office:1.0" office:version="1.2"><office:meta/></office:document-meta>'
)


def sanitize_file(src, dst):
    ext = ext_of(src)
    if ext == ".pdf":
        with fitz.open(src) as doc:
            doc.scrub()  # metadatos, XMP, JavaScript, adjuntos, miniaturas, texto oculto...
            doc.set_metadata({})
            doc.del_xml_metadata()
            doc.save(dst, garbage=4, deflate=True, clean=True)
    elif ext in IMAGE_EXTS:
        img = Image.open(src)
        img = ImageOps.exif_transpose(img)
        clean = img.copy()
        # Solo se conservan los píxeles (y la transparencia); fuera EXIF, XMP, ICC, textos...
        clean.info = {k: v for k, v in img.info.items() if k == "transparency"}
        if ext in (".jpg", ".jpeg"):
            clean.convert("RGB").save(dst, "JPEG", quality=95)
        else:
            clean.save(dst)
    elif ext in OFFICE_EXTS:
        with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "docProps/core.xml":
                    data = EMPTY_CORE.encode()
                elif item.filename == "meta.xml":
                    data = EMPTY_ODF_META.encode()
                info = zipfile.ZipInfo(item.filename, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_STORED if item.filename == "mimetype" else zipfile.ZIP_DEFLATED
                zout.writestr(info, data)
    else:
        raise ValueError(f"Formato no soportado: {ext}")


# --------------------------------------------------------------------------
# Unión
# --------------------------------------------------------------------------

def merge_files(paths, dst):
    out = fitz.open()
    for p in paths:
        if ext_of(p) == ".pdf":
            with fitz.open(p) as d:
                out.insert_pdf(d)
        else:
            with fitz.open(p) as img:
                with fitz.open("pdf", img.convert_to_pdf()) as d:
                    out.insert_pdf(d)
    out.set_metadata({})
    out.save(dst, garbage=4, deflate=True)
    out.close()


# --------------------------------------------------------------------------
# Interfaz
# --------------------------------------------------------------------------

DOC_TYPES = [("Documentos", "*.pdf *.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp"),
             ("Todos", "*.*")]


class WatermarkTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=8)
        self.src = None
        self.preview_src = None
        self.color = (200, 0, 0)
        self._job = None
        self._photo = None

        ctrl = ttk.Frame(self)
        ctrl.pack(side="left", fill="y", padx=(0, 8))
        ttk.Button(ctrl, text="Abrir documento…", command=self.open).pack(fill="x")
        self.file_lbl = ttk.Label(ctrl, text="Ningún archivo", wraplength=230)
        self.file_lbl.pack(fill="x", pady=4)

        ttk.Label(ctrl, text="Texto de la marca:").pack(anchor="w", pady=(8, 0))
        self.text = tk.StringVar(value="Solo para uso de XXX")
        e = ttk.Entry(ctrl, textvariable=self.text, width=32)
        e.pack(fill="x")
        self.text.trace_add("write", lambda *_: self.schedule())

        self.vars = {}
        for key, label, lo, hi, val in [
            ("angle", "Orientación (°)", -90, 90, 35),
            ("size", "Tamaño del texto", 10, 150, 40),
            ("gap_x", "Separación horizontal", 0, 400, 60),
            ("gap_y", "Separación vertical", 0, 400, 80),
            ("opacity", "Opacidad (%)", 5, 100, 35),
        ]:
            var = tk.DoubleVar(value=val)
            self.vars[key] = var
            row = ttk.Frame(ctrl)
            row.pack(fill="x", pady=(8, 0))
            ttk.Label(row, text=label).pack(side="left")
            val_lbl = ttk.Label(row, text=str(val))
            val_lbl.pack(side="right")
            ttk.Scale(ctrl, from_=lo, to=hi, variable=var,
                      command=lambda v, l=val_lbl: (l.config(text=str(int(float(v)))), self.schedule())
                      ).pack(fill="x")

        self.color_btn = tk.Button(ctrl, text="Color", bg="#c80000", fg="white",
                                   command=self.pick_color)
        self.color_btn.pack(fill="x", pady=(10, 0))
        self.hardened = tk.BooleanVar(value=True)
        ttk.Checkbutton(ctrl, text="Protección anti-IA (recomendado)", variable=self.hardened,
                        command=self.schedule).pack(anchor="w", pady=6)
        ttk.Label(ctrl, wraplength=230, foreground="gray",
                  text="Añade variaciones aleatorias, líneas entrelazadas y ruido, "
                       "y rasteriza el resultado (el PDF no tiene capa de texto "
                       "que se pueda quitar).").pack(fill="x")
        ttk.Label(ctrl, text="Exportar como:").pack(anchor="w", pady=(10, 0))
        self.fmt = tk.StringVar(value="PDF")
        fr = ttk.Frame(ctrl)
        fr.pack(fill="x")
        for f in ("PDF", "JPG", "PNG"):
            ttk.Radiobutton(fr, text=f, value=f, variable=self.fmt).pack(side="left")
        ttk.Label(ctrl, text="Tamaño en píxeles (opcional):").pack(anchor="w", pady=(8, 0))
        fr = ttk.Frame(ctrl)
        fr.pack(fill="x")
        self.out_w, self.out_h = tk.StringVar(), tk.StringVar()
        ttk.Entry(fr, textvariable=self.out_w, width=7).pack(side="left")
        ttk.Label(fr, text=" × ").pack(side="left")
        ttk.Entry(fr, textvariable=self.out_h, width=7).pack(side="left")
        ttk.Label(ctrl, wraplength=230, foreground="gray",
                  text="Vacío = tamaño original. Si rellenas solo uno, "
                       "se mantiene la proporción.").pack(fill="x")
        ttk.Button(ctrl, text="Guardar con marca de agua…", command=self.save).pack(fill="x", pady=12)

        self.canvas = tk.Canvas(self, bg="#444", highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.schedule())

    def params(self):
        v = {k: var.get() for k, var in self.vars.items()}
        v["opacity"] /= 100.0
        return dict(text=self.text.get() or " ", color=self.color,
                    hardened=self.hardened.get(), **v)

    def open(self):
        path = filedialog.askopenfilename(filetypes=DOC_TYPES)
        if not path:
            return
        try:
            img, _ = load_pages(path, dpi=100)[0]
        except Exception as ex:
            messagebox.showerror(APP_NAME, f"No se pudo abrir:\n{ex}")
            return
        self.src = path
        self.preview_src = img
        self.file_lbl.config(text=os.path.basename(path))
        self.schedule()

    def pick_color(self):
        rgb, hx = colorchooser.askcolor(color="#%02x%02x%02x" % self.color)
        if rgb:
            self.color = tuple(int(c) for c in rgb)
            self.color_btn.config(bg=hx)
            self.schedule()

    def schedule(self):
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(120, self.render)

    def render(self):
        self._job = None
        if self.preview_src is None:
            return
        cw, ch = max(50, self.canvas.winfo_width()), max(50, self.canvas.winfo_height())
        img = self.preview_src.copy()
        img.thumbnail((cw - 10, ch - 10))
        wm = apply_watermark(img, seed=1000, **self.params())
        self._photo = ImageTk.PhotoImage(wm)
        self.canvas.delete("all")
        self.canvas.create_image(cw // 2, ch // 2, image=self._photo)

    def save(self):
        if not self.src:
            messagebox.showinfo(APP_NAME, "Primero abre un documento.")
            return
        try:
            w = int(self.out_w.get()) if self.out_w.get().strip() else None
            h = int(self.out_h.get()) if self.out_h.get().strip() else None
            if (w is not None and w <= 0) or (h is not None and h <= 0):
                raise ValueError
        except ValueError:
            messagebox.showerror(APP_NAME, "El tamaño debe ser un número entero de píxeles.")
            return
        ext = "." + self.fmt.get().lower()
        dst = filedialog.asksaveasfilename(
            defaultextension=ext, initialfile=os.path.basename(suffixed(self.src, "marca", ext)),
            filetypes=[(self.fmt.get(), "*" + ext)])
        if not dst:
            return
        if ext_of(dst) != ext:
            dst += ext
        self.config(cursor="watch")
        self.update()
        try:
            paths = export_watermarked(self.src, dst, self.params(), w, h)
            messagebox.showinfo(APP_NAME, "Guardado:\n" + "\n".join(paths))
        except Exception as ex:
            messagebox.showerror(APP_NAME, f"Error al guardar:\n{ex}")
        finally:
            self.config(cursor="")


class RedactTab(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=8)
        self.doc = None
        self.src = None
        self.page_no = 0
        self.zoom = 1.3
        self.marks = {}  # nº página -> [[fitz.Rect], ...] (grupos)
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

        bar2 = ttk.Frame(self)
        bar2.pack(fill="x", pady=6)
        ttk.Label(bar2, text="Buscar y censurar:").pack(side="left")
        self.search = tk.StringVar()
        ttk.Entry(bar2, textvariable=self.search, width=24).pack(side="left", padx=4)
        ttk.Button(bar2, text="Marcar en todo el documento", command=self.search_mark).pack(side="left")
        ttk.Button(bar2, text="Deshacer", command=self.undo).pack(side="left", padx=(12, 0))
        ttk.Button(bar2, text="Limpiar página", command=self.clear_page).pack(side="left")
        ttk.Button(bar2, text="Aplicar censura y guardar…", command=self.save).pack(side="right")

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
        ttk.Label(self, foreground="gray",
                  text="Arrastra sobre el texto para marcarlo. La censura elimina el texto "
                       "y los píxeles de imagen subyacentes (no es solo un recuadro encima).").pack(anchor="w")

    # -- documento --
    def open(self):
        path = filedialog.askopenfilename(filetypes=DOC_TYPES)
        if not path:
            return
        try:
            doc = fitz.open(path)
            if not doc.is_pdf:
                pdf = doc.convert_to_pdf()
                doc.close()
                doc = fitz.open("pdf", pdf)
        except Exception as ex:
            messagebox.showerror(APP_NAME, f"No se pudo abrir:\n{ex}")
            return
        if self.doc:
            self.doc.close()
        self.doc, self.src, self.marks = doc, path, {}
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
        pix = self.page.get_pixmap(matrix=fitz.Matrix(self.zoom, self.zoom), alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        self._photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self._photo, anchor="nw")
        self.canvas.config(scrollregion=(0, 0, pix.width, pix.height))
        for r in (r for g in self.marks.get(self.page_no, []) for r in g):
            c = self.to_canvas(r)
            self.canvas.create_rectangle(c.x0, c.y0, c.x1, c.y1, fill="black",
                                         stipple="gray50", outline="red")
        self.page_lbl.config(text=f"{self.page_no + 1} / {len(self.doc)}")

    # -- selección --
    def on_press(self, e):
        if not self.doc:
            return
        x, y = self.canvas.canvasx(e.x), self.canvas.canvasy(e.y)
        self._start = (x, y)
        self._rect_id = self.canvas.create_rectangle(x, y, x, y, outline="#0af", width=2, dash=(4, 2))

    def on_drag(self, e):
        if self._start:
            self.canvas.coords(self._rect_id, *self._start,
                               self.canvas.canvasx(e.x), self.canvas.canvasy(e.y))

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
            for w in self.page.get_text("words"):
                wr = fitz.Rect(w[:4])
                if wr.intersects(sel):
                    new.append(wr)
            if not new:
                messagebox.showinfo(APP_NAME, "No se ha encontrado texto en esa zona.\n"
                                    "Si es un documento escaneado, usa el modo 'Área libre'.")
        else:
            new.append(sel)
        if new:
            self.marks.setdefault(self.page_no, []).append(new)  # un grupo por selección
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
        for i, page in enumerate(self.doc):
            hits = page.search_for(term)
            if hits:
                self.marks.setdefault(i, []).append(hits)
                count += len(hits)
        self.render()
        messagebox.showinfo(APP_NAME, f"{count} coincidencia(s) marcadas.")

    def save(self):
        if not self.doc:
            return
        if not any(self.marks.values()):
            messagebox.showinfo(APP_NAME, "No hay nada marcado para censurar.")
            return
        dst = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
            initialfile=os.path.basename(suffixed(self.src, "censurado", ".pdf")))
        if not dst:
            return
        try:
            data = self.doc.tobytes()
            with fitz.open("pdf", data) as out:
                for pno, groups in self.marks.items():
                    page = out[pno]
                    for r in (r for g in groups for r in g):
                        page.add_redact_annot(r, fill=(0, 0, 0))
                    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS)
                out.scrub()
                out.set_metadata({})
                out.save(dst, garbage=4, deflate=True, clean=True)
            messagebox.showinfo(APP_NAME, f"Guardado:\n{dst}")
        except Exception as ex:
            messagebox.showerror(APP_NAME, f"Error al guardar:\n{ex}")


class FileListTab(ttk.Frame):
    """Base para pestañas con una lista de archivos."""

    types = DOC_TYPES

    def __init__(self, master, intro, reorder):
        super().__init__(master, padding=8)
        ttk.Label(self, text=intro, wraplength=700).pack(anchor="w", pady=(0, 6))
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

    def refresh(self):
        self.lb.delete(0, "end")
        for p in self.paths:
            self.lb.insert("end", os.path.basename(p))

    def add(self):
        self.paths.extend(filedialog.askopenfilenames(filetypes=self.types))
        self.refresh()

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


class SanitizeTab(FileListTab):
    types = [("Soportados", "*.pdf *.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp *.gif "
                            "*.docx *.xlsx *.pptx *.odt *.ods *.odp"), ("Todos", "*.*")]

    def __init__(self, master):
        super().__init__(master, "Elimina metadatos (autor, software, fechas, GPS/EXIF, XMP, "
                                 "JavaScript, adjuntos y miniaturas en PDF). Se guarda una copia "
                                 "con el sufijo _limpio en la carpeta elegida.", reorder=False)
        ttk.Button(self.side, text="Limpiar todo…", command=self.run).pack(fill="x", pady=(16, 0))

    def run(self):
        if not self.paths:
            return
        folder = filedialog.askdirectory(title="Carpeta de destino")
        if not folder:
            return
        ok, errors = 0, []
        for p in self.paths:
            dst = os.path.join(folder, os.path.basename(suffixed(p, "limpio")))
            try:
                sanitize_file(p, dst)
                ok += 1
            except Exception as ex:
                errors.append(f"{os.path.basename(p)}: {ex}")
        msg = f"{ok} archivo(s) limpiados."
        if errors:
            msg += "\n\nErrores:\n" + "\n".join(errors)
        messagebox.showinfo(APP_NAME, msg)


class MergeTab(FileListTab):
    def __init__(self, master):
        super().__init__(master, "Une varios PDFs (y/o imágenes) en un único PDF, en el orden de la lista.",
                         reorder=True)
        ttk.Button(self.side, text="Unir y guardar…", command=self.run).pack(fill="x", pady=(16, 0))

    def run(self):
        if len(self.paths) < 2:
            messagebox.showinfo(APP_NAME, "Añade al menos dos archivos.")
            return
        dst = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
                                           initialfile="unido.pdf")
        if not dst:
            return
        try:
            merge_files(self.paths, dst)
            messagebox.showinfo(APP_NAME, f"Guardado:\n{dst}")
        except Exception as ex:
            messagebox.showerror(APP_NAME, f"Error al unir:\n{ex}")


def main():
    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry("1150x780")
    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)
    nb.add(WatermarkTab(nb), text="Marca de agua")
    nb.add(RedactTab(nb), text="Censurar PDF")
    nb.add(SanitizeTab(nb), text="Limpiar metadatos")
    nb.add(MergeTab(nb), text="Unir PDFs")
    root.mainloop()


if __name__ == "__main__":
    main()
