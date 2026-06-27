# Passe — Instruction Shard

Auto-loaded via `~/.claude/rules/passe.md`.

## Overrides

| Your Default | What I Need |
|-------------|-------------|
| WebFetch (summaries) | `passe fetch` for web content. Never WebFetch — summaries miss nuance. |
| `open URL` | `browse URL` for quick inspection (opens in the appliance Chrome). |

## The browser Passe drives = the kube appliance

There is **no local Chrome Passe** any more — the Mac `~/.chrome-passe` + `Chrome Passe.app`
and the old Hezza Xvfb appliance are both retired (2026-06-27). Passe drives a real,
logged-in Chrome on **kube**: the `passe-partout` appliance (NVIDIA GPU, home residential
egress, persistent logins).

- **`localhost:9222` IS the kube appliance, on every CC machine.** A `passe-kube-tunnel`
  unit (systemd-user on hezza, launchd on the Mac) holds `ssh -N -L 9222:localhost:9222
  kube`, so passe's default CDP endpoint already reaches kube. **Don't set `PASSE_CDP`** —
  the default (`http://localhost:9222`) is correct everywhere.
- **Authenticated / gated pages**: just `passe fetch` or `goto` — the appliance Chrome
  already holds the logins (claude.ai, Medium, …). Profile/login state lives on kube.
- **Connection trouble?** Run `passe status` first (reports `cdp_endpoint` / `reachable` /
  `chrome_version`). If `localhost:9222` is unreachable, the `passe-kube-tunnel` unit is
  probably down — check/restart it; don't say "passe is broken."
- Browser automation: `passe` (CDP CLI). Compound ops in one Bash call.

**To change what the browser is logged into, or where it runs → the `passe-partout` repo**
(the appliance is config there — systemd units + a logged-in profile + the tunnel — not
code here). A fresh CC machine needs the `passe-kube-tunnel` installed; see `passe-partout`
`deploy/` (`deploy/hezza/install.sh` for hezza; the launchd agent pattern for a Mac).
