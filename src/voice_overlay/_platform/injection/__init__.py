from __future__ import annotations

import sys

if sys.platform == "linux":
    from voice_overlay._platform.injection.linux import UinputInjector as TextInjectorBackend
elif sys.platform == "win32":
    from voice_overlay._platform.injection.windows import WindowsInjector as TextInjectorBackend
