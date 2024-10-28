# main.py
from search import OSINTSearch

def main():
    searcher = OSINTSearch()
    query = input("Enter the username or email to search: ").strip()
    site = input("Enter a specific site to dork (e.g., tiktok.com) or leave blank for a general search: ").strip() or None

    results = searcher.search(query, site)
    filename = searcher.save_results(results, query=query)

    if filename:
        searcher.process_with_llm(filename)

if __name__ == "__main__":
    main()
