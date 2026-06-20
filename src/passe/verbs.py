"""Canonical verb facade for the passe DSL — and the test patch surface.

The verb *implementations* live in four modules: ``verbs_navigation``,
``verbs_interaction``, ``verbs_observation``, ``verbs_control``. This module
re-exports all of them under one name, ``passe.verbs``, which is load-bearing
in two ways:

1. **Single import surface.** ``runner`` (the dispatch loop), ``cli``, and
   ``commands`` import every verb from here rather than chasing four modules.
2. **Test patch point.** Tests patch ``passe.verbs.do_X`` to stub a verb, and
   ``do_watch`` deliberately late-binds ``passe.verbs.do_screenshot`` so that
   patch takes effect (see ``verbs_observation.do_watch``). CLAUDE.md documents
   this contract: patch ``passe.runner.do_X`` when mocking inside
   ``run_script``, ``passe.verbs.do_X`` when mocking inside another verb.

**Do not delete.** This is public API, not transitional scaffolding. The
earlier ``from x import *`` wildcards were replaced with the explicit
re-exports below so the facade's contract is legible — every name
``passe.verbs`` exposes is named here.
"""

from passe.verbs_navigation import (  # noqa: F401
    do_navigate, do_back, do_forward, do_wait_idle,
)
from passe.verbs_interaction import (  # noqa: F401
    do_click, do_click_text, do_fill, do_type, do_select,
    do_press, do_hover, do_tap, do_swipe, do_scroll,
)
from passe.verbs_observation import (  # noqa: F401
    do_screenshot, do_snapshot, do_read, do_fetch,
    do_exists, do_count, do_visible, do_pdf,
    do_eval, do_eval_to, do_eval_file, do_eval_file_to,
    do_assert, do_watch,
    do_ax_tree, do_ax_find, do_ax_node,
)
from passe.verbs_control import (  # noqa: F401
    do_wait_for, do_wait_stable, do_frame, do_device, do_viewport,
)

# Non-verb names that are part of the facade contract — imported via
# passe.verbs by cli/fastpath, or referenced in tests. Kept explicit alongside
# the verbs so the full surface is in one place.
from passe.verbs_observation import (  # noqa: F401
    _check_thin_read, _render_apple_json,
    THIN_READ_THRESHOLD, AUTH_PATTERNS, RAW_CONTENT_TYPES,
)
