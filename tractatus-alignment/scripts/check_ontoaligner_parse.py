"""
Smoke test: check that OntoAligner parses both prepared ontologies correctly.
"""

from pathlib import Path

from rdflib import OWL, RDF, RDFS, Graph, Namespace
from ontoaligner import ontology

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
TEMP_DIR = BASE_DIR / "temp"
TEMP_DIR.mkdir(exist_ok=True)

SCHEMA = Namespace("https://schema.org/")

files = {
    "Wittgensteiniana": DATA_DIR / "wittgensteiniana_final.ttl",
    "WAB": DATA_DIR / "wab_tractatus_subgraph.ttl",
}

for name, source_path in files.items():
    graph = Graph()
    graph.parse(str(source_path), format="turtle")

    classes = set(graph.subjects(RDF.type, OWL.Class)) | set(graph.subjects(RDF.type, RDFS.Class))
    for class_uri in classes:
        graph.add((class_uri, RDF.type, OWL.Class))
        if not list(graph.objects(class_uri, RDFS.label)):
            for label in graph.objects(class_uri, SCHEMA.name):
                graph.add((class_uri, RDFS.label, label))

    xml_path = TEMP_DIR / f"{name.lower()}.rdf"
    graph.serialize(destination=str(xml_path), format="xml")

    parsed = ontology.GenericOntology().parse(str(xml_path))
    print(f"{name}: prepared {len(classes)} classes, extracted {len(parsed)}")
    for item in parsed:
        print(f"  {item['name']} | label={item['label']} | parents={item['parents']}")
