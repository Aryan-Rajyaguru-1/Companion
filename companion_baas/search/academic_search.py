#!/usr/bin/env python3
"""
Academic Search Integration
==========================

Search scholarly sources: Google Scholar, arXiv, PubMed, JSTOR
"""

import asyncio
import aiohttp
from typing import List, Dict, Optional
from datetime import datetime
from companion_baas.search.multi_source_orchestrator import SearchSource, SourceType

class AcademicSearchClient:
    """Search academic papers and scholarly articles"""

    def __init__(self):
        self.serpapi_key = None  # Optional: SerpAPI for Google Scholar
        self.arxiv_enabled = True
        self.pubmed_enabled = True
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def search_scholar(
        self,
        query: str,
        max_results: int = 10
    ) -> List[SearchSource]:
        """
        Search Google Scholar

        Returns papers with:
        - Title
        - Authors
        - Publication year
        - Citations count
        - PDF link (if available)
        - Abstract
        """
        results = []

        try:
            # Try SerpAPI first (if available)
            if self.serpapi_key:
                results = await self._search_scholar_serpapi(query, max_results)
            else:
                # Fallback to scholarly library
                results = await self._search_scholar_scholarly(query, max_results)

        except Exception as e:
            print(f"Google Scholar search failed: {e}")
            results = []

        return results

    async def _search_scholar_serpapi(
        self,
        query: str,
        max_results: int
    ) -> List[SearchSource]:
        """Search Google Scholar using SerpAPI"""
        url = "https://serpapi.com/search"
        params = {
            "engine": "google_scholar",
            "q": query,
            "api_key": self.serpapi_key,
            "num": max_results
        }

        async with self.session.get(url, params=params) as response:
            data = await response.json()

            results = []
            for item in data.get("organic_results", []):
                # Extract publication info
                publication_info = item.get("publication_info", {})
                authors = publication_info.get("authors", [])

                # Calculate credibility score based on citations
                cited_by = item.get("cited_by", {}).get("value", 0)
                credibility_score = min(1.0, cited_by / 1000)  # Normalize

                result = SearchSource(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    source_type=SourceType.ACADEMIC,
                    source_name="Google Scholar",
                    published_date=self._parse_date(item.get("publication_info", {}).get("year")),
                    credibility_score=credibility_score,
                    relevance_score=0.8,  # Scholar results are generally relevant
                    content=item.get("snippet", ""),
                    metadata={
                        "authors": authors,
                        "cited_by": cited_by,
                        "year": item.get("publication_info", {}).get("year"),
                        "pdf_link": item.get("resources", [{}])[0].get("link", "")
                    }
                )
                results.append(result)

            return results

    async def _search_scholar_scholarly(
        self,
        query: str,
        max_results: int
    ) -> List[SearchSource]:
        """Search Google Scholar using scholarly library"""
        try:
            from scholarly import scholarly

            # This is synchronous, so we'll run it in a thread
            import concurrent.futures
            import threading

            def search_sync():
                search_query = scholarly.search_pubs(query)
                results = []
                for i, pub in enumerate(search_query):
                    if i >= max_results:
                        break

                    try:
                        pub_filled = scholarly.fill(pub)

                        # Calculate credibility score
                        cited_by = pub_filled.get('num_citations', 0)
                        credibility_score = min(1.0, cited_by / 1000)

                        result = SearchSource(
                            title=pub_filled.get('title', ''),
                            url=pub_filled.get('pub_url', ''),
                            snippet=pub_filled.get('abstract', '')[:200] + '...' if pub_filled.get('abstract') else '',
                            source_type=SourceType.ACADEMIC,
                            source_name="Google Scholar",
                            published_date=self._parse_date(pub_filled.get('year')),
                            credibility_score=credibility_score,
                            relevance_score=0.8,
                            content=pub_filled.get('abstract', ''),
                            metadata={
                                "authors": pub_filled.get('author', []),
                                "cited_by": cited_by,
                                "year": pub_filled.get('year'),
                                "venue": pub_filled.get('venue')
                            }
                        )
                        results.append(result)
                    except Exception as e:
                        print(f"Error processing scholar result: {e}")
                        continue

                return results

            # Run in thread pool to avoid blocking
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(search_sync)
                return future.result(timeout=30)

        except ImportError:
            print("scholarly library not available")
            return []
        except Exception as e:
            print(f"Scholarly search failed: {e}")
            return []

    async def search_arxiv(
        self,
        query: str,
        max_results: int = 10,
        category: Optional[str] = None
    ) -> List[SearchSource]:
        """
        Search arXiv.org (physics, math, CS papers)

        Categories:
        - cs.AI: Artificial Intelligence
        - cs.LG: Machine Learning
        - math.CO: Combinatorics
        - physics.gen-ph: General Physics
        """
        try:
            import arxiv

            # Create search
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance,
                sort_order=arxiv.SortOrder.Descending
            )

            if category:
                search = arxiv.Search(
                    query=query,
                    max_results=max_results,
                    sort_by=arxiv.SortCriterion.Relevance,
                    sort_order=arxiv.SortOrder.Descending
                )
                # Filter by category (this is approximate)
                results = []
                for paper in search.results():
                    if category in paper.categories:
                        results.append(paper)
                        if len(results) >= max_results:
                            break
            else:
                results = list(search.results())

            search_results = []
            for paper in results:
                # Calculate credibility score based on recency and citations
                years_old = datetime.now().year - paper.published.year
                recency_score = max(0.1, 1.0 - (years_old / 10))  # Favor recent papers

                result = SearchSource(
                    title=paper.title,
                    url=paper.pdf_url,
                    snippet=paper.summary[:300] + '...' if len(paper.summary) > 300 else paper.summary,
                    source_type=SourceType.ACADEMIC,
                    source_name="arXiv",
                    published_date=paper.published,
                    credibility_score=recency_score,
                    relevance_score=0.9,  # arXiv papers are generally high quality
                    content=paper.summary,
                    metadata={
                        "authors": [author.name for author in paper.authors],
                        "categories": paper.categories,
                        "primary_category": paper.primary_category,
                        "doi": paper.doi,
                        "journal_ref": paper.journal_ref,
                        "updated": paper.updated
                    }
                )
                search_results.append(result)

            return search_results

        except ImportError:
            print("arxiv library not available")
            return []
        except Exception as e:
            print(f"arXiv search failed: {e}")
            return []

    async def search_pubmed(
        self,
        query: str,
        max_results: int = 10
    ) -> List[SearchSource]:
        """
        Search PubMed (biomedical literature)

        Returns medical/biological papers
        """
        try:
            from Bio import Entrez
            import concurrent.futures

            Entrez.email = "deepthink-ai@example.com"  # Required by NCBI

            def search_sync():
                try:
                    # Search
                    handle = Entrez.esearch(
                        db="pubmed",
                        term=query,
                        retmax=max_results,
                        sort="relevance"
                    )
                    record = Entrez.read(handle)
                    handle.close()

                    ids = record["IdList"]

                    if not ids:
                        return []

                    # Fetch details
                    handle = Entrez.efetch(
                        db="pubmed",
                        id=ids,
                        retmode="xml"
                    )
                    papers = Entrez.read(handle)
                    handle.close()

                    return self._parse_pubmed_results(papers)

                except Exception as e:
                    print(f"PubMed search failed: {e}")
                    return []

            # Run in thread pool
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(search_sync)
                return future.result(timeout=30)

        except ImportError:
            print("BioPython not available")
            return []
        except Exception as e:
            print(f"PubMed search failed: {e}")
            return []

    def _parse_pubmed_results(self, papers) -> List[SearchSource]:
        """Parse PubMed XML results"""
        results = []

        try:
            for paper in papers['PubmedArticle']:
                article = paper['MedlineCitation']['Article']

                # Extract title
                title = article['ArticleTitle']

                # Extract authors
                authors = []
                if 'AuthorList' in article:
                    authors = [
                        author.get('LastName', '') + ' ' + author.get('ForeName', '')
                        for author in article.get('AuthorList', [])
                        if author.get('LastName')
                    ]

                # Extract abstract
                abstract = ""
                if 'Abstract' in article and article['Abstract'].get('AbstractText'):
                    abstract_text = article['Abstract']['AbstractText']
                    if isinstance(abstract_text, list):
                        abstract = ' '.join(abstract_text)
                    else:
                        abstract = abstract_text

                # Extract publication date
                pub_date = None
                if 'Journal' in article:
                    journal_issue = article['Journal'].get('JournalIssue', {})
                    pub_date_info = journal_issue.get('PubDate', {})

                    try:
                        year = pub_date_info.get('Year')
                        month = pub_date_info.get('Month')
                        day = pub_date_info.get('Day')

                        if year:
                            if month and day:
                                pub_date = datetime(int(year), int(month), int(day))
                            elif month:
                                pub_date = datetime(int(year), int(month), 1)
                            else:
                                pub_date = datetime(int(year), 1, 1)
                    except:
                        pass

                # Calculate credibility score (PubMed papers are generally credible)
                credibility_score = 0.9

                result = SearchSource(
                    title=title,
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{paper['MedlineCitation']['PMID']}/",
                    snippet=abstract[:300] + '...' if len(abstract) > 300 else abstract,
                    source_type=SourceType.ACADEMIC,
                    source_name="PubMed",
                    published_date=pub_date,
                    credibility_score=credibility_score,
                    relevance_score=0.85,
                    content=abstract,
                    metadata={
                        "authors": authors,
                        "pmid": paper['MedlineCitation']['PMID'],
                        "journal": article.get('Journal', {}).get('Title', ''),
                        "doi": next(
                            (id['#text'] for id in article.get('ELocationID', []) if id['@EIdType'] == 'doi'),
                            None
                        )
                    }
                )
                results.append(result)

        except Exception as e:
            print(f"Error parsing PubMed results: {e}")

        return results

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string into datetime object"""
        if not date_str:
            return None

        try:
            # Try different date formats
            for fmt in ['%Y', '%Y-%m', '%Y-%m-%d']:
                try:
                    return datetime.strptime(str(date_str), fmt)
                except ValueError:
                    continue
            return None
        except:
            return None

    async def search_all_academic(
        self,
        query: str,
        max_results: int = 8
    ) -> List[SearchSource]:
        """
        Search all academic sources simultaneously

        Returns combined results from Google Scholar, arXiv, PubMed
        """
        tasks = []

        if self.arxiv_enabled:
            tasks.append(self.search_arxiv(query, max_results // 3))

        if self.pubmed_enabled:
            tasks.append(self.search_pubmed(query, max_results // 3))

        # Google Scholar (may be slower)
        tasks.append(self.search_scholar(query, max_results // 3))

        # Run all searches in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten results
        all_results = []
        for result in results:
            if isinstance(result, list):
                all_results.extend(result)
            elif isinstance(result, Exception):
                print(f"Academic search failed: {result}")

        # Sort by relevance and credibility
        all_results.sort(key=lambda x: x.relevance_score * x.credibility_score, reverse=True)

        return all_results[:max_results]