import sys
from unittest.mock import MagicMock

# Mock sounddevice before it's imported
sys.modules['sounddevice'] = MagicMock()
sys.modules['soundfile'] = MagicMock()