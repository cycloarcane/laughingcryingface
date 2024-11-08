import PyPDF2
import spacy
import en_core_web_sm
import requests
from pathlib import Path
import logging
from typing import List, Dict, Optional, Set, Tuple
import json
from collections import Counter
import re

class DocumentAnalyzer:
    def __init__(self, llm_url="http://127.0.0.1:5000/v1/chat/completions",
                 max_chunk_tokens: int = 4000):
        # Initialize spaCy with custom configuration
        self.nlp = en_core_web_sm.load()
        # Adjust NER confidence threshold
        self.nlp.get_pipe('ner').cfg['threshold'] = 0.7
        
        self.llm_url = llm_url
        self.max_chunk_tokens = max_chunk_tokens
        
        # Load common name completions and organizations
        self.name_completions = {
            "Sam A": "Sam Altman",
            "Elon M": "Elon Musk",
            "Bill G": "Bill Gates",
            "Steve J": "Steve Jobs",
            "Mark Z": "Mark Zuckerberg",
            # Add more common completions as needed
        }
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def clean_text(self, text: str) -> str:
        """Clean PDF extracted text to handle common artifacts"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        # Fix common PDF artifacts
        text = re.sub(r'(?<=\w)-\s+(?=\w)', '', text)  # Fix hyphenated words
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)  # Add space between joined words
        # Remove non-text artifacts
        text = re.sub(r'[^\w\s.,;:?!-]', ' ', text)
        return text.strip()

    def is_valid_name(self, name: str) -> bool:
        """Validate if a string looks like a legitimate name"""
        # Must be at least 4 characters
        if len(name) < 4:
            return False
            
        # Must contain at least 2 letters
        if sum(c.isalpha() for c in name) < 2:
            return False
            
        # Check for common invalid patterns
        invalid_patterns = [
            r'\d',  # Contains numbers
            r'^[a-z]',  # Starts with lowercase
            r'\s[a-z]',  # Word starting with lowercase
            r'[^a-zA-Z\s\'-]',  # Contains characters other than letters, spaces, hyphens, apostrophes
            r'\s{2,}',  # Contains multiple consecutive spaces
            r'^[A-Z]\s?$',  # Single letter or letter with space
            r'^[A-Z][a-z]?$'  # One or two letters only
        ]
        
        for pattern in invalid_patterns:
            if re.search(pattern, name):
                return False
                
        # Must contain at least one space (first and last name)
        # Unless it's a well-formed single name like "Shakespeare"
        if ' ' not in name and len(name) < 8:
            return False
            
        return True

    def complete_partial_name(self, name: str, text: str) -> str:
        """Attempt to complete partial names using context"""
        # Check predefined completions
        if name in self.name_completions:
            return self.name_completions[name]
            
        # Look for full name in surrounding text
        words = text.split()
        name_parts = name.lower().split()
        
        # Search for names that start with our partial name
        for i in range(len(words)):
            if ' '.join(words[i:i+len(name_parts)]).lower() == ' '.join(name_parts).lower():
                # Look ahead for additional name parts
                potential_full_name = []
                j = i
                while j < len(words) and j < i + 5:  # Look up to 5 words ahead
                    word = words[j]
                    if word[0].isupper():  # Only add capitalized words
                        potential_full_name.append(word)
                    else:
                        break
                    j += 1
                
                if len(potential_full_name) > len(name_parts):
                    completed_name = ' '.join(potential_full_name)
                    if self.is_valid_name(completed_name):
                        return completed_name
        
        return name

    def merge_similar_names(self, names: Set[str]) -> Dict[str, Set[str]]:
        """Merge variations of the same name"""
        name_groups = {}
        processed_names = set()
        
        for name1 in names:
            if name1 in processed_names:
                continue
                
            similar_names = {name1}
            for name2 in names:
                if name2 in processed_names:
                    continue
                    
                # Check if names are variations of each other
                if self._are_name_variations(name1, name2):
                    similar_names.add(name2)
                    processed_names.add(name2)
                    
            if similar_names:
                # Use the longest name as the canonical form
                canonical_name = max(similar_names, key=len)
                name_groups[canonical_name] = similar_names
                processed_names.update(similar_names)
                
        return name_groups

    def _are_name_variations(self, name1: str, name2: str) -> bool:
        """Check if two names are likely variations of the same person"""
        # Split names into parts
        parts1 = name1.split()
        parts2 = name2.split()
        
        # If one is contained within the other
        if name1 in name2 or name2 in name1:
            return True
            
        # Check for matching last names and first initial
        if len(parts1) > 0 and len(parts2) > 0:
            # Check last names
            if parts1[-1] == parts2[-1]:
                # Check first initials
                if parts1[0][0] == parts2[0][0]:
                    return True
                    
        return False

    def extract_organizations(self, text: str) -> List[str]:
        """Extract organization names using NER"""
        # Clean text first
        clean_text = self.clean_text(text)
        
        # Process text in manageable chunks
        chunk_size = 5000
        chunks = [clean_text[i:i+chunk_size] for i in range(0, len(clean_text), chunk_size)]
        
        org_counts = Counter()
        
        for chunk in chunks:
            doc = self.nlp(chunk)
            
            # Extract organization entities
            for ent in doc.ents:
                if ent.label_ == 'ORG':
                    org = self.clean_organization_name(ent.text)
                    if org:
                        org_counts[org] += 1
        
        # Filter out likely false positives and sort by frequency
        valid_orgs = [org for org, count in org_counts.items() 
                     if self.is_valid_organization(org) and count >= 1]
        
        return sorted(valid_orgs)

    def clean_organization_name(self, org: str) -> Optional[str]:
        """Clean and validate organization names"""
        # Remove common noise and formatting issues
        org = org.strip()
        org = re.sub(r'\s+', ' ', org)
        org = re.sub(r'[^\w\s&.,()-]', '', org)
        
        # Remove common false positives
        invalid_orgs = {'The', 'A', 'An', 'This', 'That', 'These', 'Those', 'It'}
        if org in invalid_orgs:
            return None
            
        return org.strip()

    def is_valid_organization(self, org: str) -> bool:
        """Validate if a string looks like a legitimate organization name"""
        if not org or len(org) < 2:
            return False
            
        # Check for common organization endings
        org_indicators = {'Inc', 'Corp', 'Ltd', 'LLC', 'Company', 'Technologies', 
                         'Systems', 'Solutions', 'Group', 'Foundation', 'Institute',
                         'Association', 'University', 'College', 'School'}
                         
        # Must be properly capitalized or contain org indicators
        has_proper_caps = org[0].isupper() and any(word[0].isupper() for word in org.split())
        has_org_indicator = any(indicator in org for indicator in org_indicators)
        
        return has_proper_caps or has_org_indicator

    def extract_people_and_orgs(self, text: str) -> Tuple[List[str], List[str]]:
        """Extract both people and organization names"""
        # Clean text first
        clean_text = self.clean_text(text)
        
        # Process text in manageable chunks
        chunk_size = 5000
        chunks = [clean_text[i:i+chunk_size] for i in range(0, len(clean_text), chunk_size)]
        
        all_names = set()
        for chunk in chunks:
            doc = self.nlp(chunk)
            
            # Extract person entities
            for ent in doc.ents:
                if ent.label_ == 'PERSON':
                    name = ent.text.strip()
                    if self.is_valid_name(name):
                        # Try to complete partial names
                        completed_name = self.complete_partial_name(name, chunk)
                        all_names.add(completed_name)
        
        # Merge similar names
        name_groups = self.merge_similar_names(all_names)
        people = list(name_groups.keys())
        
        # Extract organizations
        organizations = self.extract_organizations(text)
        
        return people, organizations

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text content from PDF file with improved handling"""
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = []
                for page in reader.pages:
                    # Extract text from each page
                    page_text = page.extract_text()
                    # Clean the text
                    cleaned_text = self.clean_text(page_text)
                    text.append(cleaned_text)
                    
                return '\n'.join(text)
        except Exception as e:
            self.logger.error(f"Failed to read PDF: {str(e)}")
            raise

    def analyze_person_mentions(self, text: str, person: str) -> Dict:
        """Analyze contexts where a person is mentioned"""
        try:
            # Find relevant context around mentions
            contexts = self._extract_mention_contexts(text, person)
            
            prompt = f"""Analyze the following person mentioned in the document: {person}

            Based on these contexts where they are mentioned:
            {contexts}

            Extract and summarize:
            1. Their role/position/title (if mentioned)
            2. Key actions or contributions discussed
            3. Relationships with other entities mentioned
            4. Importance to the document's content (rank 1-10, explain why)
            5. Brief biographical details if mentioned

            Provide only factual information found in the content. Format as clear, concise bullet points.
            If certain aspects are not mentioned in the content, omit those bullet points.
            """

            data = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "You are an analyst extracting and summarizing information about people mentioned in documents."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": self.max_chunk_tokens
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
                "name": person,
                "analysis": analysis,
                "mention_count": len(contexts),
                "contexts": contexts
            }
            
        except Exception as e:
            self.logger.error(f"Failed to analyze mentions for {person}: {str(e)}")
            return None

    def _extract_mention_contexts(self, text: str, person: str, context_words: int = 50) -> List[str]:
        """Extract relevant context around name mentions"""
        contexts = []
        words = text.split()
        person_parts = person.lower().split()
        
        for i, word in enumerate(words):
            # Check if this word starts a match for the person's name
            if word.lower() == person_parts[0]:
                # Check if full name matches
                potential_name = ' '.join(words[i:i+len(person_parts)])
                if potential_name.lower() == person.lower():
                    # Extract context around mention
                    start = max(0, i - context_words)
                    end = min(len(words), i + len(person_parts) + context_words)
                    context = ' '.join(words[start:end])
                    contexts.append(context)
                    
        return contexts

    def save_entities_list(self, people: List[str], organizations: List[str], output_path: Path) -> Tuple[Path, Path]:
        """Save separate lists of people and organizations"""
        try:
            # Create file paths
            names_file = output_path.parent / f"{output_path.stem}_names.txt"
            orgs_file = output_path.parent / f"{output_path.stem}_organizations.txt"
            
            # Sort lists
            sorted_people = sorted(people)
            sorted_orgs = sorted(organizations)
            
            # Write people to file
            with names_file.open('w', encoding='utf-8') as f:
                f.write('\n'.join(sorted_people))
                
            # Write organizations to file
            with orgs_file.open('w', encoding='utf-8') as f:
                f.write('\n'.join(sorted_orgs))
                
            return names_file, orgs_file
            
        except Exception as e:
            self.logger.error(f"Failed to save entity lists: {str(e)}")
            raise

    def generate_markdown_dossier(self, analyses: List[Dict], document_name: str, organizations: List[str]) -> str:
        """Generate final markdown dossier with people and organizations"""
        try:
            # Sort analyses by mention count
            sorted_analyses = sorted(analyses, key=lambda x: x['mention_count'], reverse=True)
            
            markdown = f"""# Document Analysis: {document_name}

## Overview
Document analyzed: `{document_name}`
Total people identified: {len(analyses)}
Total organizations identified: {len(organizations)}

## Key People Analysis
(Ranked by relevance to document content)

"""
            # Add each person's analysis
            for idx, analysis in enumerate(sorted_analyses, 1):
                markdown += f"### {idx}. {analysis['name']}\n"
                markdown += f"*Mentions in document: {analysis['mention_count']}*\n\n"
                markdown += analysis['analysis']
                markdown += "\n\n---\n\n"
                
            # Add organizations section
            markdown += f"""
## Organizations Mentioned
Total organizations: {len(organizations)}

"""
            for org in sorted(organizations):
                markdown += f"- {org}\n"
                                
                return markdown
                            
        except Exception as e:
            self.logger.error(f"Failed to generate markdown dossier: {str(e)}")
            raise

    def process_document(self, pdf_path: str) -> Tuple[Optional[Path], Optional[Path], Optional[Path]]:
        """Main method to process PDF and generate analysis"""
        try:
            pdf_path = Path(pdf_path)
            self.logger.info(f"Processing document: {pdf_path}")
            
            # Extract text from PDF
            text = self.extract_text_from_pdf(str(pdf_path))
            
            # Extract people and organizations
            people, organizations = self.extract_people_and_orgs(text)
            self.logger.info(f"Found {len(people)} unique people and {len(organizations)} organizations")
            
            # Create results directory if it doesn't exist
            output_dir = Path("results")
            output_dir.mkdir(exist_ok=True)
            
            # Save entity lists
            names_path, orgs_path = self.save_entities_list(people, organizations, output_dir / pdf_path.stem)
            
            # Continue with detailed analysis
            analyses = []
            for person in people:
                self.logger.info(f"Analyzing mentions of: {person}")
                analysis = self.analyze_person_mentions(text, person)
                if analysis:
                    analyses.append(analysis)
                    
            # Generate markdown dossier
            markdown_content = self.generate_markdown_dossier(analyses, pdf_path.name, organizations)
            
            # Save markdown dossier
            dossier_path = output_dir / f"{pdf_path.stem}_analysis.md"
            with dossier_path.open('w', encoding='utf-8') as f:
                f.write(markdown_content)
                
            return dossier_path, names_path, orgs_path
            
        except Exception as e:
            self.logger.error(f"Failed to process document: {str(e)}")
            return None, None, None