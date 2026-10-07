#!/bin/sh
# Descarga la última versión publicada de DocGuard a esta carpeta: ./descargar.sh [windows|mac]
cd "$(dirname "$0")"
for p in ${1:-windows mac}; do
  curl -L -f -O "https://github.com/jpaneq/docguard/releases/latest/download/DocGuard-$p.zip"
  curl -L -f -O "https://github.com/jpaneq/docguard/releases/latest/download/DocGuard-$p.zip.sha256"
done
