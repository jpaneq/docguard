"""Conversión PDF → Word y documentos (Word, RTF, ODT, HTML, TXT) → PDF."""

import os
import shutil
import subprocess
import sys
import tempfile

import pymupdf as fitz

import core

DOC_EXTS = {".docx", ".doc", ".odt", ".rtf", ".txt", ".html", ".htm", ".md"}


def pdf_to_docx(src, dst):
    """Convierte un PDF en un .docx editable (texto, tablas e imágenes)."""
    from pdf2docx import Converter
    import logging
    logging.getLogger("pdf2docx").setLevel(logging.ERROR)
    cv = Converter(src)
    try:
        cv.convert(dst)
    finally:
        cv.close()


def _html_to_pdf(html, dst, base_dir=None):
    """Maqueta HTML en páginas A4 con PyMuPDF (sin programas externos)."""
    css = ("body{font-family:sans-serif;font-size:11pt;line-height:1.35} h1{font-size:20pt} h2{font-size:16pt}"
           " h3{font-size:13pt} table{border-collapse:collapse} td,th{border:1px solid #999;padding:3px}"
           " img{max-width:100%}")
    archive = fitz.Archive(base_dir) if base_dir else None
    story = fitz.Story(html=html, user_css=css, archive=archive)
    writer = fitz.DocumentWriter(dst)
    mediabox = fitz.paper_rect("a4")
    where = mediabox + (56, 56, -56, -56)
    more = True
    while more:
        dev = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()


def _soffice():
    cands = [shutil.which("soffice"), shutil.which("libreoffice"),
             "/Applications/LibreOffice.app/Contents/MacOS/soffice",
             r"C:\Program Files\LibreOffice\program\soffice.exe"]
    return next((c for c in cands if c and os.path.exists(c)), None)


def document_to_pdf(src, dst):
    """Word/ODT/RTF/HTML/TXT → PDF. Usa LibreOffice si está instalado (máxima fidelidad);
    si no, convierte a HTML (mammoth para .docx, textutil en macOS para el resto) y maqueta."""
    ext = core.ext_of(src)
    office = _soffice()
    if office and ext not in (".txt", ".md"):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([office, "--headless", "--convert-to", "pdf", "--outdir", tmp, src],
                           check=True, capture_output=True, timeout=180)
            out = os.path.join(tmp, os.path.splitext(os.path.basename(src))[0] + ".pdf")
            shutil.move(out, dst)
            return "LibreOffice"
    import html as html_mod
    if ext == ".docx":
        import mammoth
        with open(src, "rb") as f:
            html = mammoth.convert_to_html(f).value
        _html_to_pdf(html, dst)
        return "conversión integrada"
    if ext in (".html", ".htm"):
        with open(src, encoding="utf-8", errors="replace") as f:
            _html_to_pdf(f.read(), dst, os.path.dirname(src))
        return "conversión integrada"
    if ext in (".txt", ".md"):
        with open(src, encoding="utf-8", errors="replace") as f:
            text = f.read()
        _html_to_pdf("<pre style='white-space:pre-wrap;font-family:monospace;font-size:10pt'>"
                     + html_mod.escape(text) + "</pre>", dst)
        return "conversión integrada"
    if sys.platform == "darwin" and shutil.which("textutil"):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "doc.html")
            subprocess.run(["textutil", "-convert", "html", "-output", out, src], check=True, capture_output=True)
            with open(out, encoding="utf-8", errors="replace") as f:
                _html_to_pdf(f.read(), dst, tmp)
        return "conversión integrada (macOS)"
    raise ValueError(f"Para convertir archivos {ext} instala LibreOffice (gratuito) o guárdalo como .docx.")
