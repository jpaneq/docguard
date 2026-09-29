# DocGuard

Herramienta de escritorio (Windows y macOS), 100 % local y sin conexión, para proteger documentos personales como DNI, nóminas o contratos. Todas las pestañas admiten **arrastrar y soltar** archivos.

| Pestaña | Qué hace |
|---|---|
| **Marca de agua** | Pone un texto en mosaico sobre PDF/PNG/JPG. Se ajustan orientación, tamaño, separación, opacidad y color, con vista previa de cada página. `{fecha}` y `{hora}` se rellenan solos. Los ajustes se pueden guardar como **plantillas**. Exporta a PDF, JPG o PNG, con tamaño en píxeles opcional, y permite **procesar varios archivos a la vez**. |
| **Censurar** | Censura real: el texto y los píxeles de debajo se eliminan del archivo. Se marca de tres formas: arrastrando sobre el texto, buscando una palabra o con **Detectar datos sensibles**. Con **OCR** funciona también en escaneos y fotos. Estilos: cuadro negro, pixelado o difuminado. |
| **Páginas** | Reordenar, girar, eliminar, extraer páginas y dividir el PDF (una por archivo o por rangos como `1-3, 4-6`). |
| **Contraseña** | Protege el PDF con AES-256 y permite limitar imprimir, copiar y modificar. También quita la contraseña si la conoces. |
| **Comprimir y convertir** | Comprime PDFs en tres niveles. Convierte PDF → PNG/JPG (resolución en ppp elegible) e imágenes → PDF. |
| **Limpiar metadatos** | Borra autor, fechas, software, EXIF/GPS, XMP, JavaScript, adjuntos y miniaturas. Admite PDF, imágenes y Office (docx/xlsx/pptx/odt…). |
| **Unir PDFs** | Une varios PDF o imágenes en uno solo, en el orden que elijas. |

## Protección frente a IA
Con la opción "Protección anti-IA", cada repetición de la marca varía un poco en posición, tamaño y opacidad. Además se añaden líneas onduladas entrelazadas y un ruido leve. El resultado se **rasteriza**: el PDF final no tiene una capa de texto ni una anotación que se pueda quitar. Así es mucho más difícil borrar la marca de forma automática. Ninguna marca es 100 % imposible de quitar, pero esta no es un patrón uniforme que una IA pueda restar con facilidad.

## Detección de datos sensibles
Detecta DNI y NIE (comprueba la letra de control), IBAN (comprueba el dígito de control), tarjetas bancarias (algoritmo de Luhn), teléfonos españoles, emails y fechas. Después de marcar, revisa siempre el resultado: ningún detector automático es infalible.

El **cuadro negro** es la opción más segura. El pixelado y el difuminado también borran el texto original, pero la imagen que dejan conserva la forma aproximada de lo que había debajo.

## Ejecutar desde el código
Necesitas Python 3.10 o superior.

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt        # Windows: .venv\Scripts\pip ...
.venv/bin/python docguard.py                     # Windows: .venv\Scripts\python docguard.py
```

`DocGuard --selftest` comprueba la marca de agua, el OCR y la detección sin abrir la ventana.

## Crear el ejecutable
- macOS: `./build_mac.sh` → `dist/DocGuard.app`. Para firmarla con un certificado de Apple Developer: `CODESIGN_IDENTITY="Developer ID Application: …" ./build_mac.sh`. Sin certificado se firma solo para este equipo (firma *ad hoc*).
- Windows: `build_windows.bat` → `dist\DocGuard\DocGuard.exe`

PyInstaller no hace compilación cruzada: el .exe se genera en Windows y la .app en Mac.

### Compilación automática
Si subes este repositorio a GitHub, el workflow `.github/workflows/build.yml` compila la versión de Windows y la de macOS en cada push. Los ejecutables se descargan desde la pestaña *Actions* → *Artifacts*.

## Estructura
- `core.py`: todo el procesamiento (sin interfaz).
- `docguard.py`: la interfaz gráfica (Tkinter).
- `make_icon.py`: genera los iconos.
