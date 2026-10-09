# DocGuard

Una aplicación de escritorio (Windows y macOS) para proteger, editar y firmar documentos. Funciona **100 % en local**: ningún archivo sale del equipo. La interfaz es web y se abre en una ventana nativa. Todas las pantallas admiten arrastrar y soltar archivos.

## Funciones

| Herramienta | Qué hace |
|---|---|
| **Editar PDF** | **Buscar** texto (⌘F) con navegación entre resultados. Barra de iconos al estilo Acrobat/Word, barra de formato contextual, desplazamiento continuo con **miniaturas e índice**, menú contextual (clic derecho), ⌘C/⌘X/⌘V, deshacer y rehacer. Con la herramienta **Seleccionar** se hace casi todo: seleccionar y mover textos, imágenes (también firmas escaneadas), formas y campos, o seleccionar una zona para copiarla (las zonas sin texto se copian como captura). Los textos seleccionados se **agrandan o reducen arrastrando la esquina de su marco** (letra e interlineado, sin cambiar la fuente).<br>**Listas** con viñetas, numeradas o con letras, y sub-listas (Tab / Mayús+Tab).<br>**Escritura directa sobre la página:** doble clic en un texto para escribir en él con su misma fuente (Intro crea una línea nueva debajo con el interlineado del documento y el texto de debajo baja); clic y arrastrar para moverlo; selección múltiple con recuadro; Supr para borrar; flechas para desplazar. Para añadir texto, clic en la página y escribir.<br>**Formas** (rectángulo, elipse, línea, flecha) que se pueden mover y redimensionar: ocho tiradores en rectángulos y elipses, y un tirador en cada extremo de las líneas y flechas. Con **Mayús**: líneas en ángulos de 15° (0°, 45°, 90°…) al dibujar o mover un extremo, cuadrados y círculos perfectos, proporción fija en las esquinas y movimiento en línea recta. Al seleccionar una forma se cambian sus **propiedades**: color del contorno, grosor, tipo de línea (continua, discontinua, punteada, rayas largas), relleno, opacidad y flechas de las líneas.<br>**Copiar y pegar** también campos de formulario (con otro nombre, su valor y su aspecto) y formas, como objetos editables, incluso en otra página.<br>**Seleccionar, copiar y pegar** zonas del documento con su calidad original, también imágenes o texto desde otras aplicaciones.<br>**OCR:** convierte un escaneo en texto editable o seleccionable.<br>**Firma al margen** de todas las páginas de una vez.<br>**Texto:** cambia el texto que ya existe detectando su fuente, tamaño y color. Usa la fuente incrustada o la misma familia instalada en el sistema; si no está, una equivalente. También puedes añadir texto nuevo con la fuente que elijas.<br>**Imágenes:** insertar, mover, redimensionar y eliminar.<br>**Anotaciones:** resaltar con **fosforito** (trazo de rotulador flúor en amarillo, verde, rosa, naranja, azul o lila), subrayar y tachar **seleccionando el texto con el ratón** como en cualquier lector (también varias líneas; en páginas escaneadas sin texto, con un recuadro), notas, cuadros de texto, rectángulos, elipses y dibujo a mano.<br>**Formularios:** crear campos (texto, casilla, desplegable, lista, botón de opción), rellenarlos, editarlos y aplanarlos.<br>**Firma manuscrita:** dibujada o subida como imagen.<br>Deshacer ilimitado. |
| **Escáner** | Convierte **fotos de documentos hechas con el móvil** (DNI, pasaporte, folios) o PDFs escaneados en escaneos limpios: detecta los bordes (con esquinas ajustables a mano), endereza la perspectiva con la proporción exacta (tarjeta ID-1, pasaporte, A4, Carta), quita sombras e iluminación desigual y deja el papel blanco (color, color natural, grises o blanco y negro). **Digitaliza** a PDF a tamaño real con **texto reconocido (OCR)**, opcionalmente en **PDF/A**, o pone **anverso y reverso del DNI en una hoja A4**. Al mover las esquinas, una **lupa** muestra el punto exacto y las flechas del teclado afinan la posición. **Desde el móvil:** un QR abre en el móvil una página para hacer la foto, que llega sola por tu wifi (ver «Escanear con el móvil»). Desde Marca de agua: «¿Es una foto? Pasarla antes a modo escáner». |
| **Visor PDF** | Abre muchos PDFs a la vez, cada uno con su tira de miniaturas. **⌘F busca en todos** a la vez (contador por documento y página, fragmentos con la palabra resaltada, opción de ver solo las páginas con resultados). Al pinchar en una página se abre ese PDF **por encima** para leerlo, con las coincidencias marcadas y ▲▼ para recorrerlas. |
| **Marca de agua** | **Modo rápido DNI/pasaporte:** indicando para quién es y la finalidad, en un paso oculta los datos innecesarios, añade marca reforzada, microtexto, QR y rastreo, y guarda un PDF (con contraseña si quieres). Opcionalmente **firma digitalmente la copia** (ver «Firmar la copia»), le pone **fecha de caducidad** («Válida hasta»), deja la **foto del titular pixelada, difuminada o tapada**, la guarda en **PDF/A** y prepara el **texto para el correo** o para **proponer MiDNI**. «Comprobar una copia» genera un **informe en PDF** con sello de tiempo, y el **historial de entregas** se puede exportar, importar y copiar automáticamente en una carpeta (iCloud Drive, Google Drive, un USB…).  Texto en mosaico con tres niveles de protección (básica, reforzada y máxima). Añade microtexto sobre los datos, un código QR con el uso autorizado y una marca invisible de rastreo; con «Comprobar un documento» e «Historial de entregas» sabes a quién se entregó cada copia. Se ajustan orientación, tamaño, separación, opacidad y color, con vista previa de cada página. Admite plantillas, `{fecha}`/`{hora}`, procesar varios archivos a la vez y exportar a PDF/JPG/PNG con tamaño en píxeles. |
| **Censurar** | Las zonas marcadas **se guardan solas** y se recuperan al volver a abrir el mismo documento. **Vista previa** antes de guardar (se ve el documento ya censurado, en la misma página, y se puede volver a editar). Desplazamiento continuo con la rueda. Cada recuadro, también los detectados automáticamente, se puede seleccionar y quitar (✕ o Supr). Incluye los datos de DNI y pasaporte que no suele hacer falta compartir. Censura real (el contenido se elimina del archivo). Se marca seleccionando texto, dibujando áreas, buscando palabras o con **detección automática** de DNI/NIE, IBAN, tarjetas, teléfonos, emails y fechas. Con **OCR** funciona en escaneos. Estilos: negro, pixelado o difuminado. |
| **Firma digital** | Firma con validez legal (PAdES) de dos formas:<br>• **Certificado en archivo** `.p12/.pfx` (FNMT u otro).<br>• **DNIe o tarjeta criptográfica** por PKCS#11. Un indicador verde muestra que el DNIe está conectado y el PIN verificado.<br>Admite firma visible (con la manuscrita si quieres), motivo, lugar, **sello de tiempo cualificado** de la ACCV, **validación a largo plazo** y verificación de las firmas de un PDF.<br>**Probar mi firma:** firma un PDF de prueba (sin valor) y explica si tu firma funciona, su tipo (cualificada con DNIe; avanzada con certificado cualificado de la FNMT), el sello de tiempo y la validación.<br>**Firmar varios PDF a la vez** con el PIN o la contraseña una sola vez.<br>**Seguimiento de lo enviado a firmar:** al volver un documento, dice si lo que enviaste sigue intacto, quién ha firmado y quién falta.<br>**Dónde va la firma:** dentro de la página (arrastrando el recuadro o en un recuadro preparado, como siempre) o, si lo marcas, **en un margen añadido abajo**, pequeña y sin tapar nada (solo si el documento aún no tiene firmas; los recuadros preparados para otros firmantes se conservan).<br>**Recuadros para varios firmantes:** se preparan de antemano (uno por persona) y cada firmante firma en el suyo; la app indica quién falta.<br>**Varios firmantes:** «Firmar y pasar al siguiente firmante» deja el documento firmado abierto para que firme otra persona (su certificado o su DNIe) sin invalidar la firma anterior. «Firmar y enviar por correo» guarda el PDF y lo adjunta a un correo nuevo (Mail u Outlook). |
| **Páginas** | **Numerar páginas** y añadir encabezado y pie ({n}, {total}, {fecha}, {archivo}; con opción de saltar la portada). Miniaturas que se reordenan arrastrando. Permite girar, eliminar, extraer y dividir (una página por archivo o por rangos). |
| **Contraseña** | Cifrado AES-256 con permisos de imprimir, copiar y modificar. También quita la contraseña si la conoces. |
| **Comprimir y convertir** | Compresión en tres niveles. Conversión PDF → PNG/JPG e imágenes → PDF. |
| **Limpiar metadatos** | PDF, imágenes y documentos Office. |
| **Comparar versiones** | Dos PDFs lado a lado que se desplazan juntos, con lo quitado en rojo y lo añadido en verde, y una lista de cambios en la que cada uno salta a su sitio. |
| **Unir PDFs** | PDFs e imágenes en un solo PDF. Dos vistas: **lista de archivos** o **páginas** en cuadrícula (un color por documento), donde se reordenan, giran y quitan páginas sueltas y se inserta otro documento en cualquier punto con «+» o arrastrándolo. |

