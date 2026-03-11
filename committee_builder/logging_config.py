"""Logging setup for the committee CLI."""

from __future__ import annotations

import logging


def configure_logging(verbosity: int) -> None:
    """Configure root logging level from -v flags."""
    if verbosity <= 0:
        level = logging.WARNING
    elif verbosity == 1:
        level = logging.INFO
    else:
        level = logging.DEBUG

    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
