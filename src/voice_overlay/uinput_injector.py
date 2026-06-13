from __future__ import annotations

import sys

from voice_overlay._platform import PlatformBackendError

if sys.platform == "linux":
    from voice_overlay._platform.injection.linux import UinputInjector
else:
    class UinputInjector:
        def __init__(self, *args, **kwargs):
            raise PlatformBackendError("UinputInjector is Linux-only")
