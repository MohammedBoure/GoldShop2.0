"""Compatibility alias for the organized DuckDNS service."""

import sys

from services import duckdns as _duckdns


sys.modules[__name__] = _duckdns
