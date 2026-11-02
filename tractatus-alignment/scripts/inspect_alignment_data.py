from pathlib import Path

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

FILES = {
    "Wittgensteiniana": DATA_DIR / "wittgensteiniana_final.ttl",
    "WAB": DATA_DIR / "wab_tractatus_subgraph.ttl",
}

for name, file_path in FILES.items():
    print(f"\n{'=' * 60}")
    print(name)
    print(f"{'=' * 60}")

    if not file_path.exists():
        print(f"File not found: {file_path}")
        continue

    graph = Graph()
    graph.parse(file_path, format="turtle")

    classes = set(graph.subjects(RDF.type, OWL.Class))
    object_properties = set(graph.subjects(RDF.type, OWL.ObjectProperty))
    datatype_properties = set(graph.subjects(RDF.type, OWL.DatatypeProperty))
    named_individuals = set(graph.subjects(RDF.type, OWL.NamedIndividual))

    typed_resources = {
        subject
        for subject, _, obj in graph.triples((None, RDF.type, None))
        if obj not in {OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty}
    }

    labels = set(graph.subjects(RDFS.label, None))
    labels.update(graph.subjects(SKOS.prefLabel, None))

    print(f"File: {file_path.name}")
    print(f"Triples: {len(graph):,}")
    print(f"OWL classes: {len(classes):,}")
    print(f"Object properties: {len(object_properties):,}")
    print(f"Datatype properties: {len(datatype_properties):,}")
    print(f"Named individuals: {len(named_individuals):,}")
    print(f"Other typed resources: {len(typed_resources):,}")
    print(f"Resources with labels: {len(labels):,}")

    print("\nClasses:")
    for item in sorted(classes, key=str)[:20]:
        print(" -", item)

    print("\nObject properties:")
    for item in sorted(object_properties, key=str)[:20]:
        print(" -", item)