#!/bin/bash
# Construye e instala «Lectiva.app»: abre una ventana con la versión, levanta el servidor y muestra
# la dirección (con QR) para los estudiantes. Uso: bash scripts/mac/instalar_app.sh
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$RAIZ"
VERSION="$(sed -n 's/^VERSION = "\(.*\)"/\1/p' backend/version.py)"
[ -n "$VERSION" ] || { echo "No se pudo leer la versión de backend/version.py"; exit 1; }
command -v swiftc >/dev/null || { echo "Falta swiftc: instala las herramientas de línea de comandos con «xcode-select --install»."; exit 1; }

DIST="$RAIZ/dist"
APP="$DIST/Lectiva.app"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "→ Compilando la aplicación (versión $VERSION)…"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
swiftc -O -swift-version 5 mac/Lectiva.swift -o "$APP/Contents/MacOS/Lectiva"

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
  <key>CFBundleName</key><string>Lectiva</string>
  <key>CFBundleDisplayName</key><string>Lectiva</string>
  <key>CFBundleIdentifier</key><string>cr.ctplaspalmitas.lectiva</string>
  <key>CFBundleExecutable</key><string>Lectiva</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSPrincipalClass</key><string>NSApplication</string>
  <key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict>
  <key>LectivaProyecto</key><string>$RAIZ</string>
</dict>
</plist>
PLIST

echo "→ Firmando…"
codesign --force --deep -s - "$APP" >/dev/null

# La app anterior se llamaba «Examen Digital»: debe estar cerrada para reemplazarla
if pgrep -x ExamenDigital >/dev/null || pgrep -x Lectiva >/dev/null; then
  echo "Cierra la aplicación (Examen Digital o Lectiva) con «Detener servidor y salir» y vuelve a ejecutar este script."
  exit 1
fi

DESTINO="/Applications"
if ! cp -R "$APP" "$DESTINO/" 2>/dev/null; then
  DESTINO="$HOME/Applications"
  mkdir -p "$DESTINO"
fi
rm -rf "$DESTINO/Lectiva.app"
cp -R "$APP" "$DESTINO/"
echo "→ Instalada en $DESTINO/Lectiva.app"

# Quitar la versión anterior con el nombre «Examen Digital» (app, acceso directo e icono del Dock)
DOCK_CAMBIO=0
DOCK_ACTUAL="$(defaults read com.apple.dock persistent-apps 2>/dev/null || true)"
for VIEJA in "/Applications/Examen Digital.app" "$HOME/Applications/Examen Digital.app"; do
  [ -e "$VIEJA" ] && rm -rf "$VIEJA" && echo "→ Eliminada la versión anterior: $VIEJA"
done
[ -L "$HOME/Desktop/Examen Digital" ] && rm -f "$HOME/Desktop/Examen Digital" && echo "→ Eliminado el acceso directo anterior"
if [[ "$DOCK_ACTUAL" == *"Examen%20Digital.app"* || "$DOCK_ACTUAL" == *"Examen Digital.app"* ]]; then
  /usr/bin/python3 - <<'PY'
import plistlib, subprocess
ruta = subprocess.run(["defaults", "export", "com.apple.dock", "-"], capture_output=True, check=True).stdout
dock = plistlib.loads(ruta)
antes = len(dock.get("persistent-apps", []))
dock["persistent-apps"] = [a for a in dock.get("persistent-apps", [])
    if "Examen%20Digital.app" not in a.get("tile-data", {}).get("file-data", {}).get("_CFURLString", "")
    and "Examen Digital.app" not in a.get("tile-data", {}).get("file-data", {}).get("_CFURLString", "")]
if len(dock["persistent-apps"]) != antes:
    subprocess.run(["defaults", "import", "com.apple.dock", "-"], input=plistlib.dumps(dock), check=True)
    print("→ Quitado el icono anterior del Dock")
PY
  DOCK_CAMBIO=1
fi

# Acceso directo en el Escritorio (enlace simbólico: no pide permisos)
ln -sfn "$DESTINO/Lectiva.app" "$HOME/Desktop/Lectiva"
echo "→ Acceso directo en el Escritorio"

# Dock (solo si todavía no está)
if [[ "$DOCK_ACTUAL" != *"Lectiva.app"* ]]; then
  defaults write com.apple.dock persistent-apps -array-add \
    "<dict><key>tile-data</key><dict><key>file-data</key><dict><key>_CFURLString</key><string>$DESTINO/Lectiva.app</string><key>_CFURLStringType</key><integer>0</integer></dict></dict></dict>"
  DOCK_CAMBIO=1
  echo "→ Agregada al Dock"
else
  echo "→ Ya estaba en el Dock"
fi
if [ "$DOCK_CAMBIO" = 1 ]; then killall Dock; fi
echo "Listo. Abre «Lectiva» desde el Dock, el Escritorio o Aplicaciones."
