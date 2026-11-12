import os
import re
import unicodedata

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

SOURCE = os.path.join(BASE_DIR, "cache", "wittgensteiniana_modified.ttl")
OUTPUT = os.path.join(PROJECT_DIR, "data", "wittgensteiniana_final.ttl")

SCHEMA = Namespace("https://schema.org/")
EX = Namespace("http://example.org/wittgensteiniana/")


def load_graph():
    graph = Graph()
    graph.parse(SOURCE, format="turtle")
    graph.bind("ex", EX)
    graph.bind("schema", SCHEMA)
    return graph


def add_classes(graph):
    schema_classes = [
        SCHEMA.Book,
        SCHEMA.Chapter,
        SCHEMA.CreativeWork,
        SCHEMA.DefinedTerm,
        SCHEMA.DefinedTermSet,
    ]
    for class_uri in schema_classes:
        graph.add((class_uri, RDF.type, OWL.Class))
    graph.add((EX.Author, RDF.type, OWL.Class))
    graph.add((EX.TextFragment, RDF.type, OWL.Class))


def add_object_properties(graph):
    constraints = {
        EX.hasAuthor: (SCHEMA.Book, EX.Author),
        EX.hasTextFragment: (SCHEMA.Chapter, EX.TextFragment),
        SCHEMA.exampleOfWork: (EX.TextFragment, SCHEMA.Chapter),
        SCHEMA.inDefinedTermSet: (SCHEMA.DefinedTerm, SCHEMA.DefinedTermSet),
        SCHEMA.isPartOf: (SCHEMA.CreativeWork, SCHEMA.CreativeWork),
        SCHEMA.mentions: (SCHEMA.Chapter, SCHEMA.DefinedTerm),
        SCHEMA.translationOfWork: (SCHEMA.Book, SCHEMA.Book),
    }
    for property_uri, (domain_class, range_class) in constraints.items():
        graph.add((property_uri, RDF.type, OWL.ObjectProperty))
        graph.add((property_uri, RDFS.domain, domain_class))
        graph.add((property_uri, RDFS.range, range_class))


def count_theses(graph):
    count = 0
    for unit, _, number in list(graph.triples((None, SCHEMA.name, None))):
        if not isinstance(number, Literal):
            continue
        number_text = str(number).strip()
        if not re.fullmatch(r"\d+(?:\.\d+)*", number_text):
            continue
        if not str(unit).startswith("http://wittgensteiniana.michelepasin.org/id/unit/"):
            continue
        count += 1
    return count


def add_text_fragments(graph):
    count = 0
    for fragment, _, unit in list(graph.triples((None, SCHEMA.exampleOfWork, None))):
        if not str(fragment).startswith("http://wittgensteiniana.michelepasin.org/id/fragment/"):
            continue
        if (unit, RDF.type, SCHEMA.Chapter) not in graph:
            continue
        graph.add((fragment, RDF.type, EX.TextFragment))
        graph.add((unit, EX.hasTextFragment, fragment))
        count += 1
    return count


def make_uri(kind, value):
    normalized = unicodedata.normalize("NFKD", value)
    slug = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", slug).strip("_")
    if not slug:
        slug = "entity"
    return URIRef(EX[f"{kind}/{slug}"])


def add_authors(graph):
    author_triples = list(graph.triples((None, SCHEMA.author, None)))
    for subject, predicate, value in author_triples:
        if not isinstance(value, Literal):
            continue
        author_text = str(value).strip()
        if author_text == "D.F. Pears and B.F. McGuinness":
            names = ["D.F. Pears", "B.F. McGuinness"]
        else:
            names = [author_text]
        graph.remove((subject, predicate, value))
        for author_name in names:
            author_entity = make_uri("author", author_name)
            graph.add((subject, EX.hasAuthor, author_entity))
            graph.add((author_entity, RDF.type, EX.Author))
            graph.add((author_entity, RDFS.label, Literal(author_name)))
    return len(author_triples)


def add_datatype_ranges(graph):
    property_uris = list(graph.subjects(RDF.type, OWL.DatatypeProperty))
    for property_uri in property_uris:
        values = list(graph.objects(None, property_uri))
        if not values:
            continue
        all_integer = True
        for value in values:
            if not isinstance(value, Literal):
                all_integer = False
            elif value.datatype != XSD.integer or value.language:
                all_integer = False
        if all_integer:
            graph.add((property_uri, RDFS.range, XSD.integer))
            continue
        has_language = False
        for value in values:
            if isinstance(value, Literal) and value.language:
                has_language = True
        if not has_language:
            graph.add((property_uri, RDFS.range, XSD.string))


def add_domains(graph):
    graph.add((SCHEMA.position, RDFS.domain, SCHEMA.Chapter))
    graph.add((SCHEMA.text, RDFS.domain, EX.TextFragment))
    graph.add((SCHEMA.datePublished, RDFS.domain, SCHEMA.Book))
    graph.add((SCHEMA.description, RDFS.domain, SCHEMA.DefinedTerm))


def main():
    graph = load_graph()
    add_classes(graph)
    add_object_properties(graph)
    thesis_count = count_theses(graph)
    fragment_count = add_text_fragments(graph)
    author_count = add_authors(graph)
    add_datatype_ranges(graph)
    add_domains(graph)
    graph.serialize(OUTPUT, format="turtle")
    print("Done")
    print("Theses processed:", thesis_count)
    print("Text fragments processed:", fragment_count)
    print("Author records processed:", author_count)
    print("Total triples:", len(graph))
    print("Output file:", OUTPUT)


main()