El **documento actual** (arriba en la barra lateral) se mantiene al cambiar de herramienta, con las ediciones incluidas. Cuando terminas una operación, «Seguir con este archivo…» abre el resultado en otra herramienta. Por ejemplo: editar → censurar → firmar.

## DNIe y certificado FNMT
- **FNMT (archivo):** exporta tu certificado como `.pfx`/`.p12` con su contraseña. En la app tienes la guía para Windows, Mac y Firefox.
- **DNIe:** necesitas un lector de tarjetas y el módulo PKCS#11 oficial ([dnielectronico.es](https://www.dnielectronico.es), área de descargas) u [OpenSC](https://github.com/OpenSC/OpenSC/releases). DocGuard busca el módulo automáticamente en las rutas habituales. Si está en otra ruta, se puede indicar a mano o con la variable de entorno `DOCGUARD_PKCS11`.
- El PIN solo se usa en el momento de firmar y no se guarda. El DNIe se bloquea tras 3 PIN erróneos.

## DNI y pasaporte: qué datos se ocultan
En «Marca de agua» → «Ocultar datos», DocGuard propone tapar automáticamente (OCR + etiquetas + patrones):
- **DNI, anverso:** firma, número de soporte (IDESP) y CAN.
- **DNI, reverso:** zona MRZ, equipo de expedición, progenitores, domicilio y lugar de nacimiento.
- **Pasaporte:** firma, MRZ, número personal, lugar de nacimiento y autoridad de expedición.

