"""Form detection module for detecting and interacting with web forms."""

from .models import FormField, DetectionMethod
from .detector import FormDetector
from .automation import AutomationEngine

__all__ = ['FormField', 'DetectionMethod', 'FormDetector', 'AutomationEngine']
