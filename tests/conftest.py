"""Pytest configuration and fixtures."""
import os
import pytest
from pathlib import Path

# Add the project root to PYTHONPATH
project_root = Path(__file__).parent.parent
os.environ['PYTHONPATH'] = str(project_root)

@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment."""
    # Set up any test environment variables here
    os.environ['ENV'] = 'test'
    
    # Create necessary test directories
    test_dirs = [
        project_root / 'uploads',
        project_root / 'downloads',
        project_root / 'logs'
    ]
    
    for dir_path in test_dirs:
        dir_path.mkdir(exist_ok=True)
    
    yield  # Test runs here
    
    # Cleanup after tests if needed
    # Remove test files, etc.
