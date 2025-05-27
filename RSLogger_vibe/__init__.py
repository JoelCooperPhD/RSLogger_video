"""
RSLogger VIBE - Unified Video, Audio, and Behavioral Recording System

A modular recording system for research applications that combines:
- Audio recording capabilities
- Video recording capabilities  
- Web-based user interface
- Extensible sensor architecture
"""

__version__ = "1.0.0"
__author__ = "Joel Cooper"

from . import sensors
from . import ui

__all__ = ["sensors", "ui"]