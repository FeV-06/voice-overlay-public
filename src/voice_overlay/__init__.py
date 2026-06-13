from __future__ import annotations

import sys

if sys.version_info < (3, 10):
    sys.exit("VoiceOverlay requires Python 3.10 or higher. You have Python {}.{}.".format(*sys.version_info[:2]))