Los recuadros se revisan sobre la vista previa: clic y ✕ para quitar uno, o arrastrar para tapar otra zona. Son propuestas: revisa siempre el resultado.

## Código QR
Si la copia tiene fecha de caducidad, el QR la incluye y la página de verificación la muestra como **caducada** pasada esa fecha. Al escanearlo puede mostrar:
- una **ficha** (tarjeta de contacto que el móvil enseña sin internet);
- una **página web de verificación**. Hay que publicar `docs/verificar.html`, por ejemplo con `publicar_github.sh`; los datos van dentro del enlace, tras `#`, y el servidor nunca los recibe;
- **texto plano**.

## Firmar la copia
En el modo rápido, **«Firmar digitalmente la copia»** la firma con tu certificado de la FNMT (`.p12/.pfx`) o con tu DNIe. El PIN o la contraseña se piden al guardar y no se guardan; con el DNIe se usa una sola vez aunque haya varios archivos.

- **Dónde va la firma** (a elegir):
  - **debajo, en una franja añadida**, fuera de la imagen del documento, con el uso autorizado («Copia de uso restringido · Solo para… · Finalidad… · Ref.») y la firma pequeña;
  - **dentro del documento**, donde la coloques arrastrando en la vista previa (por defecto, abajo a la derecha);
  - **invisible**: va en el PDF, pero sin recuadro.
