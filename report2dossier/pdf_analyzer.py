import PyPDF2
import requests
from pathlib import Path
import logging
from typing import List, Dict, Optional, Tuple
import json
import re
import time

class DocumentAnalyzer:
    def __init__(self, llm_url="http://127.0.0.1:5000/v1/chat/completions",
                 max_chunk_tokens: int = 2000):
        self.llm_url = llm_url
        self.max_chunk_tokens = max_chunk_tokens
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text content from PDF file"""
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = []
                for page in reader.pages:
                    text.append(page.extract_text())
                return '\n'.join(text)
        except Exception as e:
            self.logger.error(f"Failed to read PDF: {str(e)}")
            raise

    def clean_text_chunk(self, text: str) -> str:
        """Clean text chunk before processing"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Fix common PDF artifacts
        text = re.sub(r'(?<=\w)-\s+(?=\w)', '', text)  # Fix hyphenated words
        text = re.sub(r'(?<=\w)\s+(?=\w)', ' ', text)  # Fix split words
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s.,;:?!-]', ' ', text)
        return text.strip()

    def filter_invalid_entities(self, entities: List[str]) -> List[str]:
        """Filter out invalid entities like dates and artifacts"""
        filtered = []
        
        # Patterns to exclude
        date_patterns = [
            r'file d',  # Matches "file d" prefix
            r'\b[A-Z][a-z]{2,8}\s+\d{1,2},?\s+\d{4}\b',  # Month DD, YYYY
            r'\b\d{1,2}\s+[A-Z][a-z]{2,8}\s+\d{4}\b',  # DD Month YYYY
            r'N o v emb er',  # Split November
            r'Ma y',  # Split May
            r'file d.*\d{4}',  # Any "filed" followed by a year
            r'\b[A-Z][a-z]{2,8}\s+\d{1,2}\b'  # Month DD
        ]
        
        # Combine all patterns
        combined_pattern = '|'.join(date_patterns)
        
        for entity in entities:
            # Skip if entity matches any date pattern
            if re.search(combined_pattern, entity, re.IGNORECASE):
                continue
                
            # Skip if entity is too short
            if len(entity) < 4:
                continue
                
            # Skip if entity has too many numbers
            if sum(c.isdigit() for c in entity) > 2:
                continue
                
            # Skip if entity has weird spacing
            if re.search(r'\w\s\w\s\w', entity):
                continue
                
            filtered.append(entity)
        
        return filtered

    def extract_entities(self, text: str) -> Tuple[List[str], List[str]]:
            """Extract people and organizations using LLM"""
            try:
                # Reduce chunk size and increase timeout
                chunk_size = 2000  # Reduced from 6000
                chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
                
                all_people = set()
                all_organizations = set()
                
                for i, chunk in enumerate(chunks, 1):
                    self.logger.info(f"Processing chunk {i} of {len(chunks)}")
                    
                    # Clean the chunk
                    clean_chunk = self.clean_text_chunk(chunk)
                    
                    # Skip empty or very short chunks
                    if len(clean_chunk.strip()) < 100:
                        continue
                    
                    data = {
                        "model": "gpt-3.5-turbo",
                        "messages": [
                            {
                                "role": "system",
                                "content": "Extract names of people and organizations from text. Respond only with JSON."
                            },
                            {
                                "role": "user",
                                "content": f"""Extract named entities from this text. Return only a JSON object with two arrays.

    Format: {{"people": ["Name 1", "Name 2"], "organizations": ["Org 1", "Org 2"]}}

    Rules:
    - Include full names for people
    - Include complete organization names
    - Exclude dates and numbers
    - Exclude partial or unclear names

    Text:
    {clean_chunk}"""
                            }
                        ],
                        "max_tokens": 1000,  # Reduced from 4000
                        "temperature": 0.3
                    }

                    retries = 3
                    for attempt in range(retries):
                        try:
                            response = requests.post(
                                self.llm_url,
                                json=data,
                                headers={"Content-Type": "application/json"},
                                timeout=30  # Reduced timeout, but will retry
                            )
                            response.raise_for_status()
                            
                            content = response.json()["choices"][0]["message"]["content"]
                            # Clean the content string
                            content = content.strip()
                            if not content.startswith('{'):
                                content = content[content.find('{'):]
                            if not content.endswith('}'):
                                content = content[:content.rfind('}')+1]
                                
                            entities = json.loads(content)
                            
                            # Update sets with new entities
                            if "people" in entities:
                                all_people.update(entities["people"])
                            if "organizations" in entities:
                                all_organizations.update(entities["organizations"])
                                
                            # If successful, break retry loop
                            break
                            
                        except requests.Timeout:
                            self.logger.warning(f"Timeout on chunk {i}, attempt {attempt + 1}/{retries}")
                            if attempt == retries - 1:  # Last attempt
                                self.logger.error(f"Failed to process chunk {i} after {retries} attempts")
                        except json.JSONDecodeError as e:
                            self.logger.warning(f"Failed to parse JSON from chunk {i}: {str(e)}")
                            break  # Don't retry JSON parsing errors
                        except Exception as e:
                            self.logger.warning(f"Error processing chunk {i}: {str(e)}")
                            if attempt == retries - 1:  # Last attempt
                                self.logger.error(f"Failed to process chunk {i} after {retries} attempts")
                    
                    # Add a small delay between chunks
                    time.sleep(1)
                
                # Remove empty strings and duplicates, then filter invalid entities
                people = self.filter_invalid_entities(sorted(list(filter(None, all_people))))
                organizations = self.filter_invalid_entities(sorted(list(filter(None, all_organizations))))
                
                self.logger.info(f"Extracted {len(people)} people and {len(organizations)} organizations")
                return people, organizations
                
            except Exception as e:
                self.logger.error(f"Failed to extract entities: {str(e)}")
                raise

    def save_entity_lists(self, people: List[str], organizations: List[str], output_path: Path) -> Tuple[Path, Path]:
        """Save lists of people and organizations to separate files"""
        try:
            # Create file paths
            names_file = output_path.parent / f"{output_path.stem}_names.txt"
            orgs_file = output_path.parent / f"{output_path.stem}_organizations.txt"
            
            # Write people to file
            with names_file.open('w', encoding='utf-8') as f:
                f.write('\n'.join(people))
                
            # Write organizations to file
            with orgs_file.open('w', encoding='utf-8') as f:
                f.write('\n'.join(organizations))
                
            return names_file, orgs_file
            
        except Exception as e:
            self.logger.error(f"Failed to save entity lists: {str(e)}")
            raise

    def process_document(self, pdf_path: str) -> Tuple[Optional[Path], Optional[Path]]:
        """Process PDF and extract entities"""
        try:
            pdf_path = Path(pdf_path)
            self.logger.info(f"Processing document: {pdf_path}")
            
            # Extract text from PDF
            text = self.extract_text_from_pdf(str(pdf_path))
            
            # Extract entities
            people, organizations = self.extract_entities(text)
            self.logger.info(f"Found {len(people)} people and {len(organizations)} organizations")
            
            # Create results directory if it doesn't exist
            output_dir = Path("results")
            output_dir.mkdir(exist_ok=True)
            
            # Save entity lists
            names_path, orgs_path = self.save_entity_lists(
                people, organizations, output_dir / pdf_path.stem
            )
            
            return names_path, orgs_path
            
        except Exception as e:
            self.logger.error(f"Failed to process document: {str(e)}")
            return None, None