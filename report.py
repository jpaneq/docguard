"""Informe de comprobación de una copia en PDF: reúne a quién se entregó, cómo se ha
identificado, la huella del archivo, sus firmas y los indicios de edición con IA, listo para
adjuntar a una reclamación o denuncia. Si hay internet, el propio informe lleva un sello de
tiempo cualificado que acredita cuándo se hizo la comprobación."""

import datetime
import hashlib
import html
import io

import pymupdf as fitz

CSS = """
* {font-family: sans-serif; font-size: 10.5px; line-height: 1.4; color: #1d2330}
h1 {font-size: 19px; margin: 0 0 2px 0; color: #0d1b2e}
h2 {font-size: 13px; margin: 14px 0 4px 0; color: #0d1b2e; border-bottom: 1px solid #c9d1de}
.muted {color: #5b6475; font-size: 9.5px}
.ok {color: #177a44; font-weight: bold}
.bad {color: #b91c1c; font-weight: bold}
p.kv {margin: 1px 0}
.k {color: #5b6475}
.mono {font-family: monospace; font-size: 9px}
"""


def _e(value):
    return html.escape(str(value if value not in (None, "") else "—"))


def _rows(pairs):
    return "".join(f"<p class='kv'><span class='k'>{_e(k)}:</span> {v}</p>" for k, v in pairs)


def build(check, name, data, image_png=None, now=None):
    """PDF del informe a partir del resultado de «Comprobar una copia»."""
    now = now or datetime.datetime.now()
    parts = [f"<h1>Informe de comprobación de una copia</h1>"
             f"<p class='muted'>Generado con DocGuard el {now:%d/%m/%Y a las %H:%M:%S} (hora de este equipo).</p>"]
    parts.append("<h2>Archivo comprobado</h2>" + _rows([
        ("Nombre", _e(name)), ("Tamaño", f"{len(data):,} bytes".replace(",", ".")),
        ("Huella SHA-256", f"<span class='mono'>{hashlib.sha256(data).hexdigest()}</span>")]))
    found = check.get("found") or []
    if found:
        for x in found:
            rec = x.get("record") or {}
            firma = rec.get("firma") or {}
            methods = "".join(f"<li>{_e(m['name'])}{(' · ' + _e(m['detail'])) if m.get('detail') else ''}</li>"
                              for m in x["methods"])
            parts.append(f"<h2>Resultado: <span class='ok'>copia identificada · referencia {_e(x['ref'])}</span></h2>"
                         f"<p>Métodos independientes que la identifican:</p><ul>{methods}</ul>")
            if rec:
                parts.append(_rows([
                    ("Entregada a", _e(rec.get("destinatario"))), ("Finalidad autorizada", _e(rec.get("finalidad"))),
                    ("Fecha de la entrega", _e(rec.get("fecha"))), ("Texto de la marca", _e(rec.get("texto"))),
                    ("Archivo original", _e(rec.get("archivo"))),
                    ("Válida hasta", _e(rec.get("caduca")) + (" · <span class='bad'>CADUCADA</span>" if x.get("caducada") else ""))
                    if rec.get("caduca") else ("Válida hasta", "sin fecha de caducidad"),
                    ("Firmada digitalmente", _e(firma.get("por")) + (" · con sello de tiempo" if firma.get("sello") else "")
                     if firma else "no")]))
            else:
                parts.append("<p class='muted'>La referencia no está en el historial de este equipo.</p>")
    else:
        parts.append("<h2>Resultado: <span class='bad'>no se ha podido identificar la copia</span></h2>"
                     "<p>Puede que no sea una copia de DocGuard, que se hiciera en otro equipo o que se haya recortado, "
                     "girado o regenerado por completo.</p>")
    delivered = check.get("file") or []
    if delivered:
        x = delivered[0]
        parts.append("<h2>Huella exacta del archivo</h2><p>" + (
            f"<span class='ok'>El archivo es idéntico, byte a byte, a la copia {_e(x['ref'])} que se entregó.</span>"
            if x.get("exact") else
            f"<span class='ok'>El archivo contiene intacta la copia {_e(x['ref'])} que se entregó</span>, con "
            f"{_e(x.get('added'))} bytes añadidos después (por ejemplo, otra firma o el acuse de recibo).") + "</p>")
    sigs = check.get("signatures") or []
    if sigs:
        items = []
        for s in sigs:
            ok = s.get("intact") and s.get("valid")
            ts = s.get("timestamp")
            items.append(f"<li><span class='{'ok' if ok else 'bad'}'>{'✔ íntegra' if ok else '✘ NO válida o alterada'}</span> · "
                         f"{_e(s.get('field'))}: {_e(str(s.get('signer', '')).replace('Common Name: ', ''))} · {_e(s.get('time'))}"
                         + (f" · sello de tiempo {_e(ts.get('time'))} ({_e(ts.get('by'))})" if ts else "") + "</li>")
        parts.append(f"<h2>Firmas digitales del archivo</h2><ul>{''.join(items)}</ul>")
    if check.get("hints"):
        parts.append("<h2>Indicios de edición con IA</h2><ul>" + "".join(f"<li>{_e(t)}</li>" for t in check["hints"]) + "</ul>")
    if image_png:
        parts.append("<h2>Copia comprobada (primera página)</h2><img src='copia.png' width='420'>")
    parts.append("<h2>Cómo se ha comprobado</h2><p class='muted'>"
                 "Marca invisible: referencia oculta en la imagen al protegerla. Rastreo reforzado: marca de baja "
                 "frecuencia, propia de cada entrega, que resiste que una IA redibuje la imagen. Huella de las zonas "
                 "ocultas: cada entrega tapa los datos con medidas únicas. Referencia escrita: la que figura en la "
                 "propia copia. Huella exacta: el SHA-256 del archivo coincide con el de la copia entregada. "
                 "Este informe lo genera el interesado con DocGuard a partir de su historial de entregas; no es un "
                 "peritaje oficial. Si el PDF lleva un sello de tiempo, su fecha y su integridad pueden comprobarse "
                 "en el panel de firmas de Adobe Acrobat Reader o en valide.redsara.es.</p>")
    archive = fitz.Archive()
    if image_png:
        archive.add((image_png, "copia.png"))
    story = fitz.Story(html="".join(parts), user_css=CSS, archive=archive)
    buf = io.BytesIO()
    writer = fitz.DocumentWriter(buf)
    page_rect = fitz.paper_rect("a4")
    more = True
    while more:
        device = writer.begin_page(page_rect)
        more, _ = story.place(page_rect + (48, 48, -48, -48))
        story.draw(device)
        writer.end_page()
    writer.close()
    with fitz.open("pdf", buf.getvalue()) as doc:
        doc.set_metadata({"title": "Informe de comprobación de una copia", "producer": "DocGuard"})
        doc.subset_fonts()
        return doc.tobytes(garbage=3, deflate=True)


def timestamp(pdf, tsa_url):
    """Sello de tiempo del propio documento (no hace falta certificado). Devuelve (pdf, sellado)."""
    try:
        from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
        from pyhanko.sign import signers, timestamps
        w = IncrementalPdfFileWriter(io.BytesIO(pdf))
        out = signers.PdfTimeStamper(timestamps.HTTPTimeStamper(tsa_url, timeout=10)).timestamp_pdf(w, "sha256")
        return out.getvalue(), True
    except Exception as ex:  # sin internet o servidor caído: el informe vale igual, sin sello
        import sys
        print(f"[informe] {ex!r}", file=sys.stderr)
        return pdf, False
