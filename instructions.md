# Passe — Instruction Shard

Auto-loaded via `~/.claude/rules/passe.md`.

## Overrides

| Your Default | What I Need |
|-------------|-------------|
| WebFetch (summaries) | `passe fetch` for web content. Never WebFetch — summaries miss nuance. |
| `open URL` | `browse URL` for quick inspection (opens in the backend Chrome — see below). |

## The browser Passe drives — TWO backends since 2026-07-21

There is **no local Chrome Passe** any more — the Mac `~/.chrome-passe` + `Chrome Passe.app`
and the old Hezza Xvfb appliance are both retired (2026-06-27). Passe drives one of **two**
real, logged-in Chromes. **Which one is host-dependent, so do not assume the default.**

> **Corrected 2026-07-26.** This section previously said "`localhost:9222` IS the kube
> appliance, on every CC machine" and "**Don't set `PASSE_CDP`**". Both became wrong when tube
> got its own browser, and the stale version survived here for five days — long enough to
> also produce a wrong row in `~/.claude/context/traps.md` and a self-contradiction in
> `infra/CLAUDE.md`. If you are reading a claim about which port is live, **check it** with
> the command below rather than trusting this file.

- **tube — its own session Chrome, and tube's default.** `passe-chrome.service` (user unit)
  runs Chrome in tube's *persistent xrdp session* on **CDP `localhost:9223`**, profile
  `~/chrome-profiles/passe`, carrying Sameer's own Google logins. `PASSE_CDP=http://localhost:9223`
  is **tube-guarded in dotfiles `shell/bashrc`**, so a plain `passe` on tube hits this one.
  Watchable by just RDPing in. Unit + installer: `passe-partout` `deploy/tube/`.
- **kube — the fingerprint specialist.** The `passe-partout` appliance (NVIDIA GPU WebGL,
  persistent site logins). Reached via the `passe-kube-tunnel` systemd-user unit
  (`ssh -N -L 9222:localhost:9222 kube`), which runs on **tube and hezza**. From tube, ask for
  it explicitly: `passe --cdp http://localhost:9222`. On hezza it is the default.
- **The Mac has no passe at all** as of 2026-07-26: no launchd agent, nothing listening on
  9222 or 9223, `passe status` → `reachable=False`, connection refused. `rules/passe.md` and
  the passe plugin cache were removed there. So none of the above applies on a Mac — don't go
  hunting for units that aren't installed. *(Measured by a Mac session, not from this host.)*
- Endpoint values **require the `http://` scheme** — bare `--cdp localhost:9222` fails.
- **Authenticated / gated pages**: just `passe fetch` or `goto` — whichever backend you reach
  already holds the logins. Profile state lives with that backend, not here.

### Connection trouble — check the unit before blaming passe

Run `passe status` first (reports `cdp_endpoint` / `reachable` / `chrome_version`). Then:

```bash
systemctl --user is-active passe-chrome passe-kube-tunnel   # which backend is even up?
ss -ltnp | grep 922                                          # what is actually listening
```

**`:9223` is session-scoped — it is up *exactly* when tube's xrdp session is up.** The unit
deliberately carries no `[Install]`/`WantedBy`; `rdp.xsession` starts it, same pattern as
`claude-desktop`. So `static` in `systemctl is-enabled` does **not** mean broken, and a port
that was live an hour ago and is gone now usually means the X session died, not a
misconfiguration. If the whole session-scoped set is absent together, that co-absence is the tell.

**A clean Chrome exit self-heals since 2026-07-26 evening** (`Restart=always` + 60s/5 start
limit, infra iw-rogopo — this paragraph previously documented the opposite: clean exits used to
vanish silently, and did, twice that day). A closed window or tidy self-exit now relaunches in
~3s; a *deliberate* stop is `systemctl --user stop passe-chrome`, which systemd honours. So if
`:9223` is absent for more than a few seconds, the causes left are: the X session died (check
the co-absence tell above), the unit was deliberately stopped (`is-active` → `inactive`), or the
start limit tripped after a dead-display relaunch loop (`is-active` → `failed`, and a
status-email alert has already fired — the limit self-clears after 60s, so a plain
`systemctl --user restart passe-chrome` recovers it once the display is back).

- Browser automation: `passe` (CDP CLI). Compound ops in one Bash call.

**To change what the browser is logged into, or where it runs → the `passe-partout` repo**
(the appliance is config there — systemd units + a logged-in profile + the tunnel — not
code here). A fresh CC machine needs the `passe-kube-tunnel` installed; see `passe-partout`
`deploy/` (`deploy/hezza/install.sh` for hezza; the launchd agent pattern for a Mac).
