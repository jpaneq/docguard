#!/bin/sh
# Sube DocGuard a GitHub (repositorio privado), compila las versiones de Windows y macOS
# en GitHub Actions y descarga el resultado en dist-github/. También publica la página
# de verificación del QR en un repositorio público aparte (GitHub Pages).
# Solo hace falta iniciar sesión en GitHub la primera vez.
set -e
cd "$(dirname "$0")"
command -v gh >/dev/null || { echo "Instala GitHub CLI: brew install gh"; exit 1; }
gh auth status >/dev/null 2>&1 || gh auth login --web --git-protocol https
USER=$(gh api user --jq .login)
REPO="${DOCGUARD_REPO:-docguard}"

# 1. Repositorio privado con el código y todas las versiones (etiquetas)
if ! gh repo view "$USER/$REPO" >/dev/null 2>&1; then
  gh repo create "$USER/$REPO" --private --source . --remote origin --description "DocGuard: proteger, editar y firmar documentos"
fi
git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/$USER/$REPO.git"
BRANCH=$(git branch --show-current)
git push -u origin "$BRANCH" --tags

# 2. Página de verificación del QR (repositorio público, solo con esa página)
PAGES="$REPO-verificar"
if ! gh repo view "$USER/$PAGES" >/dev/null 2>&1; then
  TMP=$(mktemp -d)
  cp docs/verificar.html "$TMP/verificar.html"
  cp docs/verificar.html "$TMP/index.html"
  (cd "$TMP" && git init -q -b main && git add . && git commit -qm "Página de verificación de DocGuard" \
    && gh repo create "$USER/$PAGES" --public --source . --push --description "Verificación de copias de DocGuard")
  gh api -X POST "repos/$USER/$PAGES/pages" -f "source[branch]=main" -f "source[path]=/" >/dev/null 2>&1 || true
fi
echo "Página de verificación del QR: https://$USER.github.io/$PAGES/verificar.html"

# 3. Esperar a la compilación y descargar los ejecutables
echo "Compilando en GitHub (tarda unos 10-15 minutos)…"
sleep 10
RUN=$(gh run list --repo "$USER/$REPO" --workflow build.yml --branch "$BRANCH" --limit 1 --json databaseId --jq '.[0].databaseId')
gh run watch "$RUN" --repo "$USER/$REPO" --exit-status
rm -rf dist-github && gh run download "$RUN" --repo "$USER/$REPO" --dir dist-github
echo "Listo. Windows: dist-github/DocGuard-Windows/  ·  macOS: dist-github/DocGuard-macOS/"
