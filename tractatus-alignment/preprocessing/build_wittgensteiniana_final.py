import os
import re
import unicodedata

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

SOURCE = os.path.join(BASE_DIR, "cache", "wittgensteiniana_modified.ttl")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "data")
OUTPUT = os.path.join(OUTPUT_DIR, "wittgensteiniana_final.ttl")

graph = Graph()
graph.parse(SOURCE, format="turtle")

SCHEMA = Namespace("https://schema.org/")
EX = Namespace("http://example.org/wittgensteiniana/")

graph.bind("ex", EX)
graph.bind("schema", SCHEMA)

schema_classes = [
    SCHEMA.Book,
    SCHEMA.Chapter,
    SCHEMA.CreativeWork,
    SCHEMA.DefinedTerm,
    SCHEMA.DefinedTermSet
]

for class_uri in schema_classes:
    graph.add((class_uri, RDF.type, OWL.Class))

graph.add((EX.Author, RDF.type, OWL.Class))
graph.add((EX.TextFragment, RDF.type, OWL.Class))

object_property_constraints = {
    EX.hasAuthor: (SCHEMA.Book, EX.Author),
    EX.hasTextFragment: (SCHEMA.Chapter, EX.TextFragment),
    SCHEMA.exampleOfWork: (EX.TextFragment, SCHEMA.Chapter),
    SCHEMA.inDefinedTermSet: (
        SCHEMA.DefinedTerm,
        SCHEMA.DefinedTermSet
    ),
    SCHEMA.isPartOf: (
        SCHEMA.CreativeWork,
        SCHEMA.CreativeWork
    ),
    SCHEMA.mentions: (SCHEMA.Chapter, SCHEMA.DefinedTerm),
    SCHEMA.translationOfWork: (SCHEMA.Book, SCHEMA.Book)
}

for property_uri, (domain_class, range_class) in (
    object_property_constraints.items()
):
    graph.add((property_uri, RDF.type, OWL.ObjectProperty))
    graph.add((property_uri, RDFS.domain, domain_class))
    graph.add((property_uri, RDFS.range, range_class))


# unit inventory: count the proposition units (schema:Chapter with a
# proposition-number name) without adding any redundant class typing -
# the original export already types them schema:Chapter only
thesis_count = 0

for unit, _, number in list(graph.triples((None, SCHEMA.name, None))):
    if not isinstance(number, Literal):
        continue

    number_text = str(number).strip()

    if not re.fullmatch(r"\d+(?:\.\d+)*", number_text):
        continue

    if not str(unit).startswith(
        "http://wittgensteiniana.michelepasin.org/id/unit/"
    ):
        continue

    thesis_count += 1


fragment_count = 0

for fragment, _, unit in list(
    graph.triples((None, SCHEMA.exampleOfWork, None))
):
    if not str(fragment).startswith(
        "http://wittgensteiniana.michelepasin.org/id/fragment/"
    ):
        continue

    if (unit, RDF.type, SCHEMA.Chapter) not in graph:
        continue

    graph.add((fragment, RDF.type, EX.TextFragment))
    graph.add((unit, EX.hasTextFragment, fragment))
    fragment_count += 1


def make_uri(kind, owner, value):
    normalized = unicodedata.normalize("NFKD", value)
    slug = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", slug).strip("_")

    if not slug:
        slug = "entity"

    return URIRef(EX[f"{kind}/{slug}"])


author_triples = list(
    graph.triples((None, SCHEMA.author, None))
)

for subject, predicate, value in author_triples:
    if not isinstance(value, Literal):
        continue

    author_text = str(value).strip()

    if author_text == "D.F. Pears and B.F. McGuinness":
        authors = ["D.F. Pears", "B.F. McGuinness"]
    else:
        authors = [author_text]

    graph.remove((subject, predicate, value))

    for author_name in authors:
        author_entity = make_uri(
            "author", subject, author_name
        )

        graph.add((subject, EX.hasAuthor, author_entity))
        graph.add((author_entity, RDF.type, EX.Author))
        graph.add((
            author_entity,
            RDFS.label,
            Literal(author_name)
        ))


datatype_properties = list(
    graph.subjects(RDF.type, OWL.DatatypeProperty)
)

for property_uri in datatype_properties:
    values = list(graph.objects(None, property_uri))

    if not values:
        continue

    if all(
        isinstance(value, Literal)
        and value.datatype == XSD.integer
        and not value.language
        for value in values
    ):
        graph.add((
            property_uri,
            RDFS.range,
            XSD.integer
        ))
    elif not any(
        isinstance(value, Literal) and value.language
        for value in values
    ):
        # plain literals only: safe to declare xsd:string. Language-tagged
        # literal values have datatype rdf:langString, which contradicts an
        # xsd:string range and makes the ontology inconsistent for DL
        # reasoners (Protégé explains: owl:Thing SubClassOf owl:Nothing),
        # so leave the range undeclared for such properties.
        graph.add((
            property_uri,
            RDFS.range,
            XSD.string
        ))


graph.add((SCHEMA.position, RDFS.domain, SCHEMA.Chapter))
graph.add((SCHEMA.text, RDFS.domain, EX.TextFragment))
graph.add((SCHEMA.datePublished, RDFS.domain, SCHEMA.Book))
graph.add((SCHEMA.description, RDFS.domain, SCHEMA.DefinedTerm))


graph.serialize(OUTPUT, format="turtle")

print("Done")
print("Theses processed:", thesis_count)
print("Text fragments processed:", fragment_count)
print("Author records processed:", len(author_triples))
print("Total triples:", len(graph))
print("Output file:", OUTPUT)