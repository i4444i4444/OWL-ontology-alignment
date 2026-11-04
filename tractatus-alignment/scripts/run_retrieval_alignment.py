"""
Retrieval alignment WAB -> Wittgensteiniana with OntoAligner only.

Classes are encoded as documents (label + synonyms + comments from the base
graphs merged with the rdfs:comment overlays) and matched with
TFIDFRetrieval, BM25Retrieval and SBERTRetrieval. The propositions bridge
overlay is merged into both sides before encoding. Results are graded against
the draft reference alignment (data/reference_alignment.json).
"""

import json
from pathlib import Path

from ontoaligner import encoder, ontology
from ontoaligner.aligner import BM25Retrieval, SBERTRetrieval, TFIDFRetrieval
from rdflib import OWL, RDF, RDFS, Graph, Namespace

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
TEMP_DIR = BASE_DIR / "temp"
RESULTS_DIR = BASE_DIR / "results" / "retrieval"
TEMP_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

FILES = {
    "WAB": (DATA_DIR / "wab_tractatus_subgraph.ttl", DATA_DIR / "wab_tractatus_comments.ttl"),
    "Wittgensteiniana": (
        DATA_DIR / "wittgensteiniana_final.ttl",
        DATA_DIR / "wittgensteiniana_comments.ttl",
    ),
}
# bridge overlay: merged into both ontologies so the shared TractatusProposition
# individuals (built by normalize_propositions.py) link the two sides
BRIDGE = DATA_DIR / "tractatus_alignment_layer.ttl"
SBERT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]

prepared = {}
for name, paths in FILES.items():
    graph = Graph()
    for path in paths:
        graph.parse(str(path), format="turtle")
    graph.parse(str(BRIDGE), format="turtle")
    classes = (set(graph.subjects(RDF.type, OWL.Class))
               | set(graph.subjects(RDF.type, RDFS.Class)))
    for class_uri in classes:
        graph.add((class_uri, RDF.type, OWL.Class))
    xml_path = TEMP_DIR / f"{name.lower()}_doc.rdf"
    graph.serialize(destination=str(xml_path), format="xml")
    prepared[name] = ontology.GenericOntology().parse(str(xml_path))

source_data = prepared["WAB"]
target_data = prepared["Wittgensteiniana"]
print("WAB concepts:", len(source_data), "| Wittgensteiniana concepts:", len(target_data))

encoded_data = encoder.DocConceptLightweightEncoder()(source=source_data, target=target_data)

results = {}
for name, aligner in (
    ("tfidf_doc", TFIDFRetrieval(top_k=10)),
    ("bm25_doc", BM25Retrieval(top_k=10)),
    # top_k must not exceed the number of target concepts (8 here)
    ("sbert_doc", SBERTRetrieval(top_k=len(target_data))),
):
    if hasattr(aligner, "model") and name == "sbert_doc":
        aligner.load(SBERT_MODEL)
    else:
        aligner.load()
    results[name] = aligner.generate(input_data=encoded_data)
    with open(RESULTS_DIR / f"{name}.json", "w", encoding="utf-8") as file:
        json.dump(results[name], file, ensure_ascii=False, indent=4, default=str)
    print(f"{name}: {len(results[name])} matched sources, saved")


def short(uri):
    uri = str(uri)
    for prefix, base in (
        ("wab:", "http://purl.org/wittgensteinsource/ont/"),
        ("scholar:", "http://purl.org/wittgensteinsource/ont/scholar/0.1/"),
        ("ex:", "http://example.org/wittgensteiniana/"),
        ("align:", "http://example.org/tractatus-alignment/"),
        ("schema:", "https://schema.org/"),
    ):
        if uri.startswith(base):
            return prefix + uri[len(base):]
    return uri


reference = json.load(open(DATA_DIR / "reference_alignment.json", encoding="utf-8"))
gold = {(short(m["source"]), short(m["target"])) for m in reference["class_mappings"]}

evaluation = {}
for name, predictions in results.items():
    scores = [score for row in predictions for score in row["score-cands"]]
    top1 = [{
        "source": short(row["source"]),
        "target": short(row["target-cands"][0]),
        "score": round(float(row["score-cands"][0]), 4),
        "in_reference": (short(row["source"]), short(row["target-cands"][0])) in gold,
    } for row in predictions]

    entry = {
        "top1": top1,
        "top1_correct": [row for row in top1 if row["in_reference"]],
        "score_stats": {"total": len(scores), "nonzero": sum(1 for s in scores if s)},
        "per_threshold": {},
    }

    if name != "bm25_doc":  # BM25 scores are not normalized
        for threshold in THRESHOLDS:
            predicted = {(short(row["source"]), short(t))
                         for row in predictions
                         for t, score in zip(row["target-cands"], row["score-cands"])
                         if score >= threshold}
            hits = predicted & gold
            precision = len(hits) / len(predicted) if predicted else 0.0
            recall = len(hits) / len(gold) if gold else 0.0
            f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
            entry["per_threshold"][str(threshold)] = {
                "predicted": len(predicted),
                "hits": sorted(hits),
                "precision": round(precision, 3),
                "recall": round(recall, 3),
                "f1": round(f1, 3),
            }

    evaluation[name] = entry
    print(f"\n=== {name} ===")
    for row in top1:
        flag = "HIT" if row["in_reference"] else "   "
        print(f"  [{flag}] {row['source']} -> {row['target']} ({row['score']})")
    for threshold, row in entry["per_threshold"].items():
        print(f"  t={threshold}: P={row['precision']} R={row['recall']} F1={row['f1']}")

with open(RESULTS_DIR / "eval_doc.json", "w", encoding="utf-8") as file:
    json.dump(evaluation, file, ensure_ascii=False, indent=2, default=str)
print("\nEvaluation saved -> eval_doc.json")
