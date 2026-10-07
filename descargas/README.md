# Descargas de DocGuard (siempre la última versión)

| Sistema | Descarga directa (siempre la última) |
|---|---|
| Windows | https://github.com/jpaneq/docguard/releases/latest/download/DocGuard-windows.zip |
| Mac | https://github.com/jpaneq/docguard/releases/latest/download/DocGuard-mac.zip |

Huellas SHA-256: las mismas URLs terminadas en `.sha256`.
Todas las versiones: https://github.com/jpaneq/docguard/releases

Los enlaces apuntan siempre a la última release, así que no hay que actualizarlos al sacar una versión nueva.

**Por qué no están los .zip dentro de la carpeta:** pesan ~155 MB cada uno y GitHub rechaza archivos de más de 100 MB en un repositorio. Se guardan como adjuntos de la release, que es lo que ya descarga el actualizador.

Desde terminal: `./descargas/descargar.sh [windows|mac]` baja el zip de la última versión a esta carpeta (está en `.gitignore`).
