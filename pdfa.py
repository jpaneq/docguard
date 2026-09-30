"""PDF/A-2b (archivo a largo plazo) para los PDF que genera DocGuard: copias protegidas y
documentos digitalizados con el escáner. Añade los metadatos XMP que lo declaran, el perfil de
color sRGB (OutputIntent) y comprueba que las fuentes estén incrustadas y que no haya cifrado.

No se ofrece para cualquier PDF: sin un conversor completo (Ghostscript) no se puede garantizar
que un PDF ajeno cumpla la norma. Tampoco se ha comprobado con un validador (veraPDF)."""

import datetime
import html
import re

import pymupdf as fitz

XMP = """<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:pdf="http://ns.adobe.com/pdf/1.3/">
   <pdfaid:part>2</pdfaid:part>
   <pdfaid:conformance>B</pdfaid:conformance>
   <dc:format>application/pdf</dc:format>
   <dc:title><rdf:Alt><rdf:li xml:lang="x-default">{title}</rdf:li></rdf:Alt></dc:title>
   <xmp:CreatorTool>DocGuard</xmp:CreatorTool>
   <xmp:CreateDate>{date}</xmp:CreateDate>
   <xmp:ModifyDate>{date}</xmp:ModifyDate>
   <xmp:MetadataDate>{date}</xmp:MetadataDate>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""


def _srgb_icc():
    from PIL import ImageCms
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def problems(pdf):
    """Lo que impediría que el PDF sea PDF/A-2b (lista vacía si todo está bien)."""
    out = []
    with fitz.open("pdf", pdf) as doc:
        if doc.needs_pass or doc.is_encrypted:
            return ["tiene contraseña (PDF/A no admite cifrado)"]
        for pno in range(len(doc)):
            for xref, ext, _type, basefont, *_ in doc.get_page_fonts(pno, full=True):
                if ext in ("n/a", ""):
                    out.append(f"la fuente «{basefont}» de la página {pno + 1} no está incrustada")
        cat = doc.pdf_catalog()
        kind, val = doc.xref_get_key(cat, "Metadata")
        if kind == "xref" and doc.xref_get_key(int(val.split()[0]), "Filter")[0] != "null":
            out.append("los metadatos XMP están comprimidos")
        if doc.xref_get_key(cat, "OutputIntents")[0] == "null":
            out.append("falta el perfil de color (OutputIntent)")
        xmp = doc.get_xml_metadata()
        if not re.search(r'pdfaid:part(>|=")\s*2', xmp):
            out.append("faltan los metadatos XMP de PDF/A-2")
        info = doc.metadata or {}
        m = re.search(r'pdf:Producer(?:>|=")([^<"]*)', xmp)
        if (info.get("producer") or "") != (m.group(1) if m else ""):
            out.append("el productor no coincide entre los metadatos Info y XMP")
        if doc.is_encrypted:
            out.append("está cifrado")
    return sorted(set(out))


def convert(pdf, title=""):
    """Convierte un PDF de DocGuard (imágenes y texto con fuentes incrustadas) en PDF/A-2b."""
    now = datetime.datetime.now().astimezone()
    tz = now.strftime("%z")  # +0200
    pdf_date = now.strftime("D:%Y%m%d%H%M%S") + f"{tz[:3]}'{tz[3:]}'"
    xmp_date = now.isoformat(timespec="seconds")
    with fitz.open("pdf", pdf) as doc:
        if doc.needs_pass or doc.is_encrypted:
            raise ValueError("PDF/A no admite contraseña.")
        doc.subset_fonts()
        cat = doc.pdf_catalog()
        # sin «Producer»: si luego se firma, pyHanko lo añade igual en Info y en XMP (coherentes)
        doc.set_metadata({"title": title or "", "creator": "DocGuard", "creationDate": pdf_date, "modDate": pdf_date})
        kind, info = doc.xref_get_key(-1, "Info")
        if kind == "xref":
            doc.xref_set_key(int(info.split()[0]), "Producer", "null")
        doc.set_xml_metadata(XMP.format(title=html.escape(title or ""), date=xmp_date))
        icc = doc.get_new_xref()
        doc.update_object(icc, "<< /N 3 >>")
        doc.update_stream(icc, _srgb_icc())
        intent = doc.get_new_xref()
        doc.update_object(intent, f"<< /Type /OutputIntent /S /GTS_PDFA1 /OutputConditionIdentifier (sRGB IEC61966-2.1) "
                                  f"/Info (sRGB IEC61966-2.1) /DestOutputProfile {icc} 0 R >>")
        doc.xref_set_key(cat, "OutputIntents", f"[{intent} 0 R]")
        # sin comprimir los metadatos XMP (lo exige la norma); el resto ya está comprimido
        out = doc.tobytes(garbage=3, deflate=False)
    left = problems(out)
    if left:
        raise ValueError("No se ha podido generar como PDF/A: " + "; ".join(left))
    return out
