# search.py
from duckduckgo_search import DDGS
import re
import requests
from pathlib import Path
import logging

class DossierBuilder:
    def __init__(self, llm_url="http://127.0.0.1:5000/v1/chat/completions"):
        self.search_engine = DDGS()
        self.llm_url = llm_url
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def search(self, query, site=None, max_results=100):
        """Perform OSINT search and return filtered results"""
        try:
            # Build search query
            search_query = f"site:{site} {query}" if site else query
            self.logger.info(f"Searching for: {search_query}")
            
            # Get results
            results = self.search_engine.text(search_query, max_results=max_results)
            
            # Filter results that contain the query
            filtered_results = [
                result for result in results 
                if query.lower() in (result['title'] + result['body'] + result['href']).lower()
            ]
            
            self.logger.info(f"Found {len(filtered_results)} relevant results")
            return filtered_results
            
        except Exception as e:
            self.logger.error(f"Search failed: {str(e)}")
            return []

    def save_raw_data(self, results, query):
        """Save raw search results to a text file"""
        # Create results directory if it doesn't exist
        Path("results").mkdir(exist_ok=True)
        
        # Create safe filename
        safe_query = re.sub(r'[^\w\-_\. ]', '_', query)
        filepath = Path("results") / f"{safe_query}_raw.txt"
        
        try:
            with filepath.open("w", encoding='utf-8') as file:
                for result in results:
                    file.write(f"Title: {result['title']}\n")
                    file.write(f"URL: {result['href']}\n")
                    file.write(f"Content: {result['body']}\n\n")
                    
            self.logger.info(f"Raw data saved to {filepath}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"Failed to save raw data: {str(e)}")
            return None

    def generate_dossier(self, filepath, query):
        """Generate a markdown dossier using local LLM"""
        try:
            # Read the raw data
            with filepath.open('r', encoding='utf-8') as file:
                content = file.read()

            # Prepare the prompt for the LLM
            prompt = f"""Analyze the following OSINT data for {query} and create a detailed dossier.
            Focus on:
            1. Key identifiers (usernames, emails, etc.)
            2. Associated platforms and services (include links)
            3. Potential locations
            4. Connected identities
            5. Possible additional search vectors
            
            Format the response in markdown with appropriate sections.
            
            Data to analyze:
            {content}"""

            # Prepare API request
            data = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "You are an OSINT analyst creating a detailed dossier."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 8000
            }

            # Call local LLM
            self.logger.info("Generating dossier using LLM...")
            response = requests.post(
                self.llm_url,
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
            
            # Extract and save dossier
            dossier_content = response.json()["choices"][0]["message"]["content"]
            dossier_path = Path("results") / f"{query}_dossier.md"
            
            with dossier_path.open('w', encoding='utf-8') as file:
                file.write(f"# OSINT Dossier: {query}\n\n")
                file.write(f"*Generated on: {Path(filepath).stat().st_mtime}*\n\n")
                file.write(dossier_content)
                
            self.logger.info(f"Dossier saved to {dossier_path}")
            return dossier_path
            
        except requests.RequestException as e:
            self.logger.error(f"LLM processing failed: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Dossier generation failed: {str(e)}")
            return None