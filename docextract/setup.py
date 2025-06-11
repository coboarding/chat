from setuptools import setup, find_packages

setup(
    name="docextract",
    version="0.1.0",
    description="Advanced document data extraction with multiple LLM support",
    author="coBoarding Team",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.95.0",
        "uvicorn>=0.21.0",
        "python-dotenv>=1.0.0",
        "pydantic>=2.0.0",
        "click>=8.1.3",
        "PyPDF2>=3.0.0",
        "python-docx>=0.8.11",
        "pytesseract>=0.3.10",
        "Pillow>=9.5.0",
        "ollama>=0.1.0",
        "spacy>=3.6.0",
        "httpx>=0.24.0",
        "typer>=0.9.0",
        "rich>=13.4.0",
    ],
    entry_points={
        "console_scripts": [
            "docextract=docextract.cli.main:app",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
)
