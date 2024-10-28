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
    print("OSINT Dossier Builder")
    print("--------------------")
    
    # Get main query
    main_query = input("Enter main target identifier (username/email/etc): ").strip()
    if not main_query:
        print("Error: Main query cannot be empty")
        return
    
    # Get additional search terms
    additional_terms = get_additional_terms()
        
    # Get optional site restriction
    site = input("\nEnter specific site to search (optional, e.g. twitter.com): ").strip() or None
    
    try:
        # Initialize dossier builder
        builder = DossierBuilder()
        
        # Perform search
        print("\nSearching...")
        if additional_terms:
            print(f"Main query: {main_query}")
            print(f"Additional terms: {', '.join(additional_terms)}")
        results = builder.search(main_query, additional_terms, site)
        
        if not results:
            print("No results found.")
            return
            
        # Save raw data
        raw_file = builder.save_raw_data(results, main_query, additional_terms)
        if not raw_file:
            print("Error: Failed to save raw data")
            return
            
        # Generate dossier
        print("\nGenerating dossier...")
        dossier_path = builder.generate_dossier(raw_file, main_query, additional_terms)
        
        if dossier_path:
            print(f"\nDossier successfully generated: {dossier_path}")
            print("\nDone!")
        else:
            print("\nError: Failed to generate dossier")
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")

if __name__ == "__main__":
    main()