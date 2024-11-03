# main.py
import argparse
from search import DossierBuilder
from pathlib import Path
from typing import List
import sys
from concurrent.futures import ProcessPoolExecutor
import json

def process_single_target(args: argparse.Namespace, target: str, additional_terms: List[str]) -> None:
    """Process a single search target"""
    try:
        builder = DossierBuilder(
            max_page_tokens=args.page_tokens,
            max_dossier_tokens=args.dossier_tokens
        )
        
        print(f"\nProcessing target: {target}")
        
        # Perform initial search
        print("Performing initial search...")
        results = builder.search(target, additional_terms, args.site, args.max_results)
        
        if not results:
            print(f"No results found for {target}")
            return
            
        # Process each result
        print("Processing search results and analyzing web pages...")
        print("This may take some time. Progress will be saved after each page.")
        distilled_path = builder.process_search_results(results, target)
        
        # Generate final dossier
        print("Generating final comprehensive dossier...")
        dossier_path = builder.generate_final_dossier(distilled_path, target, additional_terms)
        
        if dossier_path:
            print(f"Dossier successfully generated: {dossier_path}")
            print(f"Distilled data saved to: {distilled_path}")
            print("Done!")
        else:
            print(f"Error: Failed to generate final dossier for {target}")
            
    except Exception as e:
        print(f"An error occurred processing {target}: {str(e)}")

def get_additional_terms() -> List[str]:
    """Get additional search terms from user"""
    terms = []
    print("\nEnter additional search terms (press Enter without text to finish):")
    while True:
        term = input("Additional term (or Enter to finish): ").strip()
        if not term:
            break
        terms.append(term)
    return terms

def load_targets_file(file_path: str) -> List[str]:
    """Load targets from a text file"""
    try:
        with open(file_path, 'r') as f:
            # Remove empty lines and whitespace
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"Error reading targets file: {str(e)}")
        sys.exit(1)

def save_batch_summary(targets: List[str], args: argparse.Namespace):
    """Save batch processing parameters for reference"""
    summary = {
        "batch_parameters": {
            "max_results": args.max_results,
            "page_tokens": args.page_tokens,
            "dossier_tokens": args.dossier_tokens,
            "site_restriction": args.site,
            "targets": targets
        }
    }
    
    with open("results/batch_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description="Enhanced OSINT Dossier Builder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Single target:
    python main.py -t username123 -m 50
  
  Batch processing:
    python main.py -f targets.txt -m 100 --page-tokens 2000
    
  With site restriction:
    python main.py -t username123 -s twitter.com
    
Note: The targets file should contain one target identifier per line.
"""
    )
    
    # Add arguments
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("-t", "--target", help="Single target identifier")
    input_group.add_argument("-f", "--file", help="File containing target identifiers (one per line)")
    
    parser.add_argument("-m", "--max-results", type=int, default=25,
                        help="Maximum number of search results to process (default: 100)")
    parser.add_argument("-p", "--page-tokens", type=int, default=2000,
                        help="Maximum tokens for page analysis (default: 2000)")
    parser.add_argument("-d", "--dossier-tokens", type=int, default=8000,
                        help="Maximum tokens for final dossier generation (default: 8000)")
    parser.add_argument("-s", "--site", help="Restrict search to specific site (e.g., twitter.com)")
    parser.add_argument("--parallel", action="store_true",
                        help="Enable parallel processing for batch targets")
    
    args = parser.parse_args()

    # Create results directory
    Path("results").mkdir(exist_ok=True)

    try:
        # Handle single target vs batch processing
        if args.target:
            additional_terms = get_additional_terms()
            process_single_target(args, args.target, additional_terms)
        else:
            targets = load_targets_file(args.file)
            print(f"Loaded {len(targets)} targets from {args.file}")
            
            # Get additional terms once for all targets
            additional_terms = get_additional_terms()
            
            # Save batch parameters
            save_batch_summary(targets, args)
            
            if args.parallel:
                # Parallel processing
                with ProcessPoolExecutor() as executor:
                    futures = [
                        executor.submit(process_single_target, args, target, additional_terms)
                        for target in targets
                    ]
                    for future in futures:
                        future.result()  # This will raise any exceptions that occurred
            else:
                # Sequential processing
                for target in targets:
                    process_single_target(args, target, additional_terms)
            
            print("\nBatch processing complete!")
            print(f"Results saved in the 'results' directory")
            print(f"Batch summary saved to 'results/batch_summary.json'")
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()