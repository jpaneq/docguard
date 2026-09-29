# DocGuard

Una aplicación de escritorio (Windows y macOS) para proteger, editar y firmar documentos. Funciona **100 % en local**: ningún archivo sale del equipo. La interfaz es web y se abre en una ventana nativa. Todas las pantallas admiten arrastrar y soltar archivos.

## Funciones

| Herramienta | Qué hace |
|---|---|
| **Editar PDF** | **Escritura directa sobre la página:** doble clic en un texto para escribir en él con su misma fuente; clic y arrastrar para moverlo; selección múltiple con recuadro; Supr para borrar; flechas para desplazar. Para añadir texto, clic en la página y escribir.<br>**Formas** (rectángulo, elipse, línea, flecha) que se pueden mover y redimensionar.<br>**Seleccionar, copiar y pegar** zonas del documento con su calidad original, también imágenes o texto desde otras aplicaciones.<br>**OCR:** convierte un escaneo en texto editable o seleccionable.<br>**Firma al margen** de todas las páginas de una vez.<br>**Texto:** cambia el texto que ya existe detectando su fuente, tamaño y color. Usa la fuente incrustada o la misma familia instalada en el sistema; si no está, una equivalente. También puedes añadir texto nuevo con la fuente que elijas.<br>**Imágenes:** insertar, mover, redimensionar y eliminar.<br>**Anotaciones:** resaltar, subrayar, tachar, notas, cuadros de texto, rectángulos, elipses y dibujo a mano.<br>**Formularios:** crear campos (texto, casilla, desplegable, lista, botón de opción), rellenarlos, editarlos y aplanarlos.<br>**Firma manuscrita:** dibujada o subida como imagen.<br>Deshacer ilimitado. |
| **Marca de agua** | Texto en mosaico con tres niveles de protección (básica, reforzada y máxima). Añade microtexto sobre los datos, un código QR con el uso autorizado y una marca invisible de rastreo; con «Comprobar un documento» e «Historial de entregas» sabes a quién se entregó cada copia. Se ajustan orientación, tamaño, separación, opacidad y color, con vista previa de cada página. Admite plantillas, `{fecha}`/`{hora}`, procesar varios archivos a la vez y exportar a PDF/JPG/PNG con tamaño en píxeles. |
| **Censurar** | Cada recuadro, también los detectados automáticamente, se puede seleccionar y quitar (✕ o Supr). Incluye los datos de DNI y pasaporte que no suele hacer falta compartir. Censura real (el contenido se elimina del archivo). Se marca seleccionando texto, dibujando áreas, buscando palabras o con **detección automática** de DNI/NIE, IBAN, tarjetas, teléfonos, emails y fechas. Con **OCR** funciona en escaneos. Estilos: negro, pixelado o difuminado. |
| **Firma digital** | Firma con validez legal (PAdES) de dos formas:<br>• **Certificado en archivo** `.p12/.pfx` (FNMT u otro).<br>• **DNIe o tarjeta criptográfica** por PKCS#11. Un indicador verde muestra que el DNIe está conectado y el PIN verificado.<br>Admite firma visible con imagen manuscrita, motivo, lugar, sello de tiempo y verificación de las firmas de un PDF. |
| **Páginas** | Miniaturas que se reordenan arrastrando. Permite girar, eliminar, extraer y dividir (una página por archivo o por rangos). |
| **Contraseña** | Cifrado AES-256 con permisos de imprimir, copiar y modificar. También quita la contraseña si la conoces. |
| **Comprimir y convertir** | Compresión en tres niveles. Conversión PDF → PNG/JPG e imágenes → PDF. |
| **Limpiar metadatos** | PDF, imágenes y documentos Office. |
| **Unir PDFs** | PDFs e imágenes en un solo PDF. |

El **documento actual** (arriba en la barra lateral) se mantiene al cambiar de herramienta, con las ediciones incluidas. Cuando terminas una operación, «Seguir con este archivo…» abre el resultado en otra herramienta. Por ejemplo: editar → censurar → firmar.

## DNIe y certificado FNMT
- **FNMT (archivo):** exporta tu certificado como `.pfx`/`.p12` con su contraseña. En la app tienes la guía para Windows, Mac y Firefox.
- **DNIe:** necesitas un lector de tarjetas y el módulo PKCS#11 oficial ([dnielectronico.es](https://www.dnielectronico.es), área de descargas) u [OpenSC](https://github.com/OpenSC/OpenSC/releases). DocGuard busca el módulo automáticamente en las rutas habituales. Si está en otra ruta, se puede indicar a mano o con la variable de entorno `DOCGUARD_PKCS11`.
- El PIN solo se usa en el momento de firmar y no se guarda. El DNIe se bloquea tras 3 PIN erróneos.

## Protección frente a IA
Ninguna marca visible es imposible de quitar para una IA generativa. DocGuard combina capas para que quitarla sea costoso, deje huella y que el origen se pueda demostrar igualmente:
1. **Marca principal difícil de aislar:** cada letra con giro, tamaño, altura y tono aleatorios, una trama de líneas finas por todo el documento y, en nivel máximo, una segunda capa cruzada.
2. **Microtexto sobre los datos:** el OCR localiza cada línea (nombre, número, fechas…) y la atraviesa con microtexto del color de la tinta. Para eliminarlo hay que reescribir los datos, y una IA tiende a alterarlos al hacerlo, con lo que la copia queda falseada.
3. **Código QR:** muestra a quién se autoriza, la finalidad, la fecha y la referencia.
4. **Marca invisible de rastreo:** una referencia oculta en la imagen que resiste compresión JPEG y cambios de tamaño (probado hasta el 30 %). Aunque se borren la marca visible y el QR, «Comprobar un documento» identifica la copia en el historial local. No resiste recortes fuertes ni que la imagen se regenere por completo.

## Ejecutar desde el código
Necesitas Python 3.10–3.12. Se recomienda instalarlo con [uv](https://docs.astral.sh/uv/) o desde python.org.

```
uv venv --python 3.12 .venv
uv pip install --python .venv -r requirements.txt
.venv/bin/python app.py              # ventana nativa
.venv/bin/python app.py --browser    # en el navegador
.venv/bin/python app.py --selftest   # comprobación automática
```

## Crear el ejecutable
- macOS: `./build_mac.sh` → `dist/DocGuard.app`. Al terminar ejecuta el autotest. Para firmar la app con un certificado de Apple Developer: `CODESIGN_IDENTITY="Developer ID Application: …" ./build_mac.sh`.
- Windows: `build_windows.bat` → `dist\DocGuard\DocGuard.exe`.
- GitHub Actions (`.github/workflows/build.yml`) compila las dos versiones y pasa el autotest en cada push.

## Estructura
- `app.py`: arranque (ventana nativa o navegador) y autotest.
- `server.py`: API local; solo escucha en `127.0.0.1` y exige un token aleatorio.
- `core.py`: marca de agua, censura, OCR, detección, páginas, compresión, cifrado y metadatos.
- `editor.py`: edición de PDF (texto con fuentes, imágenes, anotaciones y formularios).
- `signing.py`: firma digital con archivo `.p12` o PKCS#11 (DNIe) y verificación.
- `web/`: interfaz (HTML/CSS/JS sin dependencias externas).

## Versiones
- `v0`: interfaz de escritorio con Tkinter.
- `v1`: interfaz web con edición de PDF, firma digital y DNIe.
