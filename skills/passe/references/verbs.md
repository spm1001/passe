# Verb Reference

**Extraction:**
`fetch <url> [--source S] [path]` — goto + auto-wait + read (compound). `extract [--source S] [--no-wait] [path]` — extract current page (`read` is alias). Sources: `trafilatura` (default), `readability`, `innertext`, `raw`.

**Navigation:**
`goto <url>`, `back`, `forward`, `scroll <x> <y>`

**Interaction:**
`click <sel-or-text-or-ref>`, `type <sel-or-ref> <text>`, `fill <sel> <val>`, `select <sel> <val>`, `press <key>`, `hover <sel-or-ref>`, `tap <sel>`, `swipe <sel> <dir> [dist]`. Refs (`e1`, `e3`...) come from `ax-tree --flat-refs`, work across invocations (scout with `--keep-tab`, act with `--reuse-tab`), and clear on navigation.

**Observation:**
`screenshot [--fast] [--viewport] [--format F] [--quality N] [path]`, `snapshot [path]`, `eval <expr>`, `eval-to <path> <expr>`, `eval-file <js>`, `eval-file-to <out> <js>`, `ax-tree [--depth N] [--compact] [--flat-refs]`, `ax-find [--role R] [--name N]`, `ax-node <selector>`, `exists <sel>`, `count <sel>`, `visible <sel>`, `pdf [path]`

**Network:**
`capture [--bodies] [--filter] <path>`

**Control:**
`wait` (bare=network idle, `<n>`=sleep, `<sel>`=element), `wait-for <sel>`, `wait-idle`, `watch [--fast] [--cooldown N] <path>`, `assert <expr>`, `log <msg>`, `frame <url-pattern>`, `frame top`, `bring-to-front`

**Emulation:**
`device <name> [--dpr N]`, `viewport <w> <h>`
