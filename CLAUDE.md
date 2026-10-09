# Instrucciones para IAs que trabajen en este repositorio (DocGuard)

## Publicar una versión (obligatorio al terminar cambios)
1. Subir `core.VERSION` en `core.py` (p. ej. "1.22").
2. Commit y push a `main`, y crear/subir la etiqueta que coincide: `git tag v1.22 && git push origin v1.22`.
2b. **Novedades visuales:** crear `novedades/vX.Y.md` (mismo nombre que la etiqueta) con este formato; el workflow lo publica como notas de la release y la ventana de actualización lo muestra como tarjetas con iconos:
   ```
   # Titular corto
   Frase de resumen.

   - 🔎 **Título de la mejora** — explicación en una frase, para el usuario (no técnica).
   ```
3. GitHub Actions (`.github/workflows/build.yml`) compila Windows y Mac y publica `DocGuard-windows.zip`, `DocGuard-mac.zip` y sus `.sha256` en *Releases*. Esperar a que termine con éxito (`gh run watch`).
4. **Carpeta `descargas/`:** debe ser siempre el sitio donde se encuentra la última versión para Mac y Windows. Sus enlaces usan `releases/latest/download/…`, así que se actualizan solos al publicar la release. No añadir los .zip al repo (superan los 100 MB de GitHub). Si cambian los nombres de los adjuntos, actualizar `descargas/README.md` y `descargas/descargar.sh`.
5. Entregar al usuario los dos .zip de la última versión (descargarlos con `gh release download vX.Y --repo jpaneq/docguard`) y dar el enlace de la release.

## Cuidados
- No dejar ramas con trabajo sin fusionar ni publicar: antes de publicar, revisar `git branch -r` y `git log origin/main..origin/<rama>`.
- `Page.insert_text()` de PyMuPDF no admite `fontbuffer`: usar `editor._kw(page, kw)`.
- El actualizador (`updater.py`) lee `releases/latest`; no marcar como "latest" una release incompleta.
