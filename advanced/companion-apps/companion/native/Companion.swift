import AppKit
import Foundation
import WebKit
import ServiceManagement

final class Companion: NSObject, NSApplicationDelegate, NSWindowDelegate, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate, NSMenuDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var status: NSStatusItem!
    var process: Process?
    var bootFolder: URL!
    var expectedHost: String?
    var expectedPort: Int?
    var ready = false
    var startupTimer: Timer?
    var logHandle: FileHandle?
    var serviceURL: URL?
    var sessionToken = ""
    var appDataFolder: URL {
        if let path = ProcessInfo.processInfo.environment["CROWPANEL_APP_DATA"] { return URL(fileURLWithPath: path) }
        return FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/CrowPanel Companion")
    }
    var paused = true
    var pauseItem: NSMenuItem!
    var startupItem: NSMenuItem!
    var connectionItem: NSMenuItem!

    // Draw once at menu-bar size. Template tint follows macOS light/dark appearance.
    static func statusIcon() -> NSImage {
        let icon = NSImage(size: NSSize(width: 22, height: 16), flipped: false) { _ in
            NSColor.black.setStroke()
            NSColor.black.setFill()
            let border = NSBezierPath(roundedRect: NSRect(x: 1.5, y: 3.5, width: 19, height: 9), xRadius: 1, yRadius: 1)
            border.lineWidth = 1
            border.stroke()
            // Match the workshop's pixel smile: square eyes and an eleven-pixel arc.
            // Positions are fractions of the panel outline, measured from its lower left.
            let eyes = [(0.328, 0.70), (0.674, 0.70)]
            let smile = [(0.227, 0.47), (0.281, 0.374), (0.337, 0.286),
                         (0.389, 0.229), (0.445, 0.229), (0.500, 0.229),
                         (0.556, 0.229), (0.612, 0.229), (0.665, 0.286),
                         (0.720, 0.374), (0.774, 0.47)]
            for (points, size) in [(eyes, CGFloat(1)), (smile, CGFloat(0.8))] {
                for (x, y) in points {
                    NSBezierPath(rect: NSRect(x: 1.5 + CGFloat(x) * 19 - size / 2,
                                             y: 3.5 + CGFloat(y) * 9 - size / 2,
                                             width: size, height: size)).fill()
                }
            }
            return true
        }
        icon.isTemplate = true
        return icon
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        let menu = NSMenu()
        menu.delegate = self
        connectionItem = menu.addItem(withTitle: "Starting…", action: nil, keyEquivalent: "")
        menu.addItem(.separator())
        menu.addItem(withTitle: "Open CrowPanel Companion", action: #selector(show), keyEquivalent: "")
        pauseItem = menu.addItem(withTitle: "Resume connection", action: #selector(togglePause), keyEquivalent: "")
        startupItem = menu.addItem(withTitle: "Start at sign-in", action: #selector(toggleStartup), keyEquivalent: "")
        menu.addItem(.separator())
        menu.addItem(withTitle: "Quit CrowPanel Companion", action: #selector(quit), keyEquivalent: "q")
        for item in menu.items { item.target = self }
        status = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        status.button?.image = Self.statusIcon()
        status.button?.setAccessibilityLabel("CrowPanel Companion")
        status.menu = menu
        let config = WKWebViewConfiguration()
        web = WKWebView(frame: .zero, configuration: config)
        web.navigationDelegate = self
        web.uiDelegate = self
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 760, height: 860), styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "CrowPanel Companion"
        window.minSize = NSSize(width: 620, height: 650)
        window.contentView = web
        window.delegate = self
        window.center()
        let deviceFile = appDataFolder.appendingPathComponent("device.json")
        if !FileManager.default.fileExists(atPath: deviceFile.path) { show() }
        let center = NSWorkspace.shared.notificationCenter
        center.addObserver(self, selector: #selector(sleeping), name: NSWorkspace.willSleepNotification, object: nil)
        center.addObserver(self, selector: #selector(waking), name: NSWorkspace.didWakeNotification, object: nil)
        launchBackend()
    }

    func launchBackend() {
        do {
            bootFolder = FileManager.default.temporaryDirectory.appendingPathComponent("crowpanel-" + UUID().uuidString)
            try FileManager.default.createDirectory(at: bootFolder, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
            let boot = bootFolder.appendingPathComponent("boot.json")
            guard let resources = Bundle.main.resourceURL else { throw NSError(domain: "Companion", code: 1) }
            let backend = resources.appendingPathComponent("backend/CrowPanelBackend")
            let task = Process()
            task.executableURL = backend
            task.arguments = ["--boot-file", boot.path, "--parent-pid", String(ProcessInfo.processInfo.processIdentifier)]
            let folder = appDataFolder
            try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
            let logURL = folder.appendingPathComponent("app.log")
            FileManager.default.createFile(atPath: logURL.path, contents: Data(), attributes: [.posixPermissions: 0o600])
            logHandle = try FileHandle(forWritingTo: logURL)
            task.standardOutput = logHandle
            task.standardError = logHandle
            process = task
            try task.run()
            var attempts = 0
            startupTimer = Timer.scheduledTimer(withTimeInterval: 0.2, repeats: true) { [weak self] timer in
                guard let self = self else { timer.invalidate(); return }
                attempts += 1
                if let data = try? Data(contentsOf: boot), let payload = try? JSONSerialization.jsonObject(with: data) as? [String: Any], let text = payload["url"] as? String, let url = URL(string: text), url.host == "127.0.0.1" {
                    self.expectedHost = url.host
                    self.expectedPort = url.port
                    self.serviceURL = URL(string: "http://127.0.0.1:\(url.port!)")
                    self.sessionToken = url.fragment ?? ""
                    self.ready = true
                    self.web.load(URLRequest(url: url))
                    try? FileManager.default.removeItem(at: boot)
                    timer.invalidate()
                } else if attempts > 200 || !task.isRunning {
                    timer.invalidate()
                    self.failure("The companion could not start. Details are in Library/Application Support/CrowPanel Companion/app.log.")
                }
            }
        } catch { failure("The companion could not launch its bundled service. Rebuild or reinstall the app.") }
    }
    func failure(_ message: String) {
        let alert = NSAlert()
        alert.messageText = "CrowPanel Companion"
        alert.informativeText = message
        alert.runModal()
    }
    func visible(_ value: Bool) {
        web?.evaluateJavaScript("window.setCompanionVisible && window.setCompanionVisible(\(value ? "true" : "false"))", completionHandler: nil)
    }
    @objc func show() { window?.makeKeyAndOrderFront(nil); NSApplication.shared.activate(ignoringOtherApps: true); visible(true) }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { visible(window.isVisible && !window.isMiniaturized && !NSApp.isHidden) }
    func windowDidMiniaturize(_ notification: Notification) { visible(false) }
    func windowDidDeminiaturize(_ notification: Notification) { visible(true) }
    func applicationDidHide(_ notification: Notification) { visible(false) }
    func applicationDidUnhide(_ notification: Notification) { visible(window.isVisible && !window.isMiniaturized) }
    func request(_ path: String, post: Bool = false, completion: (([String: Any]) -> Void)? = nil) {
        guard let base = serviceURL else { return }
        var request = URLRequest(url: base.appendingPathComponent("api/" + path))
        request.timeoutInterval = 8
        request.setValue(sessionToken, forHTTPHeaderField: "X-CrowPanel-Token")
        if post {
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = Data("{}".utf8)
        }
        URLSession.shared.dataTask(with: request) { data, response, error in
            let payload = data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] } ?? [:]
            DispatchQueue.main.async {
                if post && ((response as? HTTPURLResponse)?.statusCode != 200) {
                    self.failure(payload["error"] as? String ?? "The action could not complete. Open settings and retry.")
                } else { completion?(payload) }
            }
        }.resume()
    }
    func menuWillOpen(_ menu: NSMenu) {
        startupItem.state = SMAppService.mainApp.status == .enabled ? .on : .off
        pauseItem.isEnabled = ready
        request("state") { payload in
            guard let device = payload["device"] as? [String: Any] else { return }
            self.paused = device["paused"] as? Bool ?? true
            self.pauseItem.title = self.paused ? "Resume connection" : "Pause connection"
            self.pauseItem.isEnabled = !(device["busy"] as? Bool ?? false)
            self.connectionItem.title = self.paused ? "Paused" : (device["label"] as? String ?? "Disconnected")
        }
    }
    @objc func togglePause() { request(paused ? "reconnect" : "disconnect", post: true) }
    @objc func toggleStartup() {
        do {
            if SMAppService.mainApp.status == .enabled { try SMAppService.mainApp.unregister() }
            else {
                try SMAppService.mainApp.register()
                if SMAppService.mainApp.status == .requiresApproval {
                    failure("Allow CrowPanel Companion in System Settings → General → Login Items, then enable Start at sign-in again.")
                    SMAppService.openSystemSettingsLoginItems()
                }
            }
            startupItem.state = SMAppService.mainApp.status == .enabled ? .on : .off
        } catch { failure("Could not change Start at sign-in. Move the app to Applications and check System Settings → General → Login Items.") }
    }
    @objc func sleeping() { request("suspend", post: true) }
    @objc func waking() { request("wake", post: true) }
    @objc func quit() { NSApplication.shared.terminate(nil) }
    func windowShouldClose(_ sender: NSWindow) -> Bool { visible(false); sender.orderOut(nil); return false }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool { show(); return true }
    func applicationWillTerminate(_ notification: Notification) {
        startupTimer?.invalidate()
        if process?.isRunning == true { process?.terminate() }
        if let folder = bootFolder { try? FileManager.default.removeItem(at: folder) }
        try? logHandle?.close()
    }
    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else { decisionHandler(.cancel); return }
        if url.scheme == "blob" { decisionHandler(.download); return }
        if url.host == expectedHost && url.port == expectedPort && url.scheme == "http" {
            decisionHandler(navigationAction.shouldPerformDownload ? .download : .allow)
        } else { if url.scheme == "https" { NSWorkspace.shared.open(url) }; decisionHandler(.cancel) }
    }
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = navigationAction.request.url, url.scheme == "https" { NSWorkspace.shared.open(url) }
        return nil
    }
    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel(); panel.allowsMultipleSelection = false; panel.canChooseDirectories = false
        panel.beginSheetModal(for: window) { response in completionHandler(response == .OK ? panel.urls : nil) }
    }
    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) { download.delegate = self }
    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) { download.delegate = self }
    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
        let panel = NSSavePanel(); panel.nameFieldStringValue = "My-CrowPanel.json"
        panel.beginSheetModal(for: window) { result in completionHandler(result == .OK ? panel.url : nil) }
    }
}
let app = NSApplication.shared
let delegate = Companion()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
