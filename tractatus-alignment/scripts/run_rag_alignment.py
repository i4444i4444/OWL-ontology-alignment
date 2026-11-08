"""
RAG alignment WAB <-> Wittgensteiniana with OntoAligner, following the official
OntoAligner RAG guide (LLMs4OM): GenericOMDataset collection, RAGEncoders,
Qwen3-0.6B LLM with Qwen3-Embedding-0.6B retriever, heuristic + hybrid
postprocessing and XML export. Both directions are run; pairs accepted in
both directions are reported as bidirectionally confirmed.
"""

import json
from pathlib import Path

from ontoaligner import ontology
from ontoaligner.aligner import AutoModelDecoderRAGLLM, RAG, SBERTRetrieval
from ontoaligner.encoder import ConceptParentRAGEncoder
from ontoaligner.postprocess import (
    rag_heuristic_postprocessor,
    rag_hybrid_postprocessor,
)
from ontoaligner.utils import metrics, xmlify
from rdflib import OWL, RDF, RDFS, Graph, Literal, Namespace

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
TEMP_DIR = BASE_DIR / "temp"
RESULTS_DIR = BASE_DIR / "results" / "rag"
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
LLM_PATH = "Qwen/Qwen3-0.6B"
IR_PATH = "Qwen/Qwen3-Embedding-0.6B"


class QwenLLMBERTRetrieverRAG(RAG):
    Retrieval = SBERTRetrieval
    LLM = AutoModelDecoderRAGLLM


# prepare temp RDF/XML versions of the ontologies for the OntoAligner parsers
# Retrieval uses ONLY the class label (ConceptLightweightEncoder: owl["label"]).
# Add short cross-language glosses so the two vocabularies can meet:
# German WAB terms vs English schema terms. Facts only, no gold-leaking.
GLOSSES = {
    "Bemerkung": "remark / note, a single text fragment",
    "Werk": "work, book, publication",
    "WittgensteinSource": "Wittgenstein primary source, a creative work",
    "TextFragment": "text fragment, a single remark",
    "Book": "book",
    "CreativeWork": "creative work",
}

SCHEMA = Namespace("https://schema.org/")
for name, paths in FILES.items():
    graph = Graph()
    for path in (*paths, BRIDGE):
        graph.parse(str(path), format="turtle")
    classes = (set(graph.subjects(RDF.type, OWL.Class))
               | set(graph.subjects(RDF.type, RDFS.Class)))
    for class_uri in classes:
        graph.add((class_uri, RDF.type, OWL.Class))
        if not list(graph.objects(class_uri, RDFS.label)):
            for label in graph.objects(class_uri, SCHEMA.name):
                graph.add((class_uri, RDFS.label, label))
    # append glosses to labels (temp files only, source ontologies untouched)
    local = lambda uri: str(uri).rsplit("/", 1)[-1].split("#")[-1]
    for class_uri in classes:
        gloss = GLOSSES.get(local(class_uri))
        if gloss:
            for label in list(graph.objects(class_uri, RDFS.label)):
                graph.remove((class_uri, RDFS.label, label))
                graph.add((class_uri, RDFS.label, Literal(f"{label} ({gloss})")))
    graph.serialize(destination=str(TEMP_DIR / f"{name.lower()}_doc.rdf"), format="xml")
    print(f"Prepared: {name}")

# top_k must not exceed the number of target classes in each direction
# (torch.topk would fail otherwise): wab2witt has 9 Witt targets,
# witt2wab has 13 WAB targets -> give the retriever every candidate.
RETRIEVER_CONFIGS = {
    "wab2witt": {"device": "cuda", "top_k": 9, "threshold": 0.1},
    "witt2wab": {"device": "cuda", "top_k": 13, "threshold": 0.1},
}
LLM_CONFIG = {
    "device": "cuda",
    "batch_size": 32,
    "answer_set": {"yes": ["yes", "true"], "no": ["no", "false"]},
    # a load_in_8bit quantized Qwen3-1.7B was tested (built-in flag) but scored
    # far below this fp16 0.6B config on 4 GB VRAM, so fp16 stays.
}
DIRECTIONS = {
    "wab2witt": (TEMP_DIR / "wab_doc.rdf", TEMP_DIR / "wittgensteiniana_doc.rdf"),
    "witt2wab": (TEMP_DIR / "wittgensteiniana_doc.rdf", TEMP_DIR / "wab_doc.rdf"),
}


def canonical_pair(row):
    """(row.source, row.target) in canonical (WAB, Wittgensteiniana) order."""
    a, b = row["source"], row["target"]
    if str(b).startswith(("http://purl.org/wittgensteinsource/",)):
        a, b = b, a
    return (a, b)