- **Qué prueba:** que la copia es tuya y exactamente cómo la entregaste (a quién, para qué, cuándo y con qué referencia). Cualquier cambio invalida la firma en Adobe Acrobat Reader, Autofirma o VALIDe. No impide una captura de pantalla ni que una IA redibuje la imagen: es una prueba, no un candado.
- **Valor legal:** con el DNIe es firma cualificada; con el certificado de la FNMT, firma avanzada basada en certificado cualificado.
- **Sello de tiempo** cualificado de la ACCV (gratuito para uso personal; solo se envía la huella del documento) y **validación a largo plazo** (se incluyen en el PDF los datos de revocación del certificado). Necesitan internet: si fallan, se firma igualmente y se avisa. La validación a largo plazo se ha probado con certificados de prueba y un DNIe simulado, no con un certificado real de la FNMT ni con un DNIe real.
- **Acuse de recibo** (opcional, con la franja): un recuadro para que el destinatario firme que recibe la copia solo para esa finalidad.
- **Compatible con otras firmas:** es una firma normal (no de certificación), así que después pueden firmar otras personas, en el acuse o en sus propios recuadros, sin invalidarla. Con contraseña, solo en recuadros que ya existan.
- **Historial y comprobación:** el historial guarda la huella exacta (SHA-256) de cada archivo entregado. «Comprobar una copia» dice si un archivo es idéntico al entregado, o si es el entregado con firmas añadidas después (por ejemplo, el acuse). También valida sus firmas y pide la contraseña si la copia la tiene.

## MiDNI: no enviar copia del DNI
Desde el 2 de abril de 2026, el Real Decreto 255/2025 obliga a administraciones y empresas a aceptar la app oficial **MiDNI** para identificarse **en persona**. No permite acreditar la identidad a distancia por internet. En el modo rápido, «¿Es en persona? Propón MiDNI…» abre dos textos editables:
- uno para **proponer MiDNI** en lugar de enviar una copia (cita el principio de minimización de datos del RGPD y deja abierta la vía de una copia protegida si hay obligación legal);
- otro con las **condiciones que acompañan a la copia** (finalidad, no cederla, borrarla cuando no haga falta, firma, referencia y acuse).

Se pueden copiar o abrir en el correo. DocGuard no envía nada por su cuenta.

## Historial de entregas e informe
- El historial (a quién se entregó cada copia, sus huellas y su firma) es la prueba de cada entrega. Se guarda de forma segura: un corte a mitad de escritura no lo estropea.
- **Copia automática:** eliges una carpeta (iCloud Drive, Google Drive, un USB…) y se copia allí cada vez que cambia, con una copia por día de los últimos 30 días. También se puede **exportar**, **importar** (une lo que falte sin perder nada) y borrar entradas. Incluye los documentos enviados a firmar.
- **Informe en PDF** desde «Comprobar una copia»: a quién se entregó, con qué métodos se ha identificado, huella del archivo, firmas, caducidad, indicios de IA e imagen de la copia. Si hay internet, el informe lleva un **sello de tiempo cualificado** que acredita cuándo se hizo la comprobación. No es un peritaje oficial.

## Foto del titular
En «Ocultar datos», la foto se puede dejar **pixelada** (bloques muy gruesos), **difuminada fuerte** (con ruido, para que no se pueda deshacer) o **tapada**. Se hace sobre la copia; el original no cambia. Es para envíos en los que no hace falta verte la cara. Si no encuentra la foto, se tapa arrastrando un recuadro en la vista previa.

