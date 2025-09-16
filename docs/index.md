<script>
  if (window.mermaid) { mermaid.initialize({ startOnLoad: true }); }
</script>
# releasecopilot-ai Docs

Welcome! This site documents the architecture and implementation details for **releasecopilot-ai**, a modular, AWS-deployable AI release audit tool that integrates with Jira and Bitbucket, with future Agent + RAG capabilities.

- Start with **Architecture → Overview** for a guided tour.
- Diagrams are authored in Mermaid and rendered live.

## Local Preview
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-docs.txt || pip install mkdocs mkdocs-material pymdown-extensions
mkdocs serve
```
Open the URL printed in the terminal (usually http://127.0.0.1:8000).
