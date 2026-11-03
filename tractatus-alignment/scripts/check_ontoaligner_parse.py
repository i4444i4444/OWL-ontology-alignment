from pathlib import Path
from rdflib import Graph, RDF, OWL, RDFS, Namespace
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
    print(f"\n{'=' * 60}")
    print(name)

    graph = Graph()
    graph.parse(str(source_path), format="turtle")

    classes = set(graph.subjects(RDF.type, OWL.Class))
    classes.update(graph.subjects(RDF.type, RDFS.Class))

    for class_uri in classes:
        graph.add((class_uri, RDF.type, OWL.Class))

        if not list(graph.objects(class_uri, RDFS.label)):
            for label in graph.objects(class_uri, SCHEMA.name):
                graph.add((class_uri, RDFS.label, label))

    print("Classes prepared:", len(classes))

    xml_path = TEMP_DIR / f"{name.lower()}.rdf"
    graph.serialize(destination=str(xml_path), format="xml")

    parser = ontology.GenericOntology()
    parsed_data = parser.parse(str(xml_path))

    print("Classes extracted:", len(parsed_data))

    for item in parsed_data:
        print({
            "name": item["name"],
            "label": item["label"],
            "iri": item["iri"],
            "parents": item["parents"],
        })