## PDF/A
Las copias protegidas (sin contraseña, que PDF/A no admite) y los documentos del escáner se pueden guardar como **PDF/A-2b**, el formato de archivo a largo plazo que piden algunas sedes electrónicas. Incluye los metadatos XMP, el perfil de color sRGB y las fuentes incrustadas, y sigue siéndolo al firmar después. Solo se ofrece para los PDF que genera DocGuard y **no se ha comprobado con un validador (veraPDF)**.

## Escanear con el móvil
En el Escáner, «📱 Desde el móvil…» muestra un QR. En el móvil (en la misma wifi) se abre una página para hacer la foto, que llega sola al Escáner para enderezarla.
- Usa un **servidor aparte y temporal**, solo en la dirección de la red local. El enlace lleva una clave aleatoria y deja de funcionar al cerrar la ventana o a los 10 minutos.
- Solo admite fotos JPG o PNG (hasta 25 MB y 40 por sesión) y **nunca expone la aplicación**.
- La foto no pasa por internet, pero **viaja sin cifrar por la wifi**: úsalo solo en tu wifi de casa. La primera vez, el ordenador puede preguntar si permites conexiones entrantes.

## Protección frente a IA
**Lo importante, medido y sin exagerar:** ninguna marca visible impide que una IA generativa (ChatGPT, Gemini…) redibuje un DNI limpio si los datos se pueden leer. Por eso DocGuard combina tres objetivos:
1. **Que quitar la marca estropee los datos.** Es el caso de los eliminadores «de relleno» (LaMa, usado por muchas webs de quitar marcas).
2. **Que, aunque la IA deje la copia limpia, se pueda demostrar a quién se entregó.**
3. **Disuadir y reducir lo que se comparte.**

Capas (en «Marca de agua»; el **modo rápido DNI/pasaporte** las activa todas):
- **Marca principal** con variaciones por letra, trama de seguridad y **microtexto sobre los datos**.
- **Rastreo reforzado:** marca invisible de baja frecuencia, propia de cada entrega, que **resiste la regeneración por IA**.
- **Huella en las zonas ocultas:** cada entrega tapa los datos con medidas únicas (sin descubrir nunca un dato); las IA conservan esos recuadros al redibujar.
- **Rótulos «OCULTO · SOLO PARA… · REF»** dentro de las zonas ocultas y **MRZ señuelo**: una MRZ falsa con aspecto real que dice para quién es la copia.
- **Sello sobre la foto**, como los oficiales: para quitarlo hay que redibujar parte de la cara.
- **Aviso contra la edición**, también dirigido a los asistentes de IA.
- **Resolución máxima** (1600 px en el modo rápido): legible, pero menos útil para falsificar.
- **QR en posición automática**, sin tapar datos.

**«Comprobar una copia»** identifica a quién se entregó con varios métodos independientes: marca invisible, rastreo reforzado, huella de las zonas ocultas, referencia escrita y, si el archivo no se ha tocado, su huella exacta. Además avisa si el archivo lleva metadatos de edición con IA (C2PA, IPTC).

### Resultados del banco de pruebas (`tools/benchmark_ia.py`)
DNI ficticio, protección de la v1.8 (modo rápido). «Identificada» significa que DocGuard sigue sabiendo a quién se entregó la copia:

| Ataque | Marca visible | Datos tras el ataque | ¿Identificada? |
|---|---|---|---|
| Redes sociales (reducción + JPEG) | intacta | legibles | sí (varios métodos) |
| LaMa con la máscara perfecta de la marca | quitada en gran parte | **destrozados** (p. ej. «DNI 90099909R», «LUOIA») | sí (3 métodos) |
| Regeneración de la imagen (VAE de Stable Diffusion) | se conserva | legibles | sí (rastreo reforzado; a menudo también la huella) |
| LaMa + regeneración | quitada en gran parte | destrozados | sí (rastreo reforzado) |

Antes (v1.7) la regeneración borraba el rastreo por completo. No se ha podido probar contra ChatGPT o Gemini directamente: su regeneración es más agresiva que la del banco, así que la identificación tras pasar por ellos no está garantizada.

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

