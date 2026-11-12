from pathlib import Path

from rdflib import OWL, RDF, RDFS, BNode, Graph, Namespace, URIRef

BASE_DIR = Path(__file__).resolve().parent.parent
ONTOLOGY_PATH = BASE_DIR / "data" / "wittgenstein.owl"
OUTPUT_PATH = BASE_DIR / "data" / "wab_tractatus_subgraph.ttl"

WAB = Namespace("http://purl.org/wittgensteinsource/ont/")
INSTANCES = Namespace("http://purl.org/wittgensteinsource/ont/instances/")
HAS_AUTHOR = URIRef("http://purl.org/wittgensteinsource/ont/scholar/0.1/hasAuthor")

source = Graph()
source.parse(str(ONTOLOGY_PATH), format="xml")
print("Source triples:", len(source))

target = Graph()
target.bind("wab", WAB)
target.bind("inst", INSTANCES)
target.bind("rdf", RDF)
target.bind("rdfs", RDFS)
target.bind("owl", OWL)

QUERIES = [
    ("Q1 – triples involving W-TLP", """
PREFIX inst: <http://purl.org/wittgensteinsource/ont/instances/>
CONSTRUCT { ?s ?p ?o . }
WHERE { { inst:W-TLP ?p ?o . BIND(inst:W-TLP AS ?s) } UNION { ?s ?p inst:W-TLP . } }
"""),
    ("Q2 – hasPart neighbourhood", """
PREFIX wab:  <http://purl.org/wittgensteinsource/ont/>
PREFIX inst: <http://purl.org/wittgensteinsource/ont/instances/>
CONSTRUCT { ?part ?p ?o . ?s ?p2 ?part . }
WHERE { inst:W-TLP wab:hasPart ?part . { ?part ?p ?o . } UNION { ?s ?p2 ?part . } }
"""),
    ("Q3 – isPublishedInWork neighbourhood", """
PREFIX wab:  <http://purl.org/wittgensteinsource/ont/>
PREFIX inst: <http://purl.org/wittgensteinsource/ont/instances/>
CONSTRUCT { ?res ?p ?o . ?s ?p2 ?res . }
WHERE { ?res wab:isPublishedInWork inst:W-TLP . { ?res ?p ?o . } UNION { ?s ?p2 ?res . } }
"""),
    ("Q4 – isWorkPublishedFrom neighbourhood", """
PREFIX wab:  <http://purl.org/wittgensteinsource/ont/>
PREFIX inst: <http://purl.org/wittgensteinsource/ont/instances/>
CONSTRUCT { ?res ?p ?o . ?s ?p2 ?res . }
WHERE { inst:W-TLP wab:isWorkPublishedFrom ?res . { ?res ?p ?o . } UNION { ?s ?p2 ?res . } }
"""),
]

for label, query in QUERIES:
    before = len(target)
    for triple in source.query(query):
        target.add(triple)
    print(f"{label}: +{len(target) - before} (total {len(target)})")

for subject, _, _ in list(target):
    if isinstance(subject, URIRef):
        for author in source.objects(subject, HAS_AUTHOR):
            target.add((subject, HAS_AUTHOR, author))

print("After hasAuthor:", len(target))

Q5 = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
CONSTRUCT { ?entity rdf:type ?type .
            ?entity rdfs:label ?label .
            ?entity rdfs:comment ?comment .
            ?entity rdfs:subClassOf ?super .
            ?entity rdfs:domain ?domain .
            ?entity rdfs:range ?range . }
WHERE { VALUES ?entity { %s }
        OPTIONAL { ?entity rdf:type ?type }
        OPTIONAL { ?entity rdfs:label ?label }
        OPTIONAL { ?entity rdfs:comment ?comment }
        OPTIONAL { ?entity rdfs:subClassOf ?super }
        OPTIONAL { ?entity rdfs:domain ?domain }
        OPTIONAL { ?entity rdfs:range ?range } }
"""

declared = set()
walked = set()


def undeclared_entities():
    used = set()
    for node in target.subjects(None, None):
        used.add(node)
    for node in target.objects(None, None):
        used.add(node)
    for node in target.predicates(None, None):
        used.add(node)
    used.add(WAB.WittgensteinExternalSource)
    result = set()
    for node in used:
        if isinstance(node, URIRef) and node not in declared:
            result.add(node)
    return result


def copy_class_ancestors():
    for class_uri in list(target.objects(None, RDF.type)):
        if not isinstance(class_uri, URIRef):
            continue
        if class_uri in walked:
            continue
        walked.add(class_uri)
        queue = [class_uri]
        while queue:
            current = queue.pop(0)
            for parent in source.objects(current, RDFS.subClassOf):
                target.add((current, RDFS.subClassOf, parent))
                if isinstance(parent, URIRef) and parent not in walked:
                    queue.append(parent)


def declare_entities(entities):
    for i in range(0, len(entities), 200):
        batch = entities[i:i + 200]
        values = " ".join(f"<{entity}>" for entity in batch)
        for triple in source.query(Q5 % values):
            target.add(triple)


rounds = 0
while True:
    used = undeclared_entities()
    copy_class_ancestors()
    if not used:
        break
    declared.update(used)
    declare_entities(sorted(used, key=str))
    rounds += 1
print("Declaration rounds:", rounds)

for subject, predicate, obj in list(target):
    if predicate in (RDFS.domain, RDFS.range) and isinstance(obj, BNode):
        if not any(target.triples((obj, None, None))):
            target.remove((subject, predicate, obj))

print("Final subgraph:", len(target), "triples ->", OUTPUT_PATH.name)
target.serialize(destination=str(OUTPUT_PATH), format="turtle")
