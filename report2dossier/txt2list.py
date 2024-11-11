import sys
import json
import requests
from pathlib import Path
from tqdm import tqdm
import time
from typing import List, Dict

class EntityExtractor:
    def __init__(self, chunk_size: int = 2000):
        self.chunk_size = chunk_size
        self.url = "http://127.0.0.1:5000/v1/chat/completions"
        self.headers = {"Content-Type": "application/json"}
        self.system_prompt = """You are a named entity recognition system. Extract all person names and organization names from the input text.
        Return only a JSON object with two lists: 'persons' and 'organizations'. Each list should contain unique entries."""

    def chunk_text(self, text: str) -> List[str]:
        """Split text into chunks while trying to preserve sentence boundaries"""
        words = text.split()
        chunks = []
        current_chunk = []
        current_length = 0
        
        for word in words:
            current_length += len(word) + 1  # +1 for space
            if current_length > self.chunk_size and current_chunk:
                # Try to find a sentence boundary (. ! ?) in the last 100 characters
                chunk_text = " ".join(current_chunk)
                for sep in [". ", "! ", "? "]:
                    last_sep = chunk_text.rfind(sep, -100)
                    if last_sep != -1:
                        chunks.append(chunk_text[:last_sep + 1])
                        current_chunk = chunk_text[last_sep + 1:].split()
                        break
                else:
                    chunks.append(chunk_text)
                    current_chunk = []
                current_length = sum(len(word) + 1 for word in current_chunk)
            current_chunk.append(word)
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        return chunks

    def extract_entities_from_chunk(self, text: str, retry_count: int = 3) -> Dict[str, List[str]]:
        """Extract entities from a single chunk with retry logic"""
        data = {
            "model": "local-model",
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": text}
            ],
            "temperature": 0.0
        }

        for attempt in range(retry_count):
            try:
                response = requests.post(self.url, headers=self.headers, json=data)
                response.raise_for_status()
                result = response.json()
                content = result['choices'][0]['message']['content']
                return json.loads(content)
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                if attempt == retry_count - 1:
                    raise
                time.sleep(1 * (attempt + 1))  # Exponential backoff

    def merge_entities(self, entities_list: List[Dict[str, List[str]]]) -> Dict[str, List[str]]:
        """Merge entities from multiple chunks, removing duplicates"""
        all_persons = set()
        all_organizations = set()
        
        for entities in entities_list:
            all_persons.update(entities.get('persons', []))
            all_organizations.update(entities.get('organizations', []))
        
        return {
            'persons': sorted(list(all_persons)),
            'organizations': sorted(list(all_organizations))
        }

    def process_file(self, input_file: Path) -> Dict[str, List[str]]:
        """Process the entire file with progress monitoring"""
        print(f"Reading file: {input_file}")
        with open(input_file, 'r', encoding='utf-8') as f:
            text = f.read()

        chunks = self.chunk_text(text)
        total_chars = len(text)
        processed_chars = 0
        all_entities = []

        print(f"\nProcessing text ({total_chars:,} characters in {len(chunks)} chunks)")
        progress_bar = tqdm(total=total_chars, unit='chars', unit_scale=True)

        for chunk in chunks:
            try:
                chunk_entities = self.extract_entities_from_chunk(chunk)
                all_entities.append(chunk_entities)
                processed_chars += len(chunk)
                progress_bar.update(len(chunk))
            except Exception as e:
                progress_bar.close()
                print(f"\nError processing chunk: {str(e)}")
                raise

        progress_bar.close()
        return self.merge_entities(all_entities)

def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py input.txt")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    if not input_file.exists():
        print(f"Error: File {input_file} not found")
        sys.exit(1)

    extractor = EntityExtractor()
    
    try:
        print("Starting entity extraction...")
        entities = extractor.process_file(input_file)
        
        output_file = Path('list.txt')
        print(f"\nWriting results to {output_file}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("Persons:\n")
            for person in entities['persons']:
                f.write(f"- {person}\n")
            
            f.write("\nOrganizations:\n")
            for org in entities['organizations']:
                f.write(f"- {org}\n")
        
        print("\nExtraction complete!")
        print(f"Found {len(entities['persons'])} persons and {len(entities['organizations'])} organizations")
            
    except Exception as e:
        print(f"\nError: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()