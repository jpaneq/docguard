"""Genera icon.png, icon.ico (Windows) e icon.icns (macOS)."""

from PIL import Image, ImageDraw

S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# Fondo: cuadrado redondeado con degradado azul.
grad = Image.new("RGBA", (S, S))
gd = ImageDraw.Draw(grad)
for y in range(S):
    t = y / S
    gd.line([(0, y), (S, y)], fill=(int(30 + 20 * t), int(90 + 40 * t), int(200 - 40 * t), 255))
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle((40, 40, S - 40, S - 40), radius=200, fill=255)
img.paste(grad, (0, 0), mask)

# Documento blanco.
d.rounded_rectangle((250, 170, 700, 780), radius=40, fill=(255, 255, 255, 255))
for i, y in enumerate(range(270, 640, 70)):
    color = (20, 20, 20, 255) if i in (1, 3) else (180, 190, 210, 255)  # líneas censuradas en negro
    d.rounded_rectangle((310, y, 640 - (i % 2) * 80, y + 34), radius=10, fill=color)

# Escudo con marca de verificación.
cx, top = 690, 520
shield = [(cx - 190, top), (cx, top - 60), (cx + 190, top), (cx + 170, top + 250),
          (cx, top + 380), (cx - 170, top + 250)]
d.polygon(shield, fill=(46, 204, 113, 255))
d.line([(cx - 90, top + 150), (cx - 20, top + 220), (cx + 100, top + 80)], fill="white", width=48, joint="curve")

img.save("icon.png")
img.save("icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
img.save("icon.icns")
print("iconos generados")
