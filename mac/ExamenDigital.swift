// Examen Digital para Mac: abre el sistema con un clic.
// Levanta el servidor, muestra la versión y la dirección con la que se conectan los estudiantes (con QR),
// vigila que la IP no cambie y detiene el servidor al salir.
import Cocoa
import CoreImage

let PUERTO = 8001
let VERDE = NSColor(srgbRed: 0.04, green: 0.48, blue: 0.28, alpha: 1)

// MARK: - Red

func ipLocal() -> String? {
    var lista: UnsafeMutablePointer<ifaddrs>?
    guard getifaddrs(&lista) == 0, let primera = lista else { return nil }
    defer { freeifaddrs(lista) }
    var candidatas: [(nombre: String, ip: String)] = []
    var cursor: UnsafeMutablePointer<ifaddrs>? = primera
    while let actual = cursor {
        defer { cursor = actual.pointee.ifa_next }
        guard let dir = actual.pointee.ifa_addr, dir.pointee.sa_family == UInt8(AF_INET) else { continue }
        let flags = Int32(actual.pointee.ifa_flags)
        guard flags & IFF_UP != 0, flags & IFF_LOOPBACK == 0 else { continue }
        var buffer = [CChar](repeating: 0, count: Int(NI_MAXHOST))
        guard getnameinfo(dir, socklen_t(dir.pointee.sa_len), &buffer, socklen_t(buffer.count), nil, 0, NI_NUMERICHOST) == 0 else { continue }
        let ip = String(cString: buffer)
        let partes = ip.split(separator: ".").compactMap { Int($0) }
        let privada = partes.count == 4 && (partes[0] == 10 || (partes[0] == 172 && (16...31).contains(partes[1])) || (partes[0] == 192 && partes[1] == 168))
        if privada { candidatas.append((String(cString: actual.pointee.ifa_name), ip)) }
    }
    return candidatas.first(where: { $0.nombre == "en0" })?.ip ?? candidatas.first?.ip
}

