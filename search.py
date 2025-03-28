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
    def __init__(self, llm_url="http://127.0.0.1:5000/v1/chat/completions",
                 max_page_tokens: int = 4000,
                 max_dossier_tokens: int = 16000):
        self.search_engine = DDGS()
        self.llm_url = llm_url
        self.max_page_tokens = max_page_tokens
        self.max_dossier_tokens = max_dossier_tokens
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

        
    def search(self, main_query: str, additional_terms: List[str], site: Optional[str] = None, max_results: int = 25) -> List[Dict]:
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
            
            Provide only factual information found in the content. Format as clear, concise bullet points. If information is not found in the content don't reference that bullet point or say it wasn't found, just skip it.
            
            Content to analyze:
            {content[:8000]}  # Limit content length for LLM
            """

            data = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "You are an OSINT analyst extracting key details from web content."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": self.max_page_tokens
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
        result_number = 1  # Initialize counter
        
        for result in results:
            url = result['href']
            self.logger.info(f"Processing result {result_number}: {url}")
            
            # Skip if URL seems invalid
            if not urlparse(url).scheme:
                continue
                
            # Fetch and analyze content
            content = self.fetch_webpage_content(url)
            if content:
                analysis = self.analyze_page_content(content, url, main_query)
                if analysis:
                    # Add result number to the analysis
                    analysis.update({
                        "result_number": result_number,
                        "original_title": result.get('title', '')
                    })
                    
                    processed_data.append(analysis)
                    
                    # Save progress after each successful analysis
                    with distilled_path.open('w', encoding='utf-8') as f:
                        json.dump({
                            "metadata": {
                                "target": main_query,
                                "total_results_processed": result_number,
                                "last_updated": str(Path(distilled_path).stat().st_mtime if distilled_path.exists() else None)
                            },
                            "results": processed_data
                        }, f, indent=2)
                    
                    result_number += 1  # Increment counter only for successfully processed results
                    
            # Be nice to servers
            sleep(2)
            
        return distilled_path

    def generate_final_dossier(self, distilled_path: Path, main_query: str, additional_terms: List[str]) -> Optional[Path]:
        """Generate final dossier from distilled information"""
        try:
            # Read distilled data
            with distilled_path.open('r', encoding='utf-8') as f:
                distilled_data = json.load(f)

            # Calculate statistics for prompt context
            total_sources = len(distilled_data["results"])
            domains = set(urlparse(result["url"]).netloc for result in distilled_data["results"])
            
            prompt = f"""Create a comprehensive intelligence dossier for target '{main_query}' using data from {total_sources} sources across {len(domains)} distinct domains.
            Additional context terms: {', '.join(additional_terms)}

            Generate an extensive, detailed analysis that thoroughly covers ALL available information. You have up to {self.max_dossier_tokens} tokens available - use them to provide the most comprehensive dossier possible.

            Structure the dossier with the following sections, providing extensive detail for each:

            1. EXECUTIVE SUMMARY
            - High-confidence key findings
            - Reliability assessment of sources
            - Major intelligence gaps

            2. IDENTITY AND BACKGROUND
            - Core identifiers and accounts
            - Biographical information
            - Professional/educational history
            - Location history and geographic associations

            3. DETAILED TIMELINE
            - Chronological analysis of all dated events and activities
            - Pattern analysis across time periods

            4. ASSOCIATIONS AND RELATIONSHIPS
            - Personal connections
            - Professional networks
            - Organizational affiliations
            - Platform and service usage

            5. TECHNICAL FOOTPRINT
            - Digital platforms and services
            - Technical indicators
            - Online behavior patterns
            - Account correlation analysis

            6. GEOGRAPHIC ANALYSIS
            - Confirmed locations
            - Probable locations based on evidence
            - Travel patterns if apparent
            - Geographic points of interest

            7. SOURCE ANALYSIS
            - Detailed evaluation of each significant source
            - Cross-reference patterns
            - Conflicting information assessment
            - Source reliability matrix

            8. INTELLIGENCE GAPS AND UNCERTAINTIES
            - Identified information gaps
            - Conflicting data points
            - Alternative hypotheses
            - Recommended additional collection vectors

            For each section:
            - Provide extensive detail
            - Include specific examples and evidence
            - Cross-reference information across sources
            - Assess confidence levels
            - Note contradictions or uncertainties
            - Cite source numbers [Result #X] for key findings

            Raw Data for Analysis:
            {json.dumps(distilled_data, indent=2)}"""

            data = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": """You are an expert OSINT analyst creating detailed intelligence dossiers.
                    Your task is to create the most comprehensive analysis possible using all available token space.
                    Include specific details, examples, and evidence rather than general statements.
                    Always cite sources using [Result #X] notation."""},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": self.max_dossier_tokens,
                "temperature": 0.7  # Add some variability to encourage more detailed responses
            }

            response = requests.post(
                self.llm_url,
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=300
            )
            response.raise_for_status()
            
            dossier_content = response.json()["choices"][0]["message"]["content"]
            
            # Add metadata header to dossier
            metadata_header = f"""# OSINT Dossier: {main_query}

*Investigation Details:*
- Target: `{main_query}`
- Search Context: {', '.join(additional_terms)}
- Sources Analyzed: {total_sources}
- Distinct Domains: {len(domains)}
- Generation Date: {Path(distilled_path).stat().st_mtime}
- Token Limit: {self.max_dossier_tokens}

---

"""
            
            dossier_path = Path("results") / f"{main_query}_final_dossier.md"
            
            with dossier_path.open('w', encoding='utf-8') as f:
                f.write(metadata_header)
                f.write(dossier_content)
            
            # Log token usage estimation
            approx_tokens = len(dossier_content.split()) * 1.3  # Rough estimation
            self.logger.info(f"Estimated dossier token usage: {int(approx_tokens)} of {self.max_dossier_tokens} available")
            
            return dossier_path
            
        except Exception as e:
            self.logger.error(f"Failed to generate final dossier: {str(e)}")
            return None