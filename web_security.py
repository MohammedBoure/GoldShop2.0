"""Compatibility alias for the organized web security module."""

import sys

from web import security as _security


sys.modules[__name__] = _security
