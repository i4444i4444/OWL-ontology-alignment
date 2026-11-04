"""
Extract the WAB subgraph around the Tractatus (W-TLP) from wittgenstein.owl
with SPARQL CONSTRUCT queries: the work itself, its parts, everything
published in/from it, authors, class hierarchy and schema declarations.
"""

from pathlib import Path

from rdflib import OWL, RDF, RDFS, BNode, Graph, Namespace, URIRef

BASE_DIR = Path(__file__).resolve().parent.parent
ONTOLOGY_PATH = BASE_DIR / "data" / "wittgenstein.owl"
OUTPUT_PATH = BASE_DIR / "data" / "wab_tractatus_subgraph.ttl"

WAB = Namespace("http://purl.org/wittgensteinsource/ont/")
INSTANCES = Namespace("http://purl.org/wittgensteinsource/ont/instances/")

source = Graph()
source.parse(str(ONTOLOGY_PATH), format="xml")
print("Source triples:", len(source))

target = Graph()
target.bind("wab", WAB)
target.bind("inst", INSTANCES)
target.bind("rdf", RDF)
target.bind("rdfs", RDFS)
target.bind("owl", OWL)

Q1 = """
PREFIX inst: <http://purl.org/wittgensteinsource/ont/instances/>
CONSTRUCT { ?s ?p ?o . }
WHERE { { inst:W-TLP ?p ?o . BIND(inst:W-TLP AS ?s) } UNION { ?s ?p inst:W-TLP . } }
"""

Q2 = """
PREFIX wab:  <http://purl.org/wittgensteinsource/ont/>
PREFIX inst: <http://purl.org/wittgensteinsource/ont/instances/>
CONSTRUCT { ?part ?p ?o . ?s ?p2 ?part . }
WHERE { inst:W-TLP wab:hasPart ?part . { ?part ?p ?o . } UNION { ?s ?p2 ?part . } }
"""

Q3 = """
PREFIX wab:  <http://purl.org/wittgensteinsource/ont/>
PREFIX inst: <http://purl.org/wittgensteinsource/ont/instances/>
CONSTRUCT { ?res ?p ?o . ?s ?p2 ?res . }
WHERE { ?res wab:isPublishedInWork inst:W-TLP . { ?res ?p ?o . } UNION { ?s ?p2 ?res . } }
"""

Q4 = """
PREFIX wab:  <http://purl.org/wittgensteinsource/ont/>
PREFIX inst: <http://purl.org/wittgensteinsource/ont/instances/>
CONSTRUCT { ?res ?p ?o . ?s ?p2 ?res . }
WHERE { inst:W-TLP wab:isWorkPublishedFrom ?res . { ?res ?p ?o . } UNION { ?s ?p2 ?res . } }
"""

for label, query in (
    ("Q1 – triples involving W-TLP", Q1),
    ("Q2 – hasPart neighbourhood", Q2),
    ("Q3 – isPublishedInWork neighbourhood", Q3),
    ("Q4 – isWorkPublishedFrom neighbourhood", Q4),
):
    before = len(target)
    for triple in source.query(query):
        target.add(triple)
    print(f"{label}: +{len(target) - before} (total {len(target)})")

# hasAuthor links for all selected URI resources
HAS_AUTHOR = URIRef("http://purl.org/wittgensteinsource/ont/scholar/0.1/hasAuthor")
for s, p, o in list(target):
    if isinstance(s, URIRef):
        for author in source.objects(s, HAS_AUTHOR):
            target.add((s, HAS_AUTHOR, author))

print("After hasAuthor:", len(target))

# complete superclass hierarchy for every class used in the subgraph
classes = {o for o in target.objects(None, RDF.type) if isinstance(o, URIRef)}
queue = set(classes)

while queue:
    current = queue.pop()
    for parent in source.objects(current, RDFS.subClassOf):
        target.add((current, RDFS.subClassOf, parent))
        if isinstance(parent, URIRef):
            queue.add(parent)

print("After hierarchy:", len(target))

# schema declarations of all used terms
used = ({n for n in target.subjects(None, None)}
        | {n for n in target.objects(None, None)}
        | set(target.predicates(None, None))
        | {WAB.WittgensteinExternalSource})
used = {n for n in used if isinstance(n, URIRef)}

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

used = sorted(used, key=str)
for i in range(0, len(used), 200):
    values = " ".join(f"<{entity}>" for entity in used[i:i + 200])
    for triple in source.query(Q5 % values):
        target.add(triple)

# drop empty blank nodes in rdfs:domain / rdfs:range
for s, p, o in list(target):
    if p in (RDFS.domain, RDFS.range) and isinstance(o, BNode):
        if not any(target.triples((o, None, None))):
            target.remove((s, p, o))

print("Final subgraph:", len(target), "triples ->", OUTPUT_PATH.name)
target.serialize(destination=str(OUTPUT_PATH), format="turtle")
