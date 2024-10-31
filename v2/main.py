# main.py
from search import DossierBuilder

def get_additional_terms() -> list:
    """Get additional search terms from user"""
    terms = []
    print("\nEnter additional search terms (press Enter without text to finish):")
    while True:
        term = input("Additional term (or Enter to finish): ").strip()
        if not term:
            break
        terms.append(term)
    return terms

def main():
    print("Enhanced OSINT Dossier Builder")
    print("--------------------------")
    
    main_query = input("Enter main target identifier (username/email/etc): ").strip()
    if not main_query:
        print("Error: Main query cannot be empty")
        return
    
    additional_terms = get_additional_terms()
    site = input("\nEnter specific site to search (optional, e.g. twitter.com): ").strip() or None
    
    try:
        builder = DossierBuilder()
        
        # Perform initial search
        print("\nPerforming initial search...")
        results = builder.search(main_query, additional_terms, site)
        
        if not results:
            print("No results found.")
            return
            
        # Process each result
        print("\nProcessing search results and analyzing web pages...")
        print("This may take some time. Progress will be saved after each page.")
        distilled_path = builder.process_search_results(results, main_query)
        
        # Generate final dossier
        print("\nGenerating final comprehensive dossier...")
        dossier_path = builder.generate_final_dossier(distilled_path, main_query, additional_terms)
        
        if dossier_path:
            print(f"\nDossier successfully generated: {dossier_path}")
            print(f"Distilled data saved to: {distilled_path}")
            print("\nDone!")
        else:
            print("\nError: Failed to generate final dossier")
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")

if __name__ == "__main__":
    main()