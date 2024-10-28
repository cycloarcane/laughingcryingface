# search.py
from duckduckgo_search import DDGS
import re
import requests
import os

class OSINTSearch:
    def __init__(self):
        self.search_engine = DDGS()

    def search(self, query, site=None, max_results=100):
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
        return filename

    def process_with_llm(self, filename, endpoint="http://127.0.0.1:5000/v1/chat/completions"):
        if os.stat(filename).st_size == 0:  # Check if the file is empty
            print(f"{filename} is empty. Skipping LLM processing.")
            return None

        try:
            with open(filename, "r") as file:
                content = file.read()

            data = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {
                        "role": "system",
                        "content": "Look at the provided information and distill key information such as usernames, email addresses, locations, used services etc and organise them under headings. Focus on fining additional information that could be used to perform futher iterative searches. You can provide information you are unsure about in a section called 'possbile leads:'."
                    },
                    {
                        "role": "user",
                        "content": content
                    }
                ],
                "max_tokens": 8000,
            }

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer YOUR_API_KEY"
            }

            response = requests.post(endpoint, json=data, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            llm_output = result["choices"][0]["message"]["content"]
            print("LLM Response:", llm_output)

            # Save the output to a markdown file
            md_filename = filename.replace(".txt", ".md")
            with open(md_filename, "w") as md_file:
                md_file.write(f"# Analysis for {filename}\n\n")
                md_file.write(llm_output)
            print(f"LLM output saved to {md_filename}")

            return llm_output

        except (IOError, requests.RequestException) as e:
            print(f"Error processing with LLM: {e}")
            return None
