"""
Retrieval-based experiments (TF-IDF, BM25, optional SBERT) for
WAB -> Wittgensteiniana matching.

Root cause of the previous error `AttributeError: 'NoneType' object has no
attribute 'fit'`: in ontoaligner 1.9.4, `Retrieval` declares `model = None` as
a class attribute and `generate()` never calls `load()`. `TFIDFRetrieval.fit`
calls `self.model.fit(inputs)`, so the TF-IDF vectorizer must be created by an
explicit `aligner.load()` call before `generate()`. The same applies to
SBERTRetrieval (load must receive a model path). BM25Retrieval creates its
model inside fit(), but load() is called anyway for consistency.

Like the fuzzy experiments, the source graphs are read with RDFLib and
temporarily serialized to RDF/XML in temp/ for the OntoAligner parser.
The graphs are matched at the concept level (class names), so results are
lexical candidates, not semantic identifications.
"""

import json
import sys
from pathlib import Path

from ontoaligner import encoder, ontology
from ontoaligner.aligner import BM25Retrieval, SBERTRetrieval, TFIDFRetrieval
from rdflib import OWL, RDF, RDFS, Graph

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
TEMP_DIR = BASE_DIR / "temp"
RESULTS_DIR = BASE_DIR / "results" / "retrieval"

TEMP_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

FILES = {
    "WAB": DATA_DIR / "wab_tractatus_subgraph.ttl",
    "Wittgensteiniana": DATA_DIR / "wittgensteiniana_final.ttl",
}

TOP_K = 10
SBERT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def prepare_ontology(name, source_path):
    graph = Graph()
    graph.parse(str(source_path), format="turtle")

    classes = set(graph.subjects(RDF.type, OWL.Class))
    classes.update(graph.subjects(RDF.type, RDFS.Class))

    for class_uri in classes:
        graph.add((class_uri, RDF.type, OWL.Class))

    xml_path = TEMP_DIR / f"{name.lower()}_retrieval.rdf"
    graph.serialize(destination=str(xml_path), format="xml")

    parser = ontology.GenericOntology()
    return parser.parse(str(xml_path))


source_data = prepare_ontology("WAB", FILES["WAB"])
target_data = prepare_ontology("Wittgensteiniana", FILES["Wittgensteiniana"])

print("WAB entities:", len(source_data))
print("Wittgensteiniana entities:", len(target_data))

concept_encoder = encoder.ConceptLightweightEncoder()

encoded_data = concept_encoder(
    source=source_data,
    target=target_data,
)

print("Encoded source:", len(encoded_data[0]))
print("Encoded target:", len(encoded_data[1]))


def run(name, aligner, load=None):
    print(f"\nRunning {name}...")

    # Required fix: retrieval models must be loaded before generate().
    # Otherwise self.model stays None and fit() raises AttributeError.
    if load is not None:
        aligner.load(load)
    else:
        aligner.load()

    results = aligner.generate(input_data=encoded_data)

    output_path = RESULTS_DIR / f"{name}.json"

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(
            results,
            file,
            ensure_ascii=False,
            indent=4,
            default=str,
        )

    print("Number of matched sources:", len(results))
    print("Results saved to:", output_path)


for name, aligner in {
    "tfidf": TFIDFRetrieval(top_k=TOP_K),
    "bm25": BM25Retrieval(top_k=TOP_K),
}.items():
    run(name, aligner)

print("\nRetrieval experiments completed.")

# Optional SBERT experiment: downloads the model on first use.
if "--sbert" in sys.argv:
    run(
        "sbert",
        SBERTRetrieval(top_k=TOP_K),
        load=SBERT_MODEL,
    )
    print("SBERT experiment completed.")
