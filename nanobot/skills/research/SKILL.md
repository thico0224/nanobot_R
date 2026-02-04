---
name: research
description: Academic research assistant using structured academic APIs (arXiv, Semantic Scholar, OpenAlex).
homepage: https://arxiv.org/
metadata: {"nanobot":{"emoji":"🧪","always":true}}
---

# Research

This skill turns nanobot into a **research-grade academic assistant**.
It retrieves papers using **structured academic APIs** and produces evidence-based analysis.

Supported sources:
- **arXiv** — newest preprints (no API key)
- **Semantic Scholar** — citations, venue, DOI (free)
- **OpenAlex** — large-scale academic metadata (free)

---

## Primary Tool (MANDATORY)

### `academic_search`

This is the **only allowed tool** for academic literature retrieval.

It provides:
- Structured paper metadata
- Reproducible results
- Clear source attribution

### Recommended (auto mode)

```json
{
  "query": "multimodal emotion recognition",
  "source": "auto",
  "max_results": 10
}
