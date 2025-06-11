#!/usr/bin/env python3
"""
Convert Markdown CV to PDF using WeasyPrint.
"""
import os
import sys
import markdown
from weasyprint import HTML

def convert_md_to_pdf(md_path, pdf_path=None):
    """
    Convert a Markdown file to PDF.
    
    Args:
        md_path (str): Path to the input Markdown file
        pdf_path (str, optional): Path to save the output PDF. If not provided,
                                will use the same name as input with .pdf extension
    """
    # Set default output path if not provided
    if pdf_path is None:
        pdf_path = os.path.splitext(md_path)[0] + '.pdf'
    
    try:
        # Read the Markdown file
        with open(md_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
        
        # Convert Markdown to HTML
        html_content = markdown.markdown(md_content)
        
        # Add basic CSS for better PDF styling
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    margin: 40px;
                    color: #333;
                }}
                h1, h2, h3 {{
                    color: #2c3e50;
                    border-bottom: 1px solid #eee;
                    padding-bottom: 5px;
                }}
                h1 {{ font-size: 24px; }}
                h2 {{ font-size: 20px; }}
                h3 {{ font-size: 18px; }}
                a {{ color: #3498db; text-decoration: none; }}
                ul, ol {{ margin: 10px 0; padding-left: 25px; }}
                li {{ margin: 5px 0; }}
                .section {{ margin-bottom: 20px; }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
        
        # Convert HTML to PDF
        HTML(string=html).write_pdf(pdf_path)
        print(f"Successfully converted {md_path} to {pdf_path}")
        
    except FileNotFoundError:
        print(f"Error: File not found: {md_path}")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python convert_cv.py <input.md> [output.pdf]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    convert_md_to_pdf(input_file, output_file)