## Estructura (modular)
Cada módulo se puede trabajar por separado. El servidor expone cada función como una operación de la API y la interfaz tiene un archivo por herramienta.

**Servidor (Python)**
| Módulo | Contenido |
|---|---|
| `app.py` | Arranque (ventana nativa o navegador), puente con el sistema (guardar, correo) y autotest (`--selftest`). |
| `server.py` | API local: documentos abiertos, deshacer/rehacer, resultados. Solo `127.0.0.1`, con token. |
| `core.py` | Marca de agua básica, OCR, detección de datos sensibles, censura, páginas, compresión, cifrado y metadatos. |
| `editor.py` | Edición de PDF: texto con su fuente, mover/copiar/pegar, imágenes, formas, anotaciones, formularios, OCR a texto, firma al margen. |
| `protect.py` | Protección reforzada: microtexto, trama, QR (ficha/web/texto), marca invisible y registro de entregas. |
| `idfields.py` | Datos de DNI y pasaporte que conviene ocultar (MRZ, CAN, soporte, firma, domicilio…). |
| `scan.py` | Modo escáner: detección del documento, perspectiva, mejora de imagen y digitalización. |
| `compare.py` | Comparación de versiones (diferencias de texto con posición). |
| `convert.py` | PDF → Word y documentos → PDF. |
| `tools/benchmark_ia.py` | Banco de pruebas contra eliminadores de marcas con IA (no forma parte de la app). |
| `signing.py` | Firma digital PAdES con `.p12/.pfx` o DNIe/tarjeta (PKCS#11, cada tarjeta por su número de serie), aspecto de la firma, sello de tiempo y validación a largo plazo con alternativa si fallan, copias firmadas (franja, dentro o invisible, acuse), margen añadido, firma de prueba y verificación. |
| `records.py` | Historiales (entregas y envíos a firmar): guardado seguro, copia automática en una carpeta, exportar, importar y borrar. |
| `tracking.py` | Seguimiento de los documentos enviados a firmar (qué sigue intacto, quién ha firmado, quién falta). |
| `report.py` | Informe de comprobación en PDF con sello de tiempo del propio informe. |
| `pdfa.py` | PDF/A-2b para los PDF de DocGuard (XMP, perfil sRGB, comprobaciones). |
| `mobile.py` | Escanear con el móvil: servidor temporal en la red local que solo recibe fotos. |
(el servidor también ofrece `fs/list`, `fs/open`, `fs/pin` y `recent` para el explorador de archivos: listar carpetas, abrir por ruta, carpetas fijadas y archivos recientes.)

**Interfaz (`web/`)**
| Archivo | Contenido |
|---|---|
| `js/core/util.js` | API, avisos, ventanas, archivos, resultados y documento actual compartido. |
| `js/core/viewer.js` | Visor de páginas (una a una o continuo) y fuentes para la edición directa. |
| `js/core/filelist.js`, `js/core/sigs.js` | Listas de archivos y firmas manuscritas guardadas. |
| `js/tools/*.js` | Una herramienta por archivo: `edit`, `watermark`, `redact`, `sign`, `pages`, `merge`, `compare`, `library` (visor PDF), `scanner`, `share` (textos de MiDNI y de la copia), `misc` (contraseña, convertir, limpiar). |
| `js/core/shell.js` | Estructura de la aplicación: barra superior (Inicio, Herramientas y pestañas de documentos), vistas de Inicio y Herramientas, panel de herramientas ocultable y tema claro/oscuro. |
| `js/core/files.js` | Explorador de archivos del lateral: carpetas, unidades, carpetas fijadas y apertura de PDFs e imágenes. |
| `js/main.js` | Registro de herramientas y navegación. |
| `verificar.html` | Página de verificación del QR (también en `docs/` para publicarla). |

## Versiones
- `v0`: interfaz de escritorio con Tkinter.
- `v1`: interfaz web con edición de PDF, firma digital y DNIe.
- `v1.1`: protección reforzada, QR y marca invisible; documento compartido entre herramientas.
- `v1.2`: edición directa, formas, copiar/pegar, OCR en Editar, firma al margen, ocultar datos de DNI/pasaporte.
- `v1.3`: Editar estilo Acrobat/Word (barra de iconos, formato contextual, selección unificada, menú contextual, ⌘C/⌘X/⌘V, rehacer), listas, visor continuo con miniaturas e índice, varios firmantes y firmar y enviar, interfaz dividida en módulos.
- `v1.4`: edición multilínea (Intro = nueva línea y el texto de debajo baja) y Unir PDFs con vista de páginas.
- `v1.5`: vista previa de la censura, desplazamiento continuo en Censurar y Firma (y por rueda en la vista previa de Marca de agua), paneles laterales redimensionables.
- `v1.6`: zonas de censura guardadas, comparar versiones, numeración y encabezados, recuadros para varios firmantes, buscar en Editar, modo rápido DNI/pasaporte con contraseña, conversión Word ↔ PDF y script de publicación en GitHub (versión de Windows).
- `v1.7`: resaltado tipo rotulador fosforito con colores flúor y Visor PDF con búsqueda en varios documentos.
- `v1.8`: capas contra la IA generativa (rastreo reforzado, huella en zonas ocultas, rótulos y MRZ señuelo, sello sobre la foto, aviso, resolución máxima, QR automático), «Comprobar una copia» con cuatro métodos e indicios de IA, y banco de pruebas `tools/benchmark_ia.py`.
- `v1.9`: modo Escáner (detección de bordes, perspectiva, limpieza de sombras, digitalización con OCR y DNI a doble cara en A4).
- `v1.10`: firmar la copia en el modo rápido (franja debajo, dentro del documento o invisible; sello de tiempo cualificado, validación a largo plazo y acuse de recibo), margen añadido para firmar en Firma digital, huella exacta del archivo y validación de firmas en «Comprobar una copia» (también con contraseña), y textos para proponer MiDNI o acompañar la copia.
- `v1.11`: firma moderna con sello de tiempo cualificado y validación a largo plazo en Firma digital, «Probar mi firma», firma por lotes, seguimiento de lo enviado a firmar, dos DNIe a la vez, copia automática, exportación e importación del historial, informe de comprobación en PDF, caducidad de la copia, foto pixelada, difuminada o tapada, PDF/A-2b y escanear con el móvil.
- `v1.12`: cambiar el tamaño de los textos en Editar arrastrando la esquina del marco, y lupa y ajuste con flechas en las esquinas del Escáner.
- `v1.13`: formas con Mayús (ángulos de 15°, cuadrados y círculos), ocho tiradores para redimensionar, extremos de líneas y flechas arrastrables, y las formas ya no crecen al moverlas.
- `v1.14`: resaltar, subrayar y tachar seleccionando el texto con el ratón (recuadro solo en páginas sin texto), propiedades editables de las formas (color, relleno, grosor, tipo de línea, opacidad, flechas) y copiar/pegar campos de formulario y formas como objetos.
- `v1.16`: pestañas de documentos en Editar, Censurar y Firma digital (varios PDF abiertos a la vez, con sus cambios), abrir varios archivos de golpe, «Nueva ventana» (⌘N / Ctrl+N) con documentos y portapapeles compartidos, y organizar las ventanas en mosaico o en cascada (menú Ventana y botones laterales). Incluye las mejoras del visor y las rectas de la versión de Windows.
- `v1.17`: icono rojo con «PDF», versión visible en el título de la ventana y en la barra lateral, barra lateral ocultable, imprimir (⌘P/Ctrl+P), se abre en el Visor PDF, flechas ← → para pasar de página; actualizaciones automáticas (al abrirse, DocGuard consulta las versiones publicadas en GitHub, ofrece instalarlas, comprueba su huella SHA-256 y guarda la anterior), «Buscar actualizaciones», zoom con ⌘ + rueda, y compilación en GitHub solo al publicar una versión.
- `v1.20`: interfaz renovada al estilo de Acrobat: barra superior con Inicio, Herramientas y pestañas de los documentos abiertos; vista de Herramientas en cuadrícula por categorías con buscador; panel de herramientas a la derecha (ocultable); tema claro, oscuro o automático; iconos propios de trazo fino; menú «⋯» con ventanas, actualizaciones e iconos de estado. Nuevo **explorador de archivos** en el lateral izquierdo (Ctrl+Mayús+E): carpetas, unidades, carpetas fijadas, filtro y apertura de PDFs e imágenes en la herramienta en la que estés; Inicio muestra los archivos recientes.

- `v1.22`: extensión de Chrome/Edge (`extension/`) que abre en DocGuard los PDF del navegador (se activa en «Integración»; la comparte con el botón de Word la escucha local y el certificado); los textos largos de las columnas laterales (p. ej. «¿Es una foto? Pasarla antes a modo escáner») ya no se salen.

- `v1.23`: herramienta «Tabla» en Editar PDF (arrastra el recuadro, rellena las celdas o pega desde Excel/Word; cabecera, colores y borde); la negrita de las fuentes estándar ahora usa la negrita del sistema.

- `v1.24`: en Editar, ⌘/Ctrl (o Mayús) + clic o arrastre añade textos a la selección.

- `v1.25`: guías de alineación al mover o redimensionar textos e imágenes (imán a bordes y centros de los demás objetos y de la página; Alt las desactiva).

- `v1.26`: la etiqueta de la herramienta (arriba a la derecha) salta entre Editar PDF y Visor PDF con el mismo documento y en la misma página.

- `v1.27`: abrir un PDF directamente es más rápido: la interfaz arranca ya en el Visor con él (sin pasar por Inicio), la comprobación de firmas no retrasa el dibujo de las páginas, la lista de fuentes se pide después y numpy se carga solo cuando hace falta (primera página nítida a ~1,5 s en vez de ~2,5–3,4 s).

- `v1.28`: interfaz más limpia en el Visor: selector [Visor | Editar] arriba a la derecha; girar, imprimir y cerrar en la barra flotante junto a las páginas y el zoom (la barra del lector solo aparece al buscar); en Windows se quita la fila del menú «Ventana» (está en «⋯»).

- `v1.29`: «Quitar marca de agua…» en Editar (con nada seleccionado): quita «BORRADOR», «COPIA»… en diagonal, contenido marcado como marca de agua y anotaciones de marca de agua, borrando solo esas órdenes del PDF (sin tapar el resto) y con ⌘Z para deshacer (`marcas_agua.py`).

- `v1.30`: el botón «Quitar marca de agua» pasa a la barra principal de Editar (junto a la búsqueda), siempre visible con un documento abierto.

- `v1.31`: la barra del visor (páginas, zoom, ajustar a la página / a la ventana, imprimir) va arriba en todas las vistas y ya no la tapa la página; las novedades se muestran como tarjetas en la ventana de actualización (`novedades/`).

- `v1.32`: «Buscar actualizaciones» en Mac ya no dice «sin conexión» (certificados HTTPS del sistema y de certifi).

- `v1.33`: mano para mover la página (todas las vistas, o Espacio), menú de zoom con más ajustes (ancho, página, alto, 100 %, porcentajes) y comentarios con autor y fecha (pestaña «Comentarios» en Editar).

- `v1.34`: exportar a Word fiel a la página (`towords.py`: sección por página con su tamaño exacto, fondo sin texto y cuadros de texto editables; botón en Editar y modo en Comprimir y convertir).

## Publicar una versión nueva
1. Cambia `VERSION` en `core.py` (por ejemplo `1.18`).
2. Crea la etiqueta igual y súbela: `git tag v1.18 && git push origin main --tags`.
3. GitHub compila Mac y Windows y los publica en *Releases*; las copias instaladas avisarán solas.
