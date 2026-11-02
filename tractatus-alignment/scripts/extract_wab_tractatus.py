from collections import deque
from pathlib import Path

from rdflib import OWL, RDF, RDFS, Graph, Namespace, URIRef

BASE_DIR = Path(__file__).resolve().parent.parent
ONTOLOGY_PATH = BASE_DIR / "data" / "wittgenstein.owl"

WAB = Namespace("http://purl.org/wittgensteinsource/ont/")
INSTANCES = Namespace("http://purl.org/wittgensteinsource/ont/instances/")
TRACTATUS_URI = INSTANCES["W-TLP"]
PROTOTRACTATUS_URI = INSTANCES["W-PT"]

source = Graph()
source.parse(str(ONTOLOGY_PATH), format="xml")

if not ONTOLOGY_PATH.exists():
    raise FileNotFoundError(f"Ontology file not found: {ONTOLOGY_PATH}")

print(f"\nPath: {ONTOLOGY_PATH!s}")

print(f"\nAmount of triples: {len(source)}")

print("\nW-TLP exists:")
print((TRACTATUS_URI, RDF.type, WAB.Werk) in source)

print("\nW-P exists:")
print((TRACTATUS_URI, RDF.type, WAB.Werk) in source)

HAS_PART = URIRef(WAB + "hasPart")

parts = list(source.objects(TRACTATUS_URI, HAS_PART))

print(f"\nNumber of direct parts: {len(parts)}")

works = {
    "W-TLP": TRACTATUS_URI,
    "W-PT": PROTOTRACTATUS_URI
}

for name, work_uri in works.items():
    parts = list(source.objects(work_uri, HAS_PART))

    print(f"\n{name}")
    print(f"Number of direct parts: {len(parts)}")

    for part in parts[:10]:
        labels = list(source.objects(part, RDFS.label))
        types = list(source.objects(part, RDF.type))

        print(f"\nResource: {part}")
        print(f"Label: {labels}")
        print(f"Types: {types}")