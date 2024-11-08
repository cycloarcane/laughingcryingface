import argparse
from pathlib import Path
from pdf_analyzer import DocumentAnalyzer

def main():
    parser = argparse.ArgumentParser(
        description="PDF Document Analyzer - Extract and analyze people and organizations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
    python analyze_pdf.py -f document.pdf
    python analyze_pdf.py -f document.pdf --entities-only
"""
    )
    
    parser.add_argument("-f", "--file", required=True,
                        help="Path to PDF file to analyze")
    parser.add_argument("--entities-only", action="store_true",
                        help="Only output the lists of names and organizations, skip detailed analysis")
    parser.add_argument("--llm-url", default="http://127.0.0.1:5000/v1/chat/completions",
                        help="URL for LLM API (default: http://127.0.0.1:5000/v1/chat/completions)")
    parser.add_argument("--max-chunk-tokens", type=int, default=4000,
                        help="Maximum tokens for analysis chunks (default: 4000)")
    
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
            max_chunk_tokens=args.max_chunk_tokens
        )
        
        print(f"Processing PDF: {pdf_path}")
        
        if args.entities_only:
            # Extract text and entities
            text = analyzer.extract_text_from_pdf(str(pdf_path))
            people, organizations = analyzer.extract_people_and_orgs(text)
            
            # Save entity lists
            output_dir = Path("results")
            output_dir.mkdir(exist_ok=True)
            names_path, orgs_path = analyzer.save_entities_list(people, organizations, output_dir / pdf_path.stem)
            
            print(f"\nFound {len(people)} people and {len(organizations)} organizations")
            print(f"Names list saved to: {names_path}")
            print(f"Organizations list saved to: {orgs_path}")
        else:
            # Full analysis
            dossier_path, names_path, orgs_path = analyzer.process_document(pdf_path)
            
            if all((dossier_path, names_path, orgs_path)):
                print(f"\nAnalysis complete!")
                print(f"Full analysis saved to: {dossier_path}")
                print(f"Names list saved to: {names_path}")
                print(f"Organizations list saved to: {orgs_path}")
            else:
                print("\nError: Failed to complete analysis")
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")

if __name__ == "__main__":
    main()