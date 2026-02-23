import Cocoa

// ---------------------------------------------------------------------------
// Chrome Passe — native macOS launcher
//
// Replaces the bash wrapper as CFBundleExecutable. Handles Apple Events that
// bash can't receive: openFiles (Finder double-click) and kAEGetURL (link
// clicks from other apps). Launches Chrome via NSWorkspace so it gets its own
// TCC coalition (microphone, camera, etc. all work). Quits when Chrome exits.
// ---------------------------------------------------------------------------

class ChromePasseDelegate: NSObject, NSApplicationDelegate {

    static let chromeApp = URL(fileURLWithPath: "/Applications/Google Chrome.app")
    static let profile   = NSHomeDirectory() + "/.chrome-passe"
    static let lock      = profile + "/SingletonLock"

    /// True once we've launched Chrome ourselves (distinguishes "Chrome was
    /// already running when we started" from "we started Chrome").
    private var launchedByUs = false

    // MARK: - Lifecycle

    func applicationWillFinishLaunching(_ notification: Notification) {
        // Register URL scheme handler BEFORE didFinishLaunching —
        // otherwise the first URL event is lost.
        NSAppleEventManager.shared().setEventHandler(
            self,
            andSelector: #selector(handleGetURL(_:withReply:)),
            forEventClass: AEEventClass(kInternetEventClass),
            andEventID: AEEventID(kAEGetURL)
        )
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        if !chromeIsRunning() {
            launchChrome(urls: [])
        }

        // Poll: quit when Chrome exits so the dock icon disappears.
        Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] timer in
            guard let self else { timer.invalidate(); return }
            if self.launchedByUs && !self.chromeIsRunning() {
                NSApp.terminate(nil)
            }
        }
    }

    /// Dock click → bring Chrome to front (we have no windows of our own).
    func applicationShouldHandleReopen(_ sender: NSApplication,
                                       hasVisibleWindows flag: Bool) -> Bool {
        activateChrome()
        return false
    }

    // MARK: - Apple Event handlers

    /// Finder double-click / "Open With" — may receive multiple files at once.
    func application(_ sender: NSApplication, openFiles filenames: [String]) {
        let urls = filenames.compactMap { URL(string: "file://\($0)") }
        openURLs(urls)
        sender.reply(toOpenOrPrint: .success)
    }

    /// URL scheme dispatch (http/https clicked in another app).
    @objc func handleGetURL(_ event: NSAppleEventDescriptor,
                            withReply reply: NSAppleEventDescriptor) {
        guard let urlString = event.paramDescriptor(forKeyword: keyDirectObject)?.stringValue,
              let url = URL(string: urlString)
        else { return }
        openURLs([url])
    }

    // MARK: - Chrome management

    private func openURLs(_ urls: [URL]) {
        if chromeIsRunning() || launchedByUs {
            // Chrome is alive (or we just launched it and the lock isn't
            // established yet). Open URLs in the running Chrome instance.
            if urls.isEmpty { return }
            let config = NSWorkspace.OpenConfiguration()
            config.arguments = ["--user-data-dir=\(Self.profile)"]
            NSWorkspace.shared.open(
                urls,
                withApplicationAt: Self.chromeApp,
                configuration: config
            )
        } else {
            // Nobody started Chrome yet — do a full launch with the URLs.
            launchChrome(urls: urls)
        }
    }

    private func launchChrome(urls: [URL]) {
        // Launch Chrome via NSWorkspace — Chrome gets its own TCC coalition
        // so microphone, camera, screen recording, etc. all work without
        // needing usage descriptions in Chrome Passe's Info.plist.
        let config = NSWorkspace.OpenConfiguration()
        config.arguments = [
            "--remote-debugging-port=9222",
            "--remote-allow-origins=*",
            "--user-data-dir=\(Self.profile)",
            "--no-default-browser-check",
        ]

        if urls.isEmpty {
            NSWorkspace.shared.openApplication(
                at: Self.chromeApp,
                configuration: config
            )
        } else {
            NSWorkspace.shared.open(
                urls,
                withApplicationAt: Self.chromeApp,
                configuration: config
            )
        }
        launchedByUs = true
    }

    /// Bring Chrome's window to front by PID from SingletonLock.
    private func activateChrome() {
        guard let pid = chromePID() else { return }
        if let app = NSRunningApplication(processIdentifier: pid) {
            app.activate(options: .activateIgnoringOtherApps)
        }
    }

    // MARK: - SingletonLock

    private func chromeIsRunning() -> Bool {
        guard let pid = chromePID() else { return false }
        return kill(pid, 0) == 0
    }

    /// Extract PID from SingletonLock symlink (e.g. "Mac-87417" → 87417).
    private func chromePID() -> pid_t? {
        guard let target = try? FileManager.default
                .destinationOfSymbolicLink(atPath: Self.lock),
              let suffix = target.split(separator: "-").last,
              let pid = pid_t(suffix)
        else { return nil }
        return pid
    }
}

// MARK: - Entry point

let app = NSApplication.shared
let delegate = ChromePasseDelegate()
app.delegate = delegate
app.run()
