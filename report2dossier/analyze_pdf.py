import argparse
from pathlib import Path
from pdf_analyzer import DocumentAnalyzer

def main():
    parser = argparse.ArgumentParser(
        description="PDF Entity Extractor - Extract people and organizations from PDF documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
    python analyze_pdf.py -f document.pdf
    python analyze_pdf.py -f document.pdf --llm-url http://your-llm-server/v1/chat/completions
"""
    )
    
    parser.add_argument("-f", "--file", required=True,
                        help="Path to PDF file to analyze")
    parser.add_argument("--llm-url", default="http://127.0.0.1:5000/v1/chat/completions",
                        help="URL for LLM API")
    parser.add_argument("--chunk-tokens", type=int, default=4000,
                        help="Maximum tokens per chunk (default: 4000)")
    
    args = parser.parse_args()
    
    try:
        # Validate PDF file
        pdf_path = Path(args.file)
        if not pdf_path.exists():
            print(f"Error: PDF file not found: {pdf_path}")
            return
        
        if pdf_path.suffix.lower() != '.pdf':
            print(f"Error: File must be a PDF: {pdf_path}")
            return
            
        # Process document
        analyzer = DocumentAnalyzer(
            llm_url=args.llm_url,
            max_chunk_tokens=args.chunk_tokens
        )
        
        print(f"Processing PDF: {pdf_path}")
        names_path, orgs_path = analyzer.process_document(pdf_path)
        
        if names_path and orgs_path:
            print(f"\nExtraction complete!")
            print(f"Names list saved to: {names_path}")
            print(f"Organizations list saved to: {orgs_path}")
        else:
            print("\nError: Failed to complete extraction")
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")

if __name__ == "__main__":
    main()