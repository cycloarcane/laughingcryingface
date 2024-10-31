# search.py
from duckduckgo_search import DDGS
import re
import requests
from pathlib import Path
import logging
from typing import List, Optional, Dict
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from time import sleep
import json

class DossierBuilder:
    def __init__(self, llm_url="http://127.0.0.1:5000/v1/chat/completions"):
        self.search_engine = DDGS()
        self.llm_url = llm_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def search(self, main_query: str, additional_terms: List[str], site: Optional[str] = None, max_results: int = 100) -> List[Dict]:
        """Perform OSINT search with combined terms"""
        try:
            # Build search query
            search_query = self.build_search_query(main_query, additional_terms, site)
            self.logger.info(f"Searching for: {search_query}")
            
            # Get results with retry mechanism
            try_count = 0
            max_tries = 3
            while try_count < max_tries:
                try:
                    results = list(self.search_engine.text(search_query, max_results=max_results))
                    break
                except Exception as e:
                    try_count += 1
                    if try_count == max_tries:
                        raise e
                    sleep(2)  # Wait before retry
            
            # Filter results that contain the main query
            filtered_results = []
            for result in results:
                if isinstance(result, dict) and all(k in result for k in ['title', 'body', 'href']):
                    if main_query.lower() in (result['title'] + result['body'] + result['href']).lower():
                        filtered_results.append(result)
            
            self.logger.info(f"Found {len(filtered_results)} relevant results")
            return filtered_results
            
        except Exception as e:
            self.logger.error(f"Search failed: {str(e)}")
            raise

 
    def build_search_query(self, main_query: str, additional_terms: List[str], site: Optional[str] = None) -> str:
        """Build a search query combining main query with additional terms"""
        combined_query = f'"{main_query}"'
        for term in additional_terms:
            if term.strip():
                combined_query += f' "{term.strip()}"'
        if site:
            combined_query = f"site:{site} {combined_query}"
        return combined_query

    def fetch_webpage_content(self, url: str) -> Optional[str]:
        """Fetch and extract clean text content from a webpage"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for element in soup(['script', 'style', 'header', 'footer', 'nav']):
                element.decompose()
            
            # Get text content
            text = soup.get_text(separator='\n', strip=True)
            
            # Clean up excessive whitespace
            text = re.sub(r'\n\s*\n', '\n\n', text)
            
            return text
            
        except Exception as e:
            self.logger.error(f"Failed to fetch {url}: {str(e)}")
            return None

    def analyze_page_content(self, content: str, url: str, main_query: str) -> Optional[Dict]:
        """Analyze a single webpage's content using LLM"""
        try:
            prompt = f"""Analyze the following webpage content about {main_query}.
            URL: {url}
            
            Extract and summarize key details about the target focusing on:
            1. Biographical information
            2. Key dates and events
            3. Contact information or identifiers
            4. Locations mentioned
            5. Associated people or organizations
            6. Platform usage or digital footprint
            7. Professional or educational history
            
            Provide only factual information found in the content. Format as clear, concise bullet points.
            
            Content to analyze:
            {content[:8000]}  # Limit content length for LLM
            """

            data = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "You are an OSINT analyst extracting key details from web content."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 2000
            }

            response = requests.post(
                self.llm_url,
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=60
            )
            response.raise_for_status()
            
            analysis = response.json()["choices"][0]["message"]["content"]
            
            return {
                "url": url,
                "analysis": analysis,
                "timestamp": Path().stat().st_mtime
            }
            
        except Exception as e:
            self.logger.error(f"Failed to analyze content from {url}: {str(e)}")
            return None

    def process_search_results(self, results: List[Dict], main_query: str) -> Path:
        """Process each search result individually and save distilled information"""
        Path("results").mkdir(exist_ok=True)
        safe_query = re.sub(r'[^\w\-_\. ]', '_', main_query)
        distilled_path = Path("results") / f"{safe_query}_distilled.json"
        
        processed_data = []
        
        for result in results:
            url = result['href']
            self.logger.info(f"Processing: {url}")
            
            # Skip if URL seems invalid
            if not urlparse(url).scheme:
                continue
                
            # Fetch and analyze content
            content = self.fetch_webpage_content(url)
            if content:
                analysis = self.analyze_page_content(content, url, main_query)
                if analysis:
                    processed_data.append(analysis)
                    
                    # Save progress after each successful analysis
                    with distilled_path.open('w', encoding='utf-8') as f:
                        json.dump(processed_data, f, indent=2)
                    
            # Be nice to servers
            sleep(2)
            
        return distilled_path

    def generate_final_dossier(self, distilled_path: Path, main_query: str, additional_terms: List[str]) -> Optional[Path]:
        """Generate final dossier from distilled information"""
        try:
            # Read distilled data
            with distilled_path.open('r', encoding='utf-8') as f:
                distilled_data = json.load(f)

            prompt = f"""Create a comprehensive intelligence dossier for {main_query} using the following analyzed data
            from multiple sources. Consider the context terms: {', '.join(additional_terms)}

            Focus on:
            1. Cross-referencing and verifying information across sources
            2. Identifying patterns and connections
            3. Timeline construction
            4. Reliability assessment of information
            5. Potential intelligence gaps
            
            Format the response in markdown with appropriate sections.
            
            Analyzed Data:
            {json.dumps(distilled_data, indent=2)}"""

            data = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "You are an OSINT analyst creating a detailed intelligence dossier."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 8000
            }

            response = requests.post(
                self.llm_url,
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=300
            )
            response.raise_for_status()
            
            dossier_content = response.json()["choices"][0]["message"]["content"]
            dossier_path = Path("results") / f"{main_query}_final_dossier.md"
            
            with dossier_path.open('w', encoding='utf-8') as f:
                f.write(f"# OSINT Dossier: {main_query}\n\n")
                f.write(f"*Search Context: {', '.join(additional_terms)}*\n\n")
                f.write(f"*Generated on: {Path(distilled_path).stat().st_mtime}*\n\n")
                f.write(dossier_content)
            
            return dossier_path
            
        except Exception as e:
            self.logger.error(f"Failed to generate final dossier: {str(e)}")
            return None