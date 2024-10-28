# search.py
from duckduckgo_search import DDGS
import re

class OSINTSearch:
    def __init__(self):
        self.search_engine = DDGS()

    def search(self, query, site=None, max_results=10):
        if site:
            query = f"site:{site} {query}"
        return self.search_engine.text(query, max_results=max_results)

    def save_results(self, results, query, filename_suffix=".txt"):
        safe_query = re.sub(r'[^\w\-_\. ]', '_', query)
        filename = f"{safe_query}{filename_suffix}"
        with open(filename, "w") as file:
            for result in results:
                file.write(f"{result['title']}\n{result['href']}\n{result['body']}\n\n")
        print(f"Results saved to {filename}")

# Usage example:
# searcher = OSINTSearch()
# results = searcher.search("example_username", site="tiktok.com")
# searcher.save_results(results, query="example_username")
