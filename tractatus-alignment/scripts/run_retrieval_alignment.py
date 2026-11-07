"""
Retrieval alignment WAB <-> Wittgensteiniana with OntoAligner only.

Classes are encoded as documents (label + synonyms + comments from the base
graphs merged with the rdfs:comment overlays) and matched with
TFIDFRetrieval, BM25Retrieval and SBERTRetrieval. Both directions are run;
pairs predicted in BOTH directions (threshold intersection and top1 x top1)
are reported as bidirectionally confirmed. Results are graded against the
draft reference alignment (data/reference_alignment.json).
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
    for path in (*paths, BRIDGE):
        graph.parse(str(path), format="turtle")
    classes = (set(graph.subjects(RDF.type, OWL.Class))
               | set(graph.subjects(RDF.type, RDFS.Class)))
    for class_uri in classes:
        graph.add((class_uri, RDF.type, OWL.Class))
    xml_path = TEMP_DIR / f"{name.lower()}_doc.rdf"
    graph.serialize(destination=str(xml_path), format="xml")
    prepared[name] = ontology.GenericOntology().parse(str(xml_path))

DIRECTIONS = {
    "wab2witt": (prepared["WAB"], prepared["Wittgensteiniana"]),
    "witt2wab": (prepared["Wittgensteiniana"], prepared["WAB"]),
}


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


def is_wab(uri):
    return str(uri).startswith(("wab:", "scholar:"))


def canonicalize(pair):
    """Canonical orientation: (WAB term, Wittgensteiniana term)."""
    a, b = pair
    return (a, b) if is_wab(a) else (b, a)


def pair_sets(predictions):
    """Canonical (WAB, Witt) pairs per threshold, plus the top-1 pairs."""
    per_threshold = {str(t): set() for t in THRESHOLDS}
    top1 = set()
    for row in predictions:
        candidates = list(zip(row["target-cands"], row["score-cands"]))
        for cand, score in candidates:
            pair = canonicalize((short(row["source"]), short(cand)))
            for t in THRESHOLDS:
                if score >= t:
                    per_threshold[str(t)].add(pair)
        if candidates:
            top1.add(canonicalize((short(row["source"]), short(candidates[0][0]))))
    return per_threshold, top1


reference = json.load(open(DATA_DIR / "reference_alignment.json", encoding="utf-8"))
gold = {(short(m["source"]), short(m["target"])) for m in reference["class_mappings"]}


def score(pairs):
    hits = pairs & gold
    precision = len(hits) / len(pairs) if pairs else 0.0
    recall = len(hits) / len(gold)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"size": len(pairs),
            "hits": sorted(f"{s} -> {t}" for s, t in hits),
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3)}


runs = {}  # name -> {"wab2witt": {...}, "witt2wab": {...}}
for name, aligner_cls in (
    ("tfidf_doc", TFIDFRetrieval),
    ("bm25_doc", BM25Retrieval),
    ("sbert_doc", SBERTRetrieval),
):
    runs[name] = {}
    for direction, (source_data, target_data) in DIRECTIONS.items():
        # top_k must not exceed the number of target concepts
        aligner = aligner_cls(top_k=len(target_data))
        if aligner_cls is SBERTRetrieval:
            aligner.load(SBERT_MODEL)
        else:
            aligner.load()
        encoded = encoder.DocConceptLightweightEncoder()(source=source_data,
                                                         target=target_data)
        predictions = aligner.generate(input_data=encoded)

        suffix = "" if direction == "wab2witt" else "_rev"
        with open(RESULTS_DIR / f"{name}{suffix}.json", "w", encoding="utf-8") as file:
            json.dump(predictions, file, ensure_ascii=False, indent=4, default=str)

        per_threshold, top1 = pair_sets(predictions)
        runs[name][direction] = {"per_threshold": per_threshold, "top1": top1}
        print(f"{name}/{direction}: top1 pairs {len(top1)}")

# bidirectional agreement: predicted in both directions
bidirectional = {}
for name, directions in runs.items():
    fw, rev = directions["wab2witt"], directions["witt2wab"]
    entry = {"per_threshold": {},
             "top1_x_top1": {
                 "fw": score(fw["top1"]),
                 "rev": score(rev["top1"]),
                 "both": score(fw["top1"] & rev["top1"]),
             }}
    for t in THRESHOLDS:
        fw_set, rev_set = fw["per_threshold"][str(t)], rev["per_threshold"][str(t)]
        entry["per_threshold"][str(t)] = {
            "fw": score(fw_set),
            "rev": score(rev_set),
            "both": score(fw_set & rev_set),
        }
    bidirectional[name] = entry

    print(f"\n=== {name} (bidirectional) ===")
    for mode, stats in (("top1_x_top1", entry["top1_x_top1"]),):
        for variant in ("fw", "rev", "both"):
            s = stats[variant]
            print(f"  {mode}/{variant}: n={s['size']} P={s['precision']} "
                  f"R={s['recall']} F1={s['f1']}")
    for t in THRESHOLDS:
        both = entry["per_threshold"][str(t)]["both"]
        print(f"  t={t}: both n={both['size']} P={both['precision']} "
              f"R={both['recall']} F1={both['f1']}")

with open(RESULTS_DIR / "bidirectional_doc.json", "w", encoding="utf-8") as file:
    json.dump(bidirectional, file, ensure_ascii=False, indent=2, default=str)
print("\nBidirectional report saved -> bidirectional_doc.json")