def swapped(row):
    """Predicted row from the reverse direction in canonical orientation."""
    a, b = canonical_pair(row)
    return {"source": a, "target": b, "relation": row.get("relation", "=")}


task = ontology.GenericOMDataset()
datasets = {
    key: task.collect(
        source_ontology_path=str(source),
        target_ontology_path=str(target),
        reference_matching_path=str(DATA_DIR / "reference.xml"),
    )
    for key, (source, target) in DIRECTIONS.items()
}

reference = datasets["wab2witt"]["reference"]

for encoder_name, encoder_model in (
    ("concept_parent", ConceptParentRAGEncoder()),
    # concept_children encoder was tested as a checkpoint: pair sets turned out
    # ~95% identical with no accuracy gain, so it was dropped for simplicity.
):
    run_dir = RESULTS_DIR / encoder_name
    run_dir.mkdir(parents=True, exist_ok=True)

    positives = {}  # mode -> {"wab2witt": [...], "witt2wab": [...]}
    for direction, dataset in datasets.items():
        encoded = encoder_model(source=dataset["source"], target=dataset["target"])

        model = QwenLLMBERTRetrieverRAG(retriever_config=RETRIEVER_CONFIGS[direction],
                                        llm_config=LLM_CONFIG)
        model.load(llm_path=LLM_PATH, ir_path=IR_PATH)
        predicts = model.generate(input_data=encoded)

        dir_dir = run_dir / direction
        dir_dir.mkdir(parents=True, exist_ok=True)
        with open(dir_dir / "predictions.json", "w", encoding="utf-8") as file:
            json.dump(predicts, file, ensure_ascii=False, indent=4, default=str)

        matched_files = {}
        for mode, postprocessor in (
            ("heuristic", rag_heuristic_postprocessor),
            ("hybrid", rag_hybrid_postprocessor),
        ):
            if mode == "heuristic":
                matchings, _ = postprocessor(predicts=predicts,
                                             topk_confidence_ratio=3,
                                             topk_confidence_score=3)
            else:
                matchings, _ = postprocessor(predicts=predicts,
                                             ir_score_threshold=0.1,
                                             llm_confidence_th=0.8)
            with open(dir_dir / f"{mode}_matchings.json", "w", encoding="utf-8") as file:
                json.dump(matchings, file, ensure_ascii=False, indent=4, default=str)
            xml_str = xmlify.xml_alignment_generator(matchings=matchings)
            with open(dir_dir / f"{mode}_matchings.xml", "w", encoding="utf-8") as file:
                file.write(xml_str)
            matched_files[mode] = matchings

        positives[direction] = matched_files
        print(f"{encoder_name}/{direction}: heuristic {len(matched_files['heuristic'])}, "
              f"hybrid {len(matched_files['hybrid'])}")

    # bidirectional agreement: accepted in both directions, canonical orientation
    bidirectional = {}
    for mode in ("heuristic", "hybrid"):
        fw_rows = [swapped(r) for r in positives["wab2witt"][mode]]
        rev_rows = [swapped(r) for r in positives["witt2wab"][mode]]
        fw_pairs = {canonical_pair(r) for r in fw_rows}
        rev_pairs = {canonical_pair(r) for r in rev_rows}
        both_rows = [{"source": s, "target": t, "relation": "="}
                     for s, t in sorted(fw_pairs & rev_pairs, key=str)]
        entry = {"fw": metrics.evaluation_report(predicts=fw_rows, references=reference),
                 "rev": metrics.evaluation_report(predicts=rev_rows, references=reference),
                 "both": metrics.evaluation_report(predicts=both_rows, references=reference)}
        bidirectional[mode] = entry
        with open(run_dir / f"bidirectional_{mode}.json", "w", encoding="utf-8") as file:
            json.dump(both_rows, file, ensure_ascii=False, indent=4, default=str)
        with open(run_dir / f"bidirectional_{mode}.xml", "w", encoding="utf-8") as file:
            file.write(xmlify.xml_alignment_generator(matchings=both_rows))
        print(f"\n=== {encoder_name} / {mode} bidirectional ===")
        print(" fw:", entry["fw"])
        print(" rev:", entry["rev"])
        print(" both:", entry["both"])

    with open(run_dir / "bidirectional_summary.json", "w", encoding="utf-8") as file:
        json.dump(bidirectional, file, ensure_ascii=False, indent=4, default=str)

print("\nSaved -> results/rag/")
