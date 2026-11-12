import json
from pathlib import Path

from ontoaligner.aligner import AutoModelDecoderRAGLLM, RAG, SBERTRetrieval
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
BRIDGE = DATA_DIR / "tractatus_alignment_layer.ttl"
LLM_PATH = "Qwen/Qwen3-0.6B"
IR_PATH = "Qwen/Qwen3-Embedding-0.6B"


class QwenLLMBERTRetrieverRAG(RAG):
    Retrieval = SBERTRetrieval
    LLM = AutoModelDecoderRAGLLM


GLOSSES = {
    "Bemerkung": "remark / note, a single text fragment",
    "Werk": "work, book, publication",
    "WittgensteinSource": "Wittgenstein primary source, a creative work",
    "TextFragment": "text fragment, a single remark",
    "Book": "book",
    "CreativeWork": "creative work",
}

RETRIEVER_CONFIGS = {
    "wab2witt": {"device": "cuda", "top_k": 8, "threshold": 0.1},
    "witt2wab": {"device": "cuda", "top_k": 13, "threshold": 0.1},
}
LLM_CONFIG = {
    "device": "cuda",
    "batch_size": 32,
    "answer_set": {"yes": ["yes", "true"], "no": ["no", "false"]},
    "temperature": 1e-6,
    "top_p": 1.0,
    "num_beams": 1,
}
DIRECTIONS = {
    "wab2witt": (TEMP_DIR / "wab_doc.rdf", TEMP_DIR / "wittgensteiniana_doc.rdf"),
    "witt2wab": (TEMP_DIR / "wittgensteiniana_doc.rdf", TEMP_DIR / "wab_doc.rdf"),
}
SCHEMA = Namespace("https://schema.org/")


def local_name(uri):
    return str(uri).rsplit("/", 1)[-1].split("#")[-1]


def prepare_temp_ontologies():
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
        for class_uri in classes:
            gloss = GLOSSES.get(local_name(class_uri))
            if gloss:
                for label in list(graph.objects(class_uri, RDFS.label)):
                    graph.remove((class_uri, RDFS.label, label))
                    graph.add((class_uri, RDFS.label, Literal(f"{label} ({gloss})")))
        graph.serialize(destination=str(TEMP_DIR / f"{name.lower()}_doc.rdf"), format="xml")
        print(f"Prepared: {name}")


def canonical_pair(row):
    a, b = row["source"], row["target"]
    if str(b).startswith("http://purl.org/wittgensteinsource/"):
        a, b = b, a
    return (a, b)


def swapped(row):
    a, b = canonical_pair(row)
    return {"source": a, "target": b, "relation": row.get("relation", "=")}
