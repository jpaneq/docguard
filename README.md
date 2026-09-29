# DocGuard

Una herramienta de escritorio (Windows y macOS) que funciona sin conexión y protege documentos. Tiene 4 pestañas:

| Pestaña | Qué hace |
|---|---|
| **Marca de agua** | Pone un texto en mosaico (p. ej. "Solo para uso de XXX") sobre PDF/PNG/JPG. Puedes ajustar la orientación, el tamaño, la separación, la opacidad y el color, con vista previa en directo. |
| **Censurar PDF** | Arrastras el ratón sobre el texto para marcarlo, o buscas una palabra para marcarla en todo el documento. Aplica una censura *real*: borra el texto y los píxeles que hay debajo. También tiene un modo "Área libre" para escaneos e imágenes. |
| **Limpiar metadatos** | Borra autor, fechas, software, EXIF/GPS, XMP, JavaScript, adjuntos y miniaturas. Admite PDF, imágenes y Office (docx/xlsx/pptx/odt…). |
| **Unir PDFs** | Une varios PDF o imágenes en uno solo, en el orden que elijas. |

## Protección frente a IA
Con la opción "Protección anti-IA", cada repetición de la marca varía un poco en posición, tamaño y opacidad. Además se añaden líneas onduladas entrelazadas y un ruido leve. El resultado se **rasteriza**: el PDF final no tiene una capa de texto ni una anotación que se pueda quitar. Así es mucho más difícil borrar la marca de forma automática. Ninguna marca es 100 % imposible de quitar, pero esta no es un patrón uniforme que una IA pueda restar con facilidad.

## Ejecutar
Necesitas Python 3.10 o superior de https://www.python.org (en Mac, **no** uses el Python del sistema, porque su Tk es demasiado antiguo).

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt        # Windows: .venv\Scripts\pip ...
.venv/bin/python docguard.py                     # Windows: .venv\Scripts\python docguard.py
```

## Crear el ejecutable
- macOS: `./build_mac.sh` → `dist/DocGuard.app`
- Windows: `build_windows.bat` → `dist\DocGuard\DocGuard.exe`

PyInstaller no hace compilación cruzada: el .exe se genera en Windows y la .app en Mac.

### Compilación automática
Si subes este repositorio a GitHub, el workflow `.github/workflows/build.yml` compila la versión de Windows y la de macOS en cada push. Los ejecutables se descargan desde la pestaña *Actions* → *Artifacts*.
