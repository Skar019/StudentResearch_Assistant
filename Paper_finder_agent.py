"""
Paper Finder Agent — Agents for Humans Hackathon submission

An AI agent that helps student researchers gather suitable reference papers
based on a topic, a call-for-abstracts theme, or a personal research direction.

Run:
    python paper_finder_agent.py

Then type your topic/description when prompted.
"""

import requests
import xml.etree.ElementTree as ET
from strands import Agent, tool


@tool
def search_papers(query: str, limit: int = 6) -> str:
    """Search for academic papers relevant to a research topic using Semantic Scholar.

    Use this whenever the user describes a research topic, a call-for-abstracts theme,
    or a personal research direction and wants reference papers to read.

    Args:
        query: The search query — a topic, theme, or research direction.
        limit: Max number of papers to return (default 6).

    Returns:
        A formatted string listing matching papers: title, authors, year,
        abstract snippet, and an open-access PDF link when available.
    """
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": limit,
        "fields": "title,authors,year,abstract,url,openAccessPdf,venue",
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return f"Search failed: {e}"

    papers = data.get("data", [])
    if not papers:
        return f"No papers found for query: '{query}'"

    lines = [f"Found {len(papers)} papers for '{query}':\n"]
    for i, p in enumerate(papers, 1):
        title = p.get("title", "Untitled")
        year = p.get("year", "n.d.")
        venue = p.get("venue", "")
        authors = ", ".join(a.get("name", "") for a in (p.get("authors") or [])[:3])
        if len(p.get("authors") or []) > 3:
            authors += " et al."
        abstract = (p.get("abstract") or "No abstract available.")[:280]
        pdf = p.get("openAccessPdf")
        pdf_link = pdf.get("url") if pdf else None
        page_link = p.get("url", "")

        lines.append(f"{i}. {title} ({year})")
        if authors:
            lines.append(f"   Authors: {authors}")
        if venue:
            lines.append(f"   Venue: {venue}")
        lines.append(f"   Abstract: {abstract}...")
        if pdf_link:
            lines.append(f"   Open-access PDF: {pdf_link}")
        else:
            lines.append(f"   Page: {page_link} (no free PDF found via Semantic Scholar)")
        lines.append("")

    return "\n".join(lines)

@tool
def search_arxiv(query: str, limit: int = 6) -> str:
    """Search arXiv for papers. Use this if search_papers is rate-limited or returns nothing.

    Args:
        query: The search query.
        limit: Max papers to return.
    """
    url = "http://export.arxiv.org/api/query"
    params = {"search_query": f"all:{query}", "max_results": limit}
    try:
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        root = ET.fromstring(r.text)
    except Exception as e:
        return f"arXiv search failed: {e}"

    ns = {"a": "http://www.w3.org/2005/Atom"}
    entries = root.findall("a:entry", ns)
    if not entries:
        return f"No arXiv papers for '{query}'"

    out = [f"Found {len(entries)} arXiv papers for '{query}':\n"]
    for i, e in enumerate(entries, 1):
        title = e.find("a:title", ns).text.strip().replace("\n", " ")
        summary = e.find("a:summary", ns).text.strip()[:280]
        link = e.find("a:id", ns).text
        pub = e.find("a:published", ns).text[:4]
        authors = ", ".join(a.find("a:name", ns).text for a in e.findall("a:author", ns)[:3])
        out += [f"{i}. {title} ({pub})", f"   Authors: {authors}",
                f"   Abstract: {summary}...", f"   PDF: {link.replace('/abs/', '/pdf/')}", ""]
    return "\n".join(out)

SYSTEM_PROMPT = """You are a research assistant that helps student researchers find
reference papers to study. The user will describe either:
1. A personal research topic/direction they're writing about, or
2. Topics proposed by a call for abstracts/articles (optionally combined with their
   own preferred angle on it).

When they describe their context, break it down into 1-3 focused search queries and
use the search_papers tool for each. Then present a single consolidated, well-organized
list of the most relevant papers back to them, grouped by sub-theme if helpful, and
briefly note why each paper seems relevant to their stated direction

If both search tools fail or are rate-limited after one attempt each, do NOT invent
or recall papers from memory or training data — you must never present citations you
have not actually retrieved from a tool call in this conversation. Instead, tell the
user plainly that live search is temporarily unavailable right now and suggest they
retry again shortly.

Try each search tool at most once per query per attempt. If a tool fails or times out,
move on to the other tool or report the failure to the user — do not retry the same
tool repeatedly within a single response.
"""


def main():
    agent = Agent(tools=[search_papers, search_arxiv], system_prompt=SYSTEM_PROMPT)

    print("=" * 60)
    print("Paper Finder Agent")
    print("Describe your research topic, call-for-abstracts theme,")
    print("and/or personal direction. Type your request below:")
    print("=" * 60)

    user_input = input("\nYour research context: ").strip()
    if not user_input:
        print("No input given — exiting.")
        return

    result = agent(user_input)

    print("\n" + "=" * 60)
    print("Run summary")
    print("=" * 60)
    summary = result.metrics.get_summary()
    usage = summary.get("accumulated_usage", {})
    print(f"Tokens used: {usage.get('totalTokens', 'n/a')}")
    print(f"Tool calls: {summary.get('tool_usage', {}).keys()}")


if __name__ == "__main__":
    main()