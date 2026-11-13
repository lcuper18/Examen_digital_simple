// Dibuja el icono de Lectiva (1024 x 1024) y lo guarda como PNG: swift icono.swift salida.png
// Con --sangrado el color llena todo el cuadrado (sin esquinas ni sombra): sirve para los iconos del celular, que el sistema recorta.
import Cocoa

let lado: CGFloat = 1024
let sangrado = CommandLine.arguments.contains("--sangrado")
let salida = CommandLine.arguments.dropFirst().first(where: { !$0.hasPrefix("--") }) ?? "icono.png"

guard let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(lado), pixelsHigh: Int(lado), bitsPerSample: 8,
                                 samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB,
                                 bytesPerRow: 0, bitsPerPixel: 0) else { exit(1) }
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
let g = NSGraphicsContext.current!.cgContext

// Cuadrado redondeado con el margen de los iconos de macOS
let caja = sangrado ? CGRect(x: 0, y: 0, width: lado, height: lado) : CGRect(x: 100, y: 100, width: 824, height: 824)
let forma = sangrado ? CGPath(rect: caja, transform: nil) : CGPath(roundedRect: caja, cornerWidth: 185, cornerHeight: 185, transform: nil)
if !sangrado {
    g.saveGState()
    g.setShadow(offset: CGSize(width: 0, height: -14), blur: 28, color: NSColor.black.withAlphaComponent(0.35).cgColor)
    g.addPath(forma)
    g.setFillColor(NSColor(srgbRed: 0.04, green: 0.48, blue: 0.28, alpha: 1).cgColor)
    g.fillPath()
    g.restoreGState()
}

g.saveGState()
g.addPath(forma)
g.clip()
let degradado = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(), colors: [
    NSColor(srgbRed: 0.00, green: 0.78, blue: 0.55, alpha: 1).cgColor,
    NSColor(srgbRed: 0.03, green: 0.40, blue: 0.27, alpha: 1).cgColor,
] as CFArray, locations: [0, 1])!
g.drawLinearGradient(degradado, start: CGPoint(x: 512, y: sangrado ? 1024 : 924), end: CGPoint(x: 512, y: sangrado ? 0 : 100), options: [])
g.restoreGState()

// Portapapeles blanco con visto
let hoja = CGRect(x: 292, y: 250, width: 440, height: 560)
g.setFillColor(NSColor.white.cgColor)
g.addPath(CGPath(roundedRect: hoja, cornerWidth: 56, cornerHeight: 56, transform: nil))
g.fillPath()
let pinza = CGRect(x: 392, y: 756, width: 240, height: 96)
g.setFillColor(NSColor(srgbRed: 0.03, green: 0.34, blue: 0.22, alpha: 1).cgColor)
g.addPath(CGPath(roundedRect: pinza, cornerWidth: 36, cornerHeight: 36, transform: nil))
g.fillPath()
g.setFillColor(NSColor.white.cgColor)
g.fillEllipse(in: CGRect(x: 488, y: 790, width: 48, height: 48))

g.setStrokeColor(NSColor(srgbRed: 0.04, green: 0.48, blue: 0.28, alpha: 1).cgColor)
g.setLineWidth(56)
g.setLineCap(.round)
g.setLineJoin(.round)
g.move(to: CGPoint(x: 392, y: 520))
g.addLine(to: CGPoint(x: 480, y: 432))
g.addLine(to: CGPoint(x: 640, y: 612))
g.strokePath()
g.setLineWidth(30)
g.setStrokeColor(NSColor(srgbRed: 0.04, green: 0.48, blue: 0.28, alpha: 0.35).cgColor)
for y: CGFloat in [360, 300] {
    g.move(to: CGPoint(x: 372, y: y)); g.addLine(to: CGPoint(x: 652, y: y)); g.strokePath()
}
NSGraphicsContext.restoreGraphicsState()

guard let png = rep.representation(using: .png, properties: [:]) else { exit(1) }
try png.write(to: URL(fileURLWithPath: salida))
