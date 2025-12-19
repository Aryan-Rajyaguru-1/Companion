#!/usr/bin/env python3
"""
Citation Manager
===============

Manages inline citations and source tracking like Perplexity
"""

import re
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Citation:
    """Single citation"""
    number: int
    source_title: str
    source_url: str
    snippet: str
    timestamp: str

class CitationManager:
    """
    Manages citations in AI responses

    Features:
    - Automatic citation insertion
    - Source tracking
    - Deduplication
    - Citation formatting
    """

    def __init__(self):
        self.citations = {}
        self.next_citation_number = 1

    def add_citation(
        self,
        source_title: str,
        source_url: str,
        snippet: str
    ) -> int:
        """
        Add a citation and return its number

        Returns:
            Citation number to use in text
        """
        # Check if this URL already has a citation
        for num, citation in self.citations.items():
            if citation.source_url == source_url:
                return num

        # Create new citation
        num = self.next_citation_number
        self.citations[num] = Citation(
            number=num,
            source_title=source_title,
            source_url=source_url,
            snippet=snippet,
            timestamp=datetime.now().isoformat()
        )

        self.next_citation_number += 1
        return num

    def insert_citations_in_text(
        self,
        text: str,
        claim_to_source_map: Dict[str, str]
    ) -> str:
        """
        Insert citation numbers into text

        Args:
            text: The AI-generated response
            claim_to_source_map: Map of claims to source URLs

        Returns:
            Text with citations like [1], [2], etc.
        """
        for claim, source_url in claim_to_source_map.items():
            # Find citation number for this source
            citation_num = None
            for num, citation in self.citations.items():
                if citation.source_url == source_url:
                    citation_num = num
                    break

            if citation_num:
                # Replace claim with cited version
                cited_claim = f"{claim} [{citation_num}]"
                text = text.replace(claim, cited_claim)

        return text

    def format_citation_list(self) -> str:
        """
        Format citations as a list

        Returns:
            Formatted HTML citation list
        """
        html = "<div class='citations'>\n"
        html += "<h3>Sources</h3>\n"
        html += "<ol>\n"

        for num in sorted(self.citations.keys()):
            citation = self.citations[num]
            html += f"""
            <li>
                <a href="{citation.source_url}" target="_blank">
                    {citation.source_title}
                </a>
                <p class="snippet">{citation.snippet}</p>
            </li>
            """

        html += "</ol>\n</div>"
        return html

    def get_citations(self) -> List[Citation]:
        """Get all citations as list"""
        return [self.citations[num] for num in sorted(self.citations.keys())]

    def get_citation_dict(self) -> Dict[int, Citation]:
        """Get citations as dictionary"""
        return self.citations.copy()

    def clear_citations(self) -> None:
        """Clear all citations"""
        self.citations.clear()
        self.next_citation_number = 1

    def get_citation_count(self) -> int:
        """Get number of citations"""
        return len(self.citations)

    def get_citation_by_number(self, number: int) -> Citation:
        """Get citation by number"""
        return self.citations.get(number)

    def get_citation_by_url(self, url: str) -> Citation:
        """Get citation by URL"""
        for citation in self.citations.values():
            if citation.source_url == url:
                return citation
        return None

    def merge_citations(self, other_manager: 'CitationManager') -> None:
        """
        Merge citations from another manager

        Args:
            other_manager: Another CitationManager to merge from
        """
        for citation in other_manager.get_citations():
            # Check if URL already exists
            if not self.get_citation_by_url(citation.source_url):
                # Add with new number
                num = self.next_citation_number
                self.citations[num] = Citation(
                    number=num,
                    source_title=citation.source_title,
                    source_url=citation.source_url,
                    snippet=citation.snippet,
                    timestamp=citation.timestamp
                )
                self.next_citation_number += 1

    def export_citations(self, format: str = "json") -> str:
        """
        Export citations in various formats

        Args:
            format: Export format ("json", "html", "markdown", "bibtex")

        Returns:
            Formatted citation string
        """
        if format == "json":
            import json
            return json.dumps({
                num: {
                    "title": citation.source_title,
                    "url": citation.source_url,
                    "snippet": citation.snippet,
                    "timestamp": citation.timestamp
                }
                for num, citation in self.citations.items()
            }, indent=2)

        elif format == "html":
            return self.format_citation_list()

        elif format == "markdown":
            md = "## Sources\n\n"
            for num in sorted(self.citations.keys()):
                citation = self.citations[num]
                md += f"{num}. [{citation.source_title}]({citation.source_url})\n"
                if citation.snippet:
                    md += f"   > {citation.snippet}\n"
                md += "\n"
            return md

        elif format == "bibtex":
            bibtex = ""
            for num, citation in self.citations.items():
                bibtex += f"@misc{{citation{num},\n"
                bibtex += f"  title={{{citation.source_title}}},\n"
                bibtex += f"  url={{{citation.source_url}}},\n"
                bibtex += f"  note={{{citation.snippet}}},\n"
                bibtex += "}\n\n"
            return bibtex

        else:
            raise ValueError(f"Unsupported format: {format}")

    def validate_citations(self, text: str) -> Dict[str, Any]:
        """
        Validate that all citations in text are properly referenced

        Args:
            text: Text containing citations like [1], [2]

        Returns:
            Validation results
        """
        # Find all citation references in text
        citation_refs = re.findall(r'\[(\d+)\]', text)
        referenced_numbers = set(int(ref) for ref in citation_refs)

        # Check which citations exist
        existing_numbers = set(self.citations.keys())

        missing_citations = referenced_numbers - existing_numbers
        unused_citations = existing_numbers - referenced_numbers

        return {
            "valid": len(missing_citations) == 0,
            "referenced_citations": sorted(referenced_numbers),
            "missing_citations": sorted(missing_citations),
            "unused_citations": sorted(unused_citations),
            "total_references": len(citation_refs),
            "unique_references": len(referenced_numbers)
        }

    def get_citation_stats(self) -> Dict[str, Any]:
        """Get statistics about citations"""
        domains = {}
        source_types = {}

        for citation in self.citations.values():
            # Extract domain
            try:
                from urllib.parse import urlparse
                domain = urlparse(citation.source_url).netloc
                domains[domain] = domains.get(domain, 0) + 1
            except:
                domains["unknown"] = domains.get("unknown", 0) + 1

            # Count source types (would need to be added to Citation class)
            # source_types[citation.source_type] = source_types.get(citation.source_type, 0) + 1

        return {
            "total_citations": len(self.citations),
            "unique_domains": len(domains),
            "domain_distribution": domains,
            "source_type_distribution": source_types
        }

    def optimize_citations(self, text: str) -> str:
        """
        Optimize citation placement in text

        Args:
            text: Text with citations

        Returns:
            Optimized text
        """
        # This could implement more sophisticated citation placement
        # For now, just return the text as-is
        return text

    def create_citation_map(self, sources: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Create a mapping from source URLs to citation numbers

        Args:
            sources: List of source dictionaries with 'url', 'title', 'snippet'

        Returns:
            Dictionary mapping URLs to citation numbers
        """
        citation_map = {}

        for source in sources:
            citation_num = self.add_citation(
                source_title=source.get('title', 'Unknown'),
                source_url=source['url'],
                snippet=source.get('snippet', '')
            )
            citation_map[source['url']] = citation_num

        return citation_map