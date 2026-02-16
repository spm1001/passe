"""Device presets for mobile/tablet emulation.

Each preset maps to CDP calls:
  Emulation.setDeviceMetricsOverride  — viewport, DPR, mobile flag
  Emulation.setUserAgentOverride      — UA string, platform
  Emulation.setTouchEmulationEnabled  — touch events, maxTouchPoints
  Emulation.setSafeAreaInsetsOverride  — notch/dynamic island insets

Presets are intentionally hardcoded, not loaded from config.
Add new devices here; keep the dict flat.
"""

DEVICES: dict[str, dict] = {
    "iPhone 14 Pro": {
        "width": 393, "height": 852, "deviceScaleFactor": 3,
        "mobile": True, "touch": True, "maxTouchPoints": 5,
        "userAgent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
            "Mobile/15E148 Safari/604.1"
        ),
        "platform": "iPhone",
        "orientation": {"type": "portraitPrimary", "angle": 0},
        "safeArea": {"top": 59, "left": 0, "bottom": 34, "right": 0},
    },
    "iPhone SE": {
        "width": 375, "height": 667, "deviceScaleFactor": 2,
        "mobile": True, "touch": True, "maxTouchPoints": 5,
        "userAgent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
            "Mobile/15E148 Safari/604.1"
        ),
        "platform": "iPhone",
        "orientation": {"type": "portraitPrimary", "angle": 0},
        "safeArea": {"top": 20, "left": 0, "bottom": 0, "right": 0},
    },
    "Pixel 7": {
        "width": 412, "height": 915, "deviceScaleFactor": 2.625,
        "mobile": True, "touch": True, "maxTouchPoints": 5,
        "userAgent": (
            "Mozilla/5.0 (Linux; Android 14; Pixel 7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 "
            "Mobile Safari/537.36"
        ),
        "platform": "Linux armv8l",
        "orientation": {"type": "portraitPrimary", "angle": 0},
        "safeArea": {"top": 0, "left": 0, "bottom": 0, "right": 0},
    },
    "iPad Air": {
        "width": 820, "height": 1180, "deviceScaleFactor": 2,
        "mobile": True, "touch": True, "maxTouchPoints": 5,
        "userAgent": (
            "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
            "Mobile/15E148 Safari/604.1"
        ),
        "platform": "iPad",
        "orientation": {"type": "portraitPrimary", "angle": 0},
        "safeArea": {"top": 24, "left": 0, "bottom": 20, "right": 0},
    },
    "iPad Pro 11": {
        "width": 834, "height": 1194, "deviceScaleFactor": 2,
        "mobile": True, "touch": True, "maxTouchPoints": 5,
        "userAgent": (
            "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
            "Mobile/15E148 Safari/604.1"
        ),
        "platform": "iPad",
        "orientation": {"type": "portraitPrimary", "angle": 0},
        "safeArea": {"top": 24, "left": 0, "bottom": 20, "right": 0},
    },
    "Desktop 1080p": {
        "width": 1920, "height": 1080, "deviceScaleFactor": 1,
        "mobile": False, "touch": False, "maxTouchPoints": 0,
        "userAgent": "",  # empty = use Chrome's default
        "platform": "",
        "orientation": {"type": "landscapePrimary", "angle": 90},
        "safeArea": None,
    },
}

# Case-insensitive lookup
_DEVICES_LOWER = {k.lower(): k for k in DEVICES}


def get_device(name: str) -> dict:
    """Look up device preset by name (case-insensitive). Raises KeyError on miss."""
    key = _DEVICES_LOWER.get(name.lower())
    if key is None:
        available = ', '.join(DEVICES.keys())
        raise KeyError(f'Unknown device: {name!r}. Available: {available}')
    return DEVICES[key]
