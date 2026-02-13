# Plan Review Findings & Research Conclusions (2026-02-12)

## Context
The clew improvement plan at `~/.claude/plans/synthetic-doodling-kernighan.md` was reviewed by 4 parallel specialized agents (DHH-style architecture, Kieran-style code quality, code simplicity, codebase fact-checker) plus 1 independent viability gap analyst. An additional research agent surveyed industry approaches to code search accuracy.

## Key Findings

### Plan Changes Made
The plan was revised to:
- **Cut Task 2 (Jedi):** Fixes 0 of 16 test failures, Django-hostile, not portable
- **Cut Task 6 (Explain circuit breaker):** Diagnosis factually wrong — `mcp_server.py:291-296` already handles missing API key correctly
- **Simplified Task 3:** Replaced NetworkX PageRank with SQL edge count. Fixed boost formula from `0.95 + (importance * 0.15)` to `1.0 + (importance * 0.25)`
- **Added 4 new tasks:**
  - Fix PascalCase rerank skip (`rerank.py:50`) — 1-line fix, 2-3 test failures
  - Remove DEBUG test-boost prefetch in `hybrid.py`
  - File summary chunks during indexing
  - Port ignore pattern fix from earlier plan
- **Reduced team architecture** from 4 parallel devs to 2 (pipeline vs search) to eliminate merge conflicts
- **Zero new dependencies** (removed jedi, networkx)

### Projected Scores
- Current: 1.72/3.0 (NOT VIABLE)
- After revised plan: ~2.30/3.0 (CONDITIONAL VIABILITY)
- After plan + index-time enrichment: ~2.50-2.60 (approaching STRONG VIABILITY)

### Viability Test Key Stats
- 16 A/B tests, clew vs grep/glob/read
- Accuracy: 0.63/3.0 (catastrophically low)
- Completeness: 0.56/3.0 (catastrophically low)
- Efficiency: 3.00/3.0 (excellent — 80-95% context reduction)
- Tool Calls: 2.81/3.0 (excellent — consistently fewer calls)
- 0/16 complete answers, 10/16 partial, 6/16 missed
- trace() returned 0 relationships in 7/10 calls
- Full results at: /Users/albertgwo/Work/evvy/docs/plans/2026-02-11-clew-viability-results.md

### Root Causes Validated
1. Entity normalization broken → empty traces (may already be fixed by recent commits)
2. ecomm/utils.py systematically underranked
3. PascalCase queries skip Voyage reranking (rerank.py:50)
4. DEBUG intent boosts test files instead of demoting them
5. No Django FK/M2M/O2O edges in relationship graph
6. No file-level summary chunks for broad queries
7. Pattern matching (grep tasks) fundamentally impossible with semantic search

## Industry Research Conclusions

### Key Finding: Index-Time Enrichment > Query-Time Reformulation
The industry consensus from Greptile, GitHub, Sourcegraph, and academic literature:
- **Improve what you INDEX, not how you QUERY**
- Greptile: 12% cosine similarity improvement from recursive docstring generation
- GitHub: 37.6% retrieval improvement from better code-specific embedding model
- Sourcegraph: Abandoned embeddings for BM25+learned signals at enterprise scale
- Weaviate Query Agent: 14-second latency — unusable for interactive search

### Deterministic Drop-In Alternatives (No LLM Required)
| Approach | What | Gain | Qdrant Native? |
|----------|------|------|---------------|
| miniCOIL | Learned sparse retrieval (BM25 replacement) | +3-5% | Yes (FastEmbed) |
| ColBERT | Per-token late interaction | +8-15% | Yes (multivector since 1.10) |
| Multi-vector | Separate embeddings for signature/body/description | +5-10% | Yes (named vectors) |

### Model Selection for Index-Time NL Description Generation
| Model | SWE-bench | Cost/1K chunks | Quality |
|-------|-----------|---------------|---------|
| Haiku 3.5 | 40.6% | ~$0.80 | Too shallow |
| Haiku 4.5 | 73.3% | ~$1.00 | Sweet spot? Under evaluation |
| Sonnet 4.5 | ~65% | ~$3.00 | Better reasoning, 3x cost |
| Opus 4.6 | Best | ~$5.00 | Best quality, 5x cost |

### Recommended Phases
1. **Phase A (Highest ROI):** Index-time enrichment — enrich chunk content before embedding with NL description + relationships + callers + imports + layer + keywords
2. **Phase B:** Query-adaptive routing (extend intent classifier)
3. **Phase C:** HyDE with Haiku 4.5 for NL queries only (deferred)
4. **Phase D:** miniCOIL/ColBERT drop-ins (deferred, evaluate after A+B)

### Open Questions
- Which model for index-time enrichment? (Haiku 4.5 vs Sonnet 4.5 vs Opus 4.6)
- Should NL descriptions be enabled by default (not opt-in)?
- How to incorporate relationship/trace data into embeddings?
- miniCOIL as BM25 replacement — worth investigating?
- ColBERT multivector — storage tradeoff acceptable?

## References
- Viability test results: /Users/albertgwo/Work/evvy/docs/plans/2026-02-11-clew-viability-results.md
- Viability test plan: /Users/albertgwo/Work/evvy/docs/plans/2026-02-11-clew-viability-test-plan.md
- Earlier evaluation plan: /Users/albertgwo/Repositories/clew/docs/plans/2026-02-10-fix-evaluation-shortcomings.md
- Revised improvement plan: ~/.claude/plans/synthetic-doodling-kernighan.md
- Greptile blog: https://www.greptile.com/blog/semantic-codebase-search
- GitHub embedding model: https://www.infoq.com/news/2025/10/github-embedding-model/
- miniCOIL: https://qdrant.tech/articles/minicoil/
- ColBERT in Qdrant: https://qdrant.tech/articles/late-interaction-models/
- HyDE paper: https://arxiv.org/abs/2212.10496
- Qdrant code search tutorial: https://qdrant.tech/documentation/advanced-tutorials/code-search/
