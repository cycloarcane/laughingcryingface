# search.py
from duckduckgo_search import DDGS
import re
import requests
from pathlib import Path
import logging
from typing import List, Optional, Dict

class DossierBuilder:
    def __init__(self, llm_url="http://127.0.0.1:5000/v1/chat/completions"):
        self.search_engine = DDGS()
        self.llm_url = llm_url
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def build_search_query(self, main_query: str, additional_terms: List[str], site: Optional[str] = None) -> str:
        """Build a search query combining main query with additional terms"""
        # Combine main query with additional terms
        combined_query = f'"{main_query}"' # Exact match for main query
        
        # Add additional terms
        for term in additional_terms:
            if term.strip():
                combined_query += f' "{term.strip()}"'
        
        # Add site restriction if specified
        if site:
            combined_query = f"site:{site} {combined_query}"
            
        return combined_query

    def search(self, main_query: str, additional_terms: List[str], site: Optional[str] = None, max_results: int = 100) -> List[Dict]:
        """Perform OSINT search with combined terms"""
        try:
            # Build search query
            search_query = self.build_search_query(main_query, additional_terms, site)
            self.logger.info(f"Searching for: {search_query}")
            
            # Get results
            results = self.search_engine.text(search_query, max_results=max_results)
            
            # Filter results that contain the main query
            filtered_results = [
                result for result in results 
                if main_query.lower() in (result['title'] + result['body'] + result['href']).lower()
            ]
            
            self.logger.info(f"Found {len(filtered_results)} relevant results")
            return filtered_results
            
        except Exception as e:
            self.logger.error(f"Search failed: {str(e)}")
            return []

    def save_raw_data(self, results: List[Dict], main_query: str, additional_terms: List[str]) -> Optional[Path]:
        """Save raw search results to a text file"""
        Path("results").mkdir(exist_ok=True)
        
        # Create filename using main query and first additional term
        safe_query = re.sub(r'[^\w\-_\. ]', '_', main_query)
        if additional_terms:
            safe_terms = re.sub(r'[^\w\-_\. ]', '_', '_'.join(additional_terms))
            safe_query = f"{safe_query}_{safe_terms}"
            
        filepath = Path("results") / f"{safe_query}_raw.txt"
        
        try:
            with filepath.open("w", encoding='utf-8') as file:
                # Write search parameters
                file.write(f"Main Query: {main_query}\n")
                file.write(f"Additional Terms: {', '.join(additional_terms)}\n")
                file.write("-" * 50 + "\n\n")
                
                # Write results
                for result in results:
                    file.write(f"Title: {result['title']}\n")
                    file.write(f"URL: {result['href']}\n")
                    file.write(f"Content: {result['body']}\n\n")
                    
            self.logger.info(f"Raw data saved to {filepath}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"Failed to save raw data: {str(e)}")
            return None

    def generate_dossier(self, filepath: Path, main_query: str, additional_terms: List[str]) -> Optional[Path]:
        """Generate a markdown dossier using local LLM"""
        try:
            # Read the raw data
            with filepath.open('r', encoding='utf-8') as file:
                content = file.read()

            # Prepare the prompt for the LLM
            prompt = f"""Analyze the following OSINT data for target {main_query} with context terms: {', '.join(additional_terms)}
            
            Create a detailed intelligence dossier focusing on:
            1. Reports of death (Obituary detection)
            2. Key identifiers (usernames, emails, etc.)
            3. Associated platforms and services
            4. Potential locations and geographic indicators
            5. Connected identities and relationships
            6. Timeline of activities (if available)
            7. Possible additional search vectors
            8. Relevance of context terms ({', '.join(additional_terms)}) to the target
            
            
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
                timeout=300
            )
            response.raise_for_status()
            
            # Extract and save dossier
            dossier_content = response.json()["choices"][0]["message"]["content"]
            safe_query = re.sub(r'[^\w\-_\. ]', '_', main_query)
            dossier_path = Path("results") / f"{safe_query}_dossier.md"
            
            with dossier_path.open('w', encoding='utf-8') as file:
                file.write(f"# OSINT Dossier: {main_query}\n\n")
                file.write(f"*Search Context: {', '.join(additional_terms)}*\n\n")
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