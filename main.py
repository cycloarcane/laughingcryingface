# main.py
from search import DossierBuilder

def main():
    print("OSINT Dossier Builder")
    print("--------------------")
    
    # Get search parameters
    query = input("Enter target identifier (username/email/etc): ").strip()
    if not query:
        print("Error: Query cannot be empty")
        return
        
    site = input("Enter specific site to search (optional, e.g. twitter.com): ").strip() or None
    
    try:
        # Initialize dossier builder
        builder = DossierBuilder()
        
        # Perform search
        print("\nSearching...")
        results = builder.search(query, site)
        
        if not results:
            print("No results found.")
            return
            
        # Save raw data
        raw_file = builder.save_raw_data(results, query)
        if not raw_file:
            print("Error: Failed to save raw data")
            return
            
        # Generate dossier
        print("\nGenerating dossier...")
        dossier_path = builder.generate_dossier(raw_file, query)
        
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