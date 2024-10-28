# search.py
from duckduckgo_search import DDGS
import re
import requests

class OSINTSearch:
    def __init__(self):
        self.search_engine = DDGS()

    def search(self, query, site=None, max_results=10):
        if site:
            query = f"site:{site} {query}"
        results = self.search_engine.text(query, max_results=max_results)
        
        filtered_results = [
            result for result in results 
            if query.lower() in (result['title'] + result['body'] + result['href']).lower()
        ]
        return filtered_results

    def save_results(self, results, query, filename_suffix=".txt"):
        safe_query = re.sub(r'[^\w\-_\. ]', '_', query)
        filename = f"{safe_query}{filename_suffix}"
        with open(filename, "w") as file:
            for result in results:
                file.write(f"{result['title']}\n{result['href']}\n{result['body']}\n\n")
        print(f"Results saved to {filename}")
        return filename  # Return filename for use in LLM processing

    def process_with_llm(self, filename, endpoint="http://127.0.0.1:5000/v1/chat/completions"):
        try:
            with open(filename, "r") as file:
                content = file.read()

            data = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {
                        "role": "system",
                        "content": "Look at the provided information and distill key information such as usernames, email addresses, locations, used services etc and organise them under headings."
                    },
                    {
                        "role": "user",
                        "content": content
                    }
                ],
                "max_tokens": 500,
            }

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer YOUR_API_KEY"  # Replace with actual token setup if required
            }

            response = requests.post(endpoint, json=data, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            print("LLM Response:", result["choices"][0]["message"]["content"])
            return result["choices"][0]["message"]["content"]

        except (IOError, requests.RequestException) as e:
            print(f"Error processing with LLM: {e}")
            return None
