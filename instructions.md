# Passe — Instruction Shard

Auto-loaded via `~/.claude/rules/passe.md`.

## Overrides

| Your Default | What I Need |
|-------------|-------------|
| WebFetch (summaries) | `passe fetch` for web content. Never WebFetch — summaries miss nuance. |
| `open URL` | `browse URL` (Chrome Passe) for quick inspection. |

## Chrome Passe

- Profile: `~/.chrome-passe`, CDP port 9222
- Launched via `~/Applications/Chrome Passe.app`
- Authenticated pages: `webctl` with default profile
- Browser automation: `passe` (CDP CLI). Compound ops in one Bash call.
- **Connection trouble?** Run `passe status` first — it reports structured diagnostics. Don't say "passe is broken" — diagnose the connection.
