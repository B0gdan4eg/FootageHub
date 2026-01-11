"""
Downloaders for MediaBot - Envato, Freepik, Motion Array

This module provides wrapper classes for existing download utilities.
All actual download logic remains in envato_utils/ and freepik_utils/
to maintain compatibility and avoid breaking existing functionality.
"""

from .base import AbstractDownloader
from .envato import EnvatoDownloader
from .freepik import FreepikDownloader
from .motion import MotionDownloader

__all__ = [
    "AbstractDownloader",
    "EnvatoDownloader",
    "FreepikDownloader",
    "MotionDownloader",
]
