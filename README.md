# OWL Ontology Alignment

This project focuses on the **semantic alignment of the Wittgensteiniana and WAB ontologies**, which represent knowledge related to Tractatus Logico Philosophicus by Ludwig Wittgenstein.

The main objective is to identify semantic correspondences between entities in the two ontologies, analyze the results of ontology matching, and investigate how different knowledge representation models can be aligned.

## Objectives

- Analyze the structure and content of the Wittgensteiniana and WAB ontologies.
- Apply ontology matching methods to discover semantic correspondences.
- Explore the use of OntoAligner for ontology alignment.
- Evaluate and interpret the resulting mappings.
- Examine structural and semantic differences between the ontologies.

## Ontologies

### Wittgensteiniana

Wittgensteiniana uses RDF to describe Ludwig Wittgenstein's Tractatus Logico-Philosophicus. It provides a representation of philosophical concepts and textual resources associated with the work.

### WAB (Wittgenstein Archives at the University of Bergen)

An ontology developed in the context of the Wittgenstein Archives. This project focuses on the representation of resources related to Wittgenstein's Tractatus Logico-Philosophicus.

## Methodology

The project follows several stages:

1. **Ontology inspection** - examining the structure, classes, properties, and resources of both ontologies.
2. **Ontology preparation** - selecting and preparing relevant ontology entities for matching.
3. **Semantic alignment** - applying ontology matching methods to identify potential correspondences.
4. **Mapping analysis** - examining the generated correspondences and assessing their semantic validity.
5. **Results evaluation** - documenting the findings, limitations, and differences between the ontologies.

## Technologies

- Python
- OWL and RDF
- RDFLib
- SPARQL
- OntoAligner

## Project Status

The project reached the alignment stage: the LLM-based RAG alignment
(OntoAligner LLMs4OM guide) is implemented and evaluated in both directions
against a hand-checked OAEI-style reference. Pure retrieval experiments
(TF-IDF, BM25, SBERT baselines) served as early baselines and were removed;
the RAG pipeline performs its own retrieval internally.

## Results

Class-alignment quality against the 6-pair reference (`data/reference.xml`),
both-directions agreement (pairs confirmed forward and reverse):

| Config | Precision | Recall | F1 |
|---|---|---|---|
| RAG + heuristic postprocessor | 33.3 | 50.0 | 40.0 |
| RAG + hybrid postprocessor | 100.0 | 33.3 | 50.0 |
| best single direction (hybrid, witt2wab) | 57.1 | 66.7 | 61.5 |

Setup: retriever `Qwen/Qwen3-Embedding-0.6B`, LLM `Qwen/Qwen3-0.6B` (fp16),
`ConceptParentRAGEncoder`, all retrieval candidates given to the LLM,
requirements from the OntoAligner RAG documentation. An 8-bit quantized
`Qwen3-1.7B` was tested but scored far below the fp16 0.6B setup.

## Repository layout

```
tractatus-alignment/
  data/                       ontologies, prepared subgraphs, three overlay files
    (two comment overlays, one propositions bridge) 
  preprocessing/              Wittgensteiniana preprocessing scripts
    cache/                    (ignored) source data and pipeline intermediates
  temp/                       (ignored) RDF/XML conversions regenerable from data/
  results/                    alignment experiment outputs (json)
  scripts/                    extraction, normalization, alignment and verification
```

`data/wittgenstein.owl` (WAB) is committed once; the Wittgensteiniana source and
intermediates live (ignored) in `preprocessing/cache/` and can be re-fetched from
the links below.

The three overlay files in `data/` supplement the two base ontologies: two
`*_comments.ttl` files add documentation to their respective ontology, and
`tractatus_alignment_layer.ttl` (built by `scripts/normalize_propositions.py`
from shared Tractatus proposition numbers) is merged into BOTH ontologies when
running OntoAligner, so the shared `align:TractatusProposition` individuals link
the two sides together.

## Sources

- [Wittgenstein Archives at the University of Bergen](https://wab.uib.no/)
- [Wittgensteiniana RDF dataset](https://github.com/lambdamusic/wittgensteiniana/blob/main/backups/rdf/wittgensteiniana.ttl) — RDF data used as a source for the analysis.
- [Wittgensteiniana repository](https://github.com/lambdamusic/wittgensteiniana) — original project and additional information.
