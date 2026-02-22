import Cocoa

// ---------------------------------------------------------------------------
// Chrome Debug — native macOS launcher
//
// Replaces launch.sh as CFBundleExecutable. Handles Apple Events that bash
// can't receive: openFiles (Finder double-click) and kAEGetURL (link clicks
// from other apps). Launches Chrome with debug flags on first run, hands off
// URLs via Chrome's singleton mechanism on re-entry, quits when Chrome exits.
// ---------------------------------------------------------------------------

class ChromeDebugDelegate: NSObject, NSApplicationDelegate {

    static let chrome  = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    static let profile = NSHomeDirectory() + "/.chrome-debug"
    static let lock    = profile + "/SingletonLock"

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
            launchChrome(extraArgs: [])
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
        let urls = filenames.map { "file://\($0)" }
        openURLs(urls)
        sender.reply(toOpenOrPrint: .success)
    }

    /// URL scheme dispatch (http/https clicked in another app).
    @objc func handleGetURL(_ event: NSAppleEventDescriptor,
                            withReply reply: NSAppleEventDescriptor) {
        guard let url = event.paramDescriptor(forKeyword: keyDirectObject)?.stringValue
        else { return }
        openURLs([url])
    }

    // MARK: - Chrome management

    private func openURLs(_ urls: [String]) {
        if chromeIsRunning() || launchedByUs {
            // Chrome is alive (or we just launched it and the lock isn't
            // established yet). Hand off via singleton — Chrome's own IPC
            // delivers the URLs to the running instance.
            for url in urls {
                runChrome(args: ["--user-data-dir=\(Self.profile)", url])
            }
        } else {
            // Nobody started Chrome yet — do a full launch with the URLs.
            launchChrome(extraArgs: urls)
        }
    }

    private func launchChrome(extraArgs: [String]) {
        var args = [
            "--remote-debugging-port=9222",
            "--remote-debugging-address=0.0.0.0",
            "--remote-allow-origins=*",
            "--user-data-dir=\(Self.profile)",
            "--no-default-browser-check",
        ]
        args += extraArgs
        runChrome(args: args)
        launchedByUs = true
    }

    private func runChrome(args: [String]) {
        // Launch Chrome via bash, not Process() directly. When Process()
        // spawns Chrome from an NSApplication, macOS gives Chrome its own
        // dock icon ("Google Chrome") alongside ours. Bash's fork/exec
        // keeps Chrome grouped under Chrome Debug.app's process identity —
        // one dock icon, correct name.
        let quoted = args.map { "'\($0)'" }.joined(separator: " ")
        let cmd = "'\(Self.chrome)' \(quoted) &"
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/bin/bash")
        task.arguments = ["-c", cmd]
        task.standardOutput = FileHandle.nullDevice
        task.standardError = FileHandle.nullDevice
        try? task.run()
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
let delegate = ChromeDebugDelegate()
app.delegate = delegate
app.run()
