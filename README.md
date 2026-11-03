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
- Pandas
- Seaborn
- Jupyter Notebook
- OntoAligner

## Project Status

The project is currently in the ontology inspection and preparation stage. The next stage is to perform semantic alignment experiments and analyze the resulting mappings.

## Repository layout

```
ontology-download/            download + preprocessing scripts for the source datasets
  cache/                      (ignored) downloaded sources and pipeline intermediates
tractatus-alignment/
  data/                       ontologies, prepared subgraphs and comment overlays
  temp/                       (ignored) RDF/XML conversions regenerable from data/
  notebooks/                  inspection notebooks (one per dataset)
  results/                    alignment experiment outputs (json)
  scripts/                    experiment and inspection scripts
```

External ontologies are downloaded, not committed as duplicates: `data/wittgenstein.owl`
(WAB) is stored once in `tractatus-alignment/data/`; `ontology-download/cache/` holds the
re-downloadable Wittgensteiniana sources. To fetch both from the web run the scripts in
`ontology-download/`.

## Sources

- [Wittgenstein Archives at the University of Bergen](https://wab.uib.no/)
- [Wittgensteiniana RDF dataset](https://github.com/lambdamusic/wittgensteiniana/blob/main/backups/rdf/wittgensteiniana.ttl) — RDF data used as a source for the analysis.
- [Wittgensteiniana repository](https://github.com/lambdamusic/wittgensteiniana) — original project and additional information.
