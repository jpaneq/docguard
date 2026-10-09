# Notas de cada versión (novedades)

Cada versión lleva un archivo `vX.Y.md` (mismo nombre que la etiqueta de git). El workflow lo publica
como notas de la release y la ventana de actualización de DocGuard lo muestra **como tarjetas con iconos**.
Parte de `_plantilla.md`. Sin este archivo, la versión no se publica (lo comprueba `tools/check_novedades.py`).

## Formato
```
# Titular corto y con gancho            ← cabecera con degradado
Una frase que resume la versión.         ← subtítulo (opcional)

## Nuevo                                 ← rótulo de grupo (opcional): Nuevo · Mejorado · Arreglado
- 🔎 **Título de la mejora** — explicación en una frase.
```

## Cómo escribirlas (el estilo que usamos)
- **Para personas, no para programadores:** qué puedes hacer ahora, no qué función se tocó. Nada de nombres de archivos, funciones ni librerías.
- **3 a 6 tarjetas** (máximo 8). Si hay más cambios, agrúpalos en una sola idea.
- **Un icono emoji distinto en cada tarjeta**, que se entienda de un vistazo (🔎 zoom, 🖨️ imprimir, 💬 comentarios, 🛟 recuperación, 📄 Word…).
- **Título: 2 a 6 palabras**, empezando por lo que ganas («Mano para mover la página»). **Detalle: una frase**, de unas 25 palabras como mucho, en tono cercano y en positivo.
- **Orden:** lo más importante primero. Los arreglos, al final (o bajo `## Arreglado`).
- Di lo que **no** cambia si tranquiliza («no toca tu archivo original»).
- No prometas lo que no esté probado.
- Español de España, con «tú».
