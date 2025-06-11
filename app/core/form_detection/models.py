"""Models for form detection module."""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple

@dataclass
class FormField:
    """Represents a detected form field"""
    element_id: str
    field_type: str  # text, email, file, select, textarea, etc.
    label: str
    placeholder: str
    required: bool
    coordinates: Tuple[int, int, int, int]  # x, y, width, height
    css_selector: str
    xpath: str
    confidence: float

class DetectionMethod(Enum):
    """Form detection methods"""
    DOM_ANALYSIS = "dom"
    VISUAL_DETECTION = "visual" 
    TAB_NAVIGATION = "tab"
    HYBRID = "hybrid"
