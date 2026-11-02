
from pathlib import Path
from rdflib import Graph, RDF, RDFS, OWL, Literal

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

FILES = {
    "Wittgensteiniana": DATA_DIR / "wittgensteiniana_final.ttl",
    "WAB": DATA_DIR / "wab_tractatus_subgraph.ttl",
}

for name, path in FILES.items():
    print(f"\n{'=' * 70}")
    print(name)
    print("=" * 70)

    graph = Graph()
    graph.parse(str(path), format="turtle")

    print("\n1. CLASS INSTANCE COUNTS")

    classes = set(graph.subjects(RDF.type, OWL.Class))
    classes.update(graph.subjects(RDF.type, RDFS.Class))

    for cls in sorted(classes, key=str):
        instances = set(graph.subjects(RDF.type, cls))
        print(f"{cls.split('/')[-1].split('#')[-1]}: {len(instances)}")

    print("\n2. PROPERTIES WITH LITERAL VALUES")

    datatype_properties = set(
        graph.subjects(RDF.type, OWL.DatatypeProperty)
    )

    for prop in sorted(datatype_properties, key=str):
        triples = [
            (s, o)
            for s, p, o in graph.triples((None, prop, None))
            if isinstance(o, Literal)
        ]

        if triples:
            print(f"\nProperty: {prop}")
            print("Literal values:", len(triples))

            for subject, value in triples[:3]:
                print("Subject:", subject)
                print("Value:", str(value)[:250])

    print("\n3. RESOURCES WITH TEXT-RELATED NAMES")

    keywords = (
        "thesis", "text", "fragment", "bemerkung",
        "satz", "proposition", "remark", "work"
    )

    resources = set()

    for subject, predicate, obj in graph:
        if isinstance(subject, Literal):
            continue

        if any(word in str(subject).lower() for word in keywords):
            resources.add(subject)

        if isinstance(obj, Literal):
            if any(word in str(obj).lower() for word in keywords):
                resources.add(subject)

    for resource in sorted(resources, key=str)[:30]:
        print("\nResource:", resource)

        for predicate, obj in graph.predicate_objects(resource):
            print(" ", predicate, "->", str(obj)[:200])