func nombreLocal() -> String? {
    let p = Process()
    p.executableURL = URL(fileURLWithPath: "/usr/sbin/scutil")
    p.arguments = ["--get", "LocalHostName"]
    let salida = Pipe()
    p.standardOutput = salida
    p.standardError = Pipe()
    do { try p.run() } catch { return nil }
    p.waitUntilExit()
    let texto = String(data: salida.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    return texto.isEmpty ? nil : "\(texto).local"
}

func imagenQR(_ texto: String, lado: CGFloat) -> NSImage? {
    guard let filtro = CIFilter(name: "CIQRCodeGenerator") else { return nil }
    filtro.setValue(Data(texto.utf8), forKey: "inputMessage")
    filtro.setValue("M", forKey: "inputCorrectionLevel")
    guard let salida = filtro.outputImage else { return nil }
    let escala = lado / salida.extent.width
    let grande = salida.transformed(by: CGAffineTransform(scaleX: escala, y: escala))
    let rep = NSCIImageRep(ciImage: grande)
    let imagen = NSImage(size: NSSize(width: lado, height: lado))
    imagen.addRepresentation(rep)
    return imagen
}

// MARK: - Servidor

enum EstadoServidor {
    case iniciando, enLinea, yaEjecutando, detenido(String)
}

final class Servidor {
    let proyecto: URL
    private(set) var proceso: Process?
    private(set) var loLanzamos = false
    var alCambiar: ((EstadoServidor) -> Void)?
    private var temporizador: Timer?
    private(set) var estado: EstadoServidor = .iniciando { didSet { alCambiar?(estado) } }
    private var inicio = Date()

    init(proyecto: URL) { self.proyecto = proyecto }

    var logURL: URL { proyecto.appendingPathComponent("logs/servidor.log") }

    func responde(_ alTerminar: @escaping (Bool) -> Void) {
        var pedido = URLRequest(url: URL(string: "http://127.0.0.1:\(PUERTO)/api/config")!)
        pedido.timeoutInterval = 1.5
        pedido.cachePolicy = .reloadIgnoringLocalCacheData
        URLSession.shared.dataTask(with: pedido) { _, respuesta, _ in
            let bien = (respuesta as? HTTPURLResponse)?.statusCode == 200
            DispatchQueue.main.async { alTerminar(bien) }
        }.resume()
    }

    func iniciar() {
        estado = .iniciando
        inicio = Date()
        responde { [weak self] yaCorre in
            guard let self = self else { return }
            if yaCorre {
                self.estado = .yaEjecutando
            } else {
                self.lanzar()
            }
            self.vigilar()
        }
    }

    private func lanzar() {
        let python = proyecto.appendingPathComponent(".venv/bin/python")
        guard FileManager.default.isExecutableFile(atPath: python.path) else {
            estado = .detenido("No se encontró el entorno de Python en «.venv» del proyecto.")
            return
        }
        try? FileManager.default.createDirectory(at: logURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        if !FileManager.default.fileExists(atPath: logURL.path) { FileManager.default.createFile(atPath: logURL.path, contents: nil) }
        guard let log = try? FileHandle(forWritingTo: logURL) else {
            estado = .detenido("No se pudo abrir el registro del servidor.")
            return
        }
        log.seekToEndOfFile()
        let p = Process()
        p.executableURL = python
        p.arguments = ["-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "\(PUERTO)"]
        p.currentDirectoryURL = proyecto
        p.standardOutput = log
        p.standardError = log
        p.terminationHandler = { [weak self] _ in
            DispatchQueue.main.async {
                guard let self = self, self.loLanzamos, self.proceso != nil else { return }
                self.proceso = nil
                let temprano = Date().timeIntervalSince(self.inicio) < 8
                self.estado = .detenido(temprano
                    ? "El servidor no pudo iniciar. Puede que el puerto \(PUERTO) esté ocupado; revisa el registro."
                    : "El servidor se detuvo.")
            }
        }
        do {
            try p.run()
            proceso = p
            loLanzamos = true
        } catch {
            estado = .detenido("No se pudo iniciar el servidor: \(error.localizedDescription)")
        }
    }

    private func vigilar() {
        temporizador?.invalidate()
        temporizador = Timer.scheduledTimer(withTimeInterval: 1.5, repeats: true) { [weak self] _ in
            guard let self = self else { return }
            if case .detenido = self.estado { return }
            self.responde { vivo in
                if case .detenido = self.estado { return }
                if vivo {
                    if self.loLanzamos { if case .enLinea = self.estado {} else { self.estado = .enLinea } }
                    else if case .yaEjecutando = self.estado {} else { self.estado = .yaEjecutando }
                } else if case .enLinea = self.estado {
                    self.estado = .iniciando
                } else if case .yaEjecutando = self.estado {
                    self.estado = .detenido("El servidor que estaba en ejecución se detuvo.")
                } else if Date().timeIntervalSince(self.inicio) > 40 {
                    self.estado = .detenido("El servidor tardó demasiado en responder. Revisa el registro.")
                }
            }
        }
    }

    func reiniciar() {
        detener()
        loLanzamos = false
        iniciar()
    }

    /// Detiene el servidor solo si lo lanzó esta app.
    func detener() {
        temporizador?.invalidate()
        guard let p = proceso, p.isRunning else { proceso = nil; return }
        let pid = p.processIdentifier
        proceso = nil
        p.terminate()
        let limite = Date().addingTimeInterval(5)
        while p.isRunning && Date() < limite { Thread.sleep(forTimeInterval: 0.1) }
        if p.isRunning { kill(pid, SIGKILL) }
    }
}

// MARK: - Ventana

final class Ventana: NSObject, NSApplicationDelegate, NSWindowDelegate {
    var ventana: NSWindow!
    var servidor: Servidor!
    var actividad: NSObjectProtocol?

    let versionTxt = NSTextField(labelWithString: "")
    let puntoEstado = NSView()
    let estadoTxt = NSTextField(wrappingLabelWithString: "Iniciando…")
    let urlTxt = NSTextField(labelWithString: "")
    let nombreTxt = NSTextField(labelWithString: "")
    let avisoTxt = NSTextField(wrappingLabelWithString: "")
    let qr = NSImageView()
    let copiar = NSButton(title: "Copiar dirección", target: nil, action: nil)
    let abrir = NSButton(title: "Abrir panel docente", target: nil, action: nil)
    let registro = NSButton(title: "Ver registro", target: nil, action: nil)
    let reiniciarBtn = NSButton(title: "Reiniciar servidor", target: nil, action: nil)
    let salir = NSButton(title: "Detener servidor y salir", target: nil, action: nil)

    var ipActual: String?
    var sinConfirmar = false
    var ipCambio = false
    var temporizadorIP: Timer?

    func applicationDidFinishLaunching(_ notificacion: Notification) {
        guard let proyecto = rutaProyecto() else { NSApp.terminate(nil); return }
        servidor = Servidor(proyecto: proyecto)
        servidor.alCambiar = { [weak self] e in self?.pintarEstado(e) }
        construirMenu()
        construirVentana()
        actividad = ProcessInfo.processInfo.beginActivity(options: [.idleSystemSleepDisabled, .userInitiated],
                                                          reason: "Servidor de Examen Digital en el aula")
        refrescarIP(inicial: true)
        temporizadorIP = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in self?.refrescarIP(inicial: false) }
        servidor.iniciar()
        NSApp.activate(ignoringOtherApps: true)
        // Uso interno para verificar la ventana: --captura archivo.png guarda una imagen y sale sin preguntar
        if let i = CommandLine.arguments.firstIndex(of: "--captura"), i + 1 < CommandLine.arguments.count {
            let destino = CommandLine.arguments[i + 1]
            DispatchQueue.main.asyncAfter(deadline: .now() + 6) {
                if let vista = self.ventana.contentView, let rep = vista.bitmapImageRepForCachingDisplay(in: vista.bounds) {
                    vista.cacheDisplay(in: vista.bounds, to: rep)
                    try? rep.representation(using: .png, properties: [:])?.write(to: URL(fileURLWithPath: destino))
                }
                self.sinConfirmar = true
                NSApp.terminate(nil)
            }
        }
    }

    // Ruta del proyecto: la graba el instalador en Info.plist; si falta o ya no existe, se pide una vez.
    func rutaProyecto() -> URL? {
        func valida(_ ruta: String?) -> URL? {
            guard let r = ruta, FileManager.default.fileExists(atPath: r + "/backend/main.py") else { return nil }
            return URL(fileURLWithPath: r)
        }
        if let u = valida(Bundle.main.object(forInfoDictionaryKey: "ExamenDigitalProyecto") as? String) { return u }
        if let u = valida(UserDefaults.standard.string(forKey: "proyecto")) { return u }
        let panel = NSOpenPanel()
        panel.message = "Elige la carpeta del proyecto Examen_digital_simple"
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        NSApp.activate(ignoringOtherApps: true)
        guard panel.runModal() == .OK, let u = panel.url, valida(u.path) != nil else {
            let a = NSAlert()
            a.messageText = "No se encontró el proyecto"
            a.informativeText = "La carpeta elegida no contiene «backend/main.py»."
            a.runModal()
            return nil
        }
        UserDefaults.standard.set(u.path, forKey: "proyecto")
        return u
    }

    func construirMenu() {
        let barra = NSMenu()
        let app = NSMenuItem()
        barra.addItem(app)
        let menu = NSMenu()
        menu.addItem(withTitle: "Salir de Examen Digital", action: #selector(pedirSalir), keyEquivalent: "q").target = self
        app.submenu = menu
        NSApp.mainMenu = barra
    }

    func etiqueta(_ t: NSTextField, tam: CGFloat, peso: NSFont.Weight = .regular, color: NSColor = .labelColor) {
        t.font = .systemFont(ofSize: tam, weight: peso)
        t.textColor = color
        t.isSelectable = true
    }

    func construirVentana() {
        let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "?"
        let icono = NSImageView(image: NSApp.applicationIconImage)
        icono.imageScaling = .scaleProportionallyUpOrDown
        icono.widthAnchor.constraint(equalToConstant: 64).isActive = true
        icono.heightAnchor.constraint(equalToConstant: 64).isActive = true
        let titulo = NSTextField(labelWithString: "Examen Digital")
        etiqueta(titulo, tam: 26, peso: .bold)
        versionTxt.stringValue = "Versión \(version)"
        etiqueta(versionTxt, tam: 13, color: .secondaryLabelColor)
        let textos = NSStackView(views: [titulo, versionTxt]); textos.orientation = .vertical; textos.alignment = .leading; textos.spacing = 2
        let cabecera = NSStackView(views: [icono, textos]); cabecera.orientation = .horizontal; cabecera.spacing = 14

        puntoEstado.wantsLayer = true
        puntoEstado.layer?.cornerRadius = 6
        puntoEstado.widthAnchor.constraint(equalToConstant: 12).isActive = true
        puntoEstado.heightAnchor.constraint(equalToConstant: 12).isActive = true
        etiqueta(estadoTxt, tam: 14, peso: .medium)
        estadoTxt.preferredMaxLayoutWidth = 440
        let estado = NSStackView(views: [puntoEstado, estadoTxt]); estado.orientation = .horizontal; estado.spacing = 8; estado.alignment = .centerY

        let rotulo = NSTextField(labelWithString: "Los estudiantes se conectan con esta dirección (mismo wifi):")
        etiqueta(rotulo, tam: 13, color: .secondaryLabelColor)
        etiqueta(urlTxt, tam: 26, peso: .bold, color: VERDE)
        urlTxt.font = .monospacedSystemFont(ofSize: 24, weight: .bold)
        etiqueta(nombreTxt, tam: 12, color: .secondaryLabelColor)
        etiqueta(avisoTxt, tam: 13, peso: .semibold, color: .systemOrange)
        avisoTxt.preferredMaxLayoutWidth = 440
        avisoTxt.isHidden = true
        qr.imageScaling = .scaleProportionallyUpOrDown
        qr.widthAnchor.constraint(equalToConstant: 190).isActive = true
        qr.heightAnchor.constraint(equalToConstant: 190).isActive = true
        qr.wantsLayer = true
        qr.layer?.backgroundColor = NSColor.white.cgColor
        qr.layer?.cornerRadius = 8
        copiar.target = self; copiar.action = #selector(copiarURL)
        let tarjeta = NSStackView(views: [rotulo, urlTxt, nombreTxt, avisoTxt, qr, copiar])
        tarjeta.orientation = .vertical; tarjeta.alignment = .centerX; tarjeta.spacing = 10
        tarjeta.edgeInsets = NSEdgeInsets(top: 18, left: 20, bottom: 18, right: 20)
        tarjeta.wantsLayer = true
        tarjeta.layer?.backgroundColor = NSColor.controlBackgroundColor.cgColor
        tarjeta.layer?.cornerRadius = 12
        tarjeta.layer?.borderWidth = 1
        tarjeta.layer?.borderColor = NSColor.separatorColor.cgColor

        abrir.target = self; abrir.action = #selector(abrirPanel); abrir.bezelStyle = .rounded; abrir.keyEquivalent = "\r"
        registro.target = self; registro.action = #selector(verRegistro); registro.bezelStyle = .rounded
        reiniciarBtn.target = self; reiniciarBtn.action = #selector(reiniciar); reiniciarBtn.bezelStyle = .rounded; reiniciarBtn.isHidden = true
        salir.target = self; salir.action = #selector(pedirSalir); salir.bezelStyle = .rounded
        for b in [abrir, registro, reiniciarBtn, salir, copiar] {
            b.controlSize = .large
            b.heightAnchor.constraint(equalToConstant: 34).isActive = true
        }
        let fila1 = NSStackView(views: [abrir, registro, reiniciarBtn]); fila1.orientation = .horizontal; fila1.spacing = 10
        let fila2 = NSStackView(views: [salir]); fila2.orientation = .horizontal

        let ayuda = NSTextField(wrappingLabelWithString: "Deja esta ventana abierta mientras haya examen. Si la cierras, el sistema se detiene.")
        etiqueta(ayuda, tam: 12, color: .tertiaryLabelColor)
        ayuda.preferredMaxLayoutWidth = 440

        let raiz = NSStackView(views: [cabecera, estado, tarjeta, fila1, fila2, ayuda])
        raiz.orientation = .vertical; raiz.alignment = .centerX; raiz.spacing = 16
        raiz.edgeInsets = NSEdgeInsets(top: 24, left: 28, bottom: 22, right: 28)
        raiz.translatesAutoresizingMaskIntoConstraints = false
        tarjeta.widthAnchor.constraint(equalToConstant: 460).isActive = true

        ventana = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 540, height: 680),
                           styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
        ventana.title = "Examen Digital"
        ventana.delegate = self
        ventana.isReleasedWhenClosed = false
        let contenido = NSView()
        contenido.addSubview(raiz)
        NSLayoutConstraint.activate([
            raiz.topAnchor.constraint(equalTo: contenido.topAnchor),
            raiz.leadingAnchor.constraint(equalTo: contenido.leadingAnchor),
            raiz.trailingAnchor.constraint(equalTo: contenido.trailingAnchor),
            raiz.bottomAnchor.constraint(equalTo: contenido.bottomAnchor),
        ])
        ventana.contentView = contenido
        contenido.layoutSubtreeIfNeeded()
        ventana.setContentSize(NSSize(width: 540, height: raiz.fittingSize.height))
        ventana.center()
        ventana.makeKeyAndOrderFront(nil)
        pintarEstado(.iniciando)
    }

    // MARK: Estado e IP

    func pintarEstado(_ e: EstadoServidor) {
        var texto = "", color = NSColor.systemOrange, caido = false
        switch e {
        case .iniciando: texto = "Iniciando el servidor…"
        case .enLinea: texto = "Servidor en línea"; color = .systemGreen
        case .yaEjecutando: texto = "El servidor ya estaba en ejecución (esta ventana no lo apagará al salir)"; color = .systemGreen
        case .detenido(let motivo): texto = motivo; color = .systemRed; caido = true
        }
        estadoTxt.stringValue = texto
        puntoEstado.layer?.backgroundColor = color.cgColor
        reiniciarBtn.isHidden = !caido
        abrir.isEnabled = !caido
    }

    func refrescarIP(inicial: Bool) {
        let nueva = ipLocal()
        if !inicial && nueva != ipActual && ipActual != nil && nueva != nil { ipCambio = true }
        ipActual = nueva
        guard let ip = nueva else {
            urlTxt.stringValue = "Sin conexión a la red"
            urlTxt.font = .systemFont(ofSize: 20, weight: .semibold)
            urlTxt.textColor = .systemRed
            qr.image = nil
            nombreTxt.stringValue = "Conéctate al wifi del aula para que los estudiantes puedan entrar."
            return
        }
        let url = "http://\(ip):\(PUERTO)"
        urlTxt.font = .monospacedSystemFont(ofSize: 24, weight: .bold)
        urlTxt.textColor = VERDE
        urlTxt.stringValue = url
        qr.image = imagenQR(url, lado: 190)
        if let nombre = nombreLocal() { nombreTxt.stringValue = "También por nombre: http://\(nombre):\(PUERTO)" } else { nombreTxt.stringValue = "" }
        avisoTxt.stringValue = "La dirección cambió. Avisa a los estudiantes que usen esta nueva."
        avisoTxt.isHidden = !ipCambio
    }

    // MARK: Acciones

    @objc func copiarURL() {
        guard let ip = ipActual else { return }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString("http://\(ip):\(PUERTO)", forType: .string)
        copiar.title = "¡Copiada!"
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { self.copiar.title = "Copiar dirección" }
    }

    @objc func abrirPanel() { NSWorkspace.shared.open(URL(string: "http://localhost:\(PUERTO)/docente")!) }
    @objc func verRegistro() { NSWorkspace.shared.open(servidor.logURL) }
    @objc func reiniciar() { servidor.reiniciar() }
    @objc func pedirSalir() { NSApp.terminate(nil) }

    func windowShouldClose(_ sender: NSWindow) -> Bool { NSApp.terminate(nil); return false }
    func applicationShouldTerminateAfterLastWindowClosed(_ app: NSApplication) -> Bool { false }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        if servidor.loLanzamos, servidor.proceso != nil, !sinConfirmar {
            let a = NSAlert()
            a.messageText = "¿Detener el servidor y salir?"
            a.informativeText = "Los estudiantes conectados perderán la conexión. Sus respuestas ya guardadas se conservan."
            a.addButton(withTitle: "Detener y salir")
            a.addButton(withTitle: "Cancelar")
            a.alertStyle = .warning
            if a.runModal() != .alertFirstButtonReturn { return .terminateCancel }
        }
        servidor.detener()
        if let t = actividad { ProcessInfo.processInfo.endActivity(t) }
        return .terminateNow
    }
}

let app = NSApplication.shared
let delegado = Ventana()
app.delegate = delegado
app.setActivationPolicy(.regular)
app.run()
