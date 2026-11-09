#!/bin/bash
# Construye e instala «Examen Digital.app»: abre una ventana con la versión, levanta el servidor y muestra
# la dirección (con QR) para los estudiantes. Uso: bash scripts/mac/instalar_app.sh
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$RAIZ"
VERSION="$(sed -n 's/^VERSION = "\(.*\)"/\1/p' backend/version.py)"
[ -n "$VERSION" ] || { echo "No se pudo leer la versión de backend/version.py"; exit 1; }
command -v swiftc >/dev/null || { echo "Falta swiftc: instala las herramientas de línea de comandos con «xcode-select --install»."; exit 1; }

DIST="$RAIZ/dist"
APP="$DIST/Examen Digital.app"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "→ Compilando la aplicación (versión $VERSION)…"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
swiftc -O -swift-version 5 mac/ExamenDigital.swift -o "$APP/Contents/MacOS/ExamenDigital"

echo "→ Dibujando el icono…"
swiftc -O -swift-version 5 mac/icono.swift -o "$TMP/icono"
"$TMP/icono" "$TMP/icono.png"
SET="$TMP/AppIcon.iconset"
mkdir -p "$SET"
for t in 16 32 128 256 512; do
  sips -z $t $t "$TMP/icono.png" --out "$SET/icon_${t}x${t}.png" >/dev/null
  sips -z $((t*2)) $((t*2)) "$TMP/icono.png" --out "$SET/icon_${t}x${t}@2x.png" >/dev/null
done
iconutil -c icns "$SET" -o "$APP/Contents/Resources/AppIcon.icns"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Examen Digital</string>
  <key>CFBundleDisplayName</key><string>Examen Digital</string>
  <key>CFBundleIdentifier</key><string>cr.ctplaspalmitas.examendigital</string>
  <key>CFBundleExecutable</key><string>ExamenDigital</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSPrincipalClass</key><string>NSApplication</string>
  <key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict>
  <key>ExamenDigitalProyecto</key><string>$RAIZ</string>
</dict>
</plist>
PLIST

echo "→ Firmando…"
codesign --force --deep -s - "$APP" >/dev/null

DESTINO="/Applications"
if ! cp -R "$APP" "$DESTINO/" 2>/dev/null; then
  DESTINO="$HOME/Applications"
  mkdir -p "$DESTINO"
fi
rm -rf "$DESTINO/Examen Digital.app"
cp -R "$APP" "$DESTINO/"
echo "→ Instalada en $DESTINO/Examen Digital.app"

# Acceso directo en el Escritorio (enlace simbólico: no pide permisos)
ln -sfn "$DESTINO/Examen Digital.app" "$HOME/Desktop/Examen Digital"
echo "→ Acceso directo en el Escritorio"

# Dock (solo si todavía no está)
if ! defaults read com.apple.dock persistent-apps 2>/dev/null | grep -q "Examen Digital"; then
  defaults write com.apple.dock persistent-apps -array-add \
    "<dict><key>tile-data</key><dict><key>file-data</key><dict><key>_CFURLString</key><string>$DESTINO/Examen Digital.app</string><key>_CFURLStringType</key><integer>0</integer></dict></dict></dict>"
  killall Dock
  echo "→ Agregada al Dock"
else
  echo "→ Ya estaba en el Dock"
fi
echo "Listo. Abre «Examen Digital» desde el Dock, el Escritorio o Aplicaciones."
