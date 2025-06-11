"""Pytest configuration and fixtures."""
import os
import sys
import asyncio
import pytest
import tempfile
import shutil
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import MagicMock, patch

# Add the project root to PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set environment variables
os.environ['ENV'] = 'test'
os.environ['PYTHONUNBUFFERED'] = '1'
os.environ['PYTHONPATH'] = str(project_root)

# Test database configuration
os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'
os.environ['TESTING'] = 'true'

# Mock external services
os.environ['OLLAMA_API_BASE'] = 'http://localhost:11434'
os.environ['REDIS_URL'] = 'redis://localhost:6379/0'

# Create a temporary directory for test files
@pytest.fixture(scope='session')
def temp_dir():
    """Create a temporary directory for test files."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture(autouse=True)
def setup_test_environment(temp_dir: Path):
    """Setup test environment."""
    # Create necessary test directories
    test_dirs = [
        temp_dir / 'uploads',
        temp_dir / 'downloads',
        temp_dir / 'logs',
        temp_dir / 'cache'
    ]
    
    for dir_path in test_dirs:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    # Set environment variables for test directories
    os.environ['UPLOAD_FOLDER'] = str(temp_dir / 'uploads')
    os.environ['DOWNLOAD_FOLDER'] = str(temp_dir / 'downloads')
    os.environ['LOG_DIR'] = str(temp_dir / 'logs')
    os.environ['CACHE_DIR'] = str(temp_dir / 'cache')
    
    yield  # Test runs here
    
    # Cleanup after tests
    for dir_path in test_dirs:
        shutil.rmtree(dir_path, ignore_errors=True)

# Async test support
@pytest.fixture(scope='session')
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

# Database session fixture
@pytest.fixture
async def db_session():
    """Create a database session for testing."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.database.models import Base
    
    engine = create_async_engine(os.environ['DATABASE_URL'])
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

# Mock Ollama client
@pytest.fixture
def mock_ollama():
    """Mock Ollama client."""
    with patch('app.core.cv_processor.ollama.Client') as mock:
        yield mock

# Mock Redis client
@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    with patch('app.core.cache.redis.Redis') as mock:
        yield mock

# Sample test data
@pytest.fixture
def sample_cv_text():
    """Return sample CV text for testing."""
    return """
    John Doe
    Senior Software Engineer
    
    Skills:
    - Python, Docker, Kubernetes, AWS, FastAPI, SQL
    
    Experience:
    - Senior Software Engineer at Tech Corp (2020-Present)
    - Software Engineer at Dev Solutions (2018-2020)
    
    Education:
    - BSc in Computer Science, University of Tech (2014-2018)
    """
