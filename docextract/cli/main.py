"""
CLI shell for document extraction
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from docextract.core.processor import DocumentProcessor
from docextract.utils.config import Config, ExtractionMethod

# Create Typer app
app = typer.Typer(
    name="docextract",
    help="Extract data from documents using multiple LLM models",
    add_completion=False,
)

# Create console for rich output
console = Console()


@app.command("extract")
def extract(
    file_path: List[Path] = typer.Argument(
        ...,
        help="Path to document file(s)",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    method: str = typer.Option(
        None,
        "--method",
        "-m",
        help="Extraction method to use",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (JSON)",
    ),
    pretty: bool = typer.Option(
        False,
        "--pretty",
        "-p",
        help="Pretty print output",
    ),
):
    """Extract data from document(s)"""
    # Validate extraction method
    extraction_method = None
    if method:
        try:
            extraction_method = ExtractionMethod(method)
        except ValueError:
            console.print(f"[bold red]Error:[/] Invalid extraction method: {method}")
            console.print(f"Available methods: {[m.value for m in ExtractionMethod]}")
            sys.exit(1)
    
    # Create document processor
    processor = DocumentProcessor(extraction_method)
    
    # Process files
    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task("Processing documents...", total=len(file_path))
        
        for path in file_path:
            progress.update(task, description=f"Processing {path.name}...")
            
            # Run extraction
            result = asyncio.run(processor.process_file(path))
            
            # Add result
            results.append({
                "file": str(path),
                "method": processor.extraction_method.value,
                "data": result,
            })
            
            progress.update(task, advance=1)
    
    # Print results
    if len(results) == 1:
        # Single file result
        result = results[0]
        console.print(Panel(f"[bold green]Extraction complete:[/] {result['file']}"))
        console.print(f"Method: [bold]{result['method']}[/]")
        
        # Print data
        if pretty:
            import json
            console.print_json(json.dumps(result["data"]))
        else:
            table = Table(title="Extracted Data")
            table.add_column("Field", style="cyan")
            table.add_column("Value", style="green")
            
            for key, value in result["data"].items():
                table.add_row(key, str(value))
            
            console.print(table)
    else:
        # Multiple file results
        console.print(Panel(f"[bold green]Extraction complete:[/] {len(results)} files"))
        
        table = Table(title="Extraction Results")
        table.add_column("File", style="cyan")
        table.add_column("Method", style="green")
        table.add_column("Fields", style="yellow")
        
        for result in results:
            table.add_row(
                Path(result["file"]).name,
                result["method"],
                ", ".join(result["data"].keys()),
            )
        
        console.print(table)
    
    # Save to output file if specified
    if output:
        import json
        with open(output, "w") as f:
            json.dump(results, f, indent=2 if pretty else None)
        console.print(f"[bold green]Results saved to:[/] {output}")


@app.command("methods")
def list_methods():
    """List available extraction methods"""
    table = Table(title="Available Extraction Methods")
    table.add_column("Method", style="cyan")
    table.add_column("Description", style="green")
    table.add_column("Default", style="yellow")
    
    for method in ExtractionMethod:
        table.add_row(
            method.value,
            get_method_description(method),
            "✓" if method == Config.EXTRACTION_METHOD else "",
        )
    
    console.print(table)


@app.command("config")
def show_config():
    """Show current configuration"""
    config = Config.to_dict()
    
    table = Table(title="Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    
    for key, value in config.items():
        table.add_row(key, str(value))
    
    console.print(table)


@app.command("serve")
def serve(
    host: str = typer.Option(
        Config.API_HOST,
        "--host",
        "-h",
        help="API host",
    ),
    port: int = typer.Option(
        Config.API_PORT,
        "--port",
        "-p",
        help="API port",
    ),
    debug: bool = typer.Option(
        Config.DEBUG,
        "--debug",
        "-d",
        help="Enable debug mode",
    ),
):
    """Start the API server"""
    from docextract.api.main import start_api
    
    # Update config
    Config.API_HOST = host
    Config.API_PORT = port
    Config.DEBUG = debug
    
    console.print(f"[bold green]Starting API server:[/] http://{host}:{port}")
    start_api()


def get_method_description(method: ExtractionMethod) -> str:
    """Get description for extraction method"""
    descriptions = {
        ExtractionMethod.MISTRAL: "Mistral LLM text extraction",
        ExtractionMethod.LLAVA: "LLaVA visual language model extraction",
        ExtractionMethod.LLAVA_NEXT: "LLaVA Next visual language model extraction",
        ExtractionMethod.QWEN: "Qwen LLM text extraction",
        ExtractionMethod.SPACY: "spaCy NER extraction",
        ExtractionMethod.OCR: "OCR-based extraction",
        ExtractionMethod.HYBRID: "Hybrid extraction using multiple methods",
    }
    return descriptions.get(method, "Unknown method")


if __name__ == "__main__":
    app()
