import json
from pathlib import Path

from rdflib import OWL, RDF, RDFS, SKOS, Graph, Literal, Namespace, URIRef

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT = DATA_DIR.parent / "results" / "protege" / "tractatus_aligned.ttl"

ALIGN = Namespace("http://example.org/tractatus-alignment/")
SCHEMA = Namespace("https://schema.org/")
IN_LANGUAGE = SCHEMA.inLanguage
SCHEMA_NAME = SCHEMA.name


def load_graph():
    graph = Graph()
    file_names = (
        "wab_tractatus_subgraph.ttl",
        "wab_tractatus_comments.ttl",
        "wittgensteiniana_final.ttl",
        "wittgensteiniana_comments.ttl",
        "tractatus_alignment_layer.ttl",
    )
    for file_name in file_names:
        graph.parse(str(DATA_DIR / file_name), format="turtle")
    graph.bind("align", ALIGN)
    return graph


def add_ontology_header(graph):
    graph.add((ALIGN.mergedGraph, RDF.type, OWL.Ontology))
    graph.add((ALIGN.mergedGraph, RDFS.label,
               Literal("Tractatus alignment graph (WAB + Wittgensteiniana)", lang="en")))
    graph.add((ALIGN.mergedGraph, OWL.versionInfo, Literal("v1")))
    graph.add((ALIGN.mergedGraph, RDFS.comment, Literal(
        "Union of both ontologies, their documentation overlays and the bridge "
        "layer (shared TractatusProposition individuals + wab:W-TLP owl:sameAs "
        "witt-iri/tractatus). Class mappings from data/reference_alignment.json "
        "are expressed with skos:exactMatch / skos:closeMatch.", lang="en")))


def copy_schema_names_to_labels(graph):
    for subject, value in list(graph.subject_objects(SCHEMA_NAME)):
        if not any(graph.objects(subject, RDFS.label)):
            graph.add((subject, RDFS.label, value))


def add_class_mappings(graph):
    skos_property = {
        "strong": SKOS.exactMatch,
        "medium": SKOS.closeMatch,
        "weak": SKOS.closeMatch,
    }
    equivalent_ids = {"C1", "C2", "C5"}
    for prop in (SKOS.exactMatch, SKOS.closeMatch):
        graph.add((prop, RDF.type, OWL.AnnotationProperty))

    with open(DATA_DIR / "reference_alignment.json", encoding="utf-8") as file:
        reference = json.load(file)
    for mapping in reference["class_mappings"]:
        source = URIRef(mapping["source"])
        target = URIRef(mapping["target"])
        prop = skos_property[mapping["strength"]]
        graph.add((source, prop, target))
        graph.add((target, prop, source))
        graph.add((source, RDFS.comment, Literal(
            f"Reference mapping {mapping['id']} ({mapping['strength']}): "
            f"{mapping['justification']}", lang="en")))
        if mapping["id"] in equivalent_ids:
            graph.add((source, OWL.equivalentClass, target))
            graph.add((target, OWL.equivalentClass, source))


def add_language_information(graph):
    language_class = URIRef("http://purl.org/wittgensteinsource/ont/scholar/0.1/Language")
    languages = {
        "de": (ALIGN.lang_de, "German"),
        "en": (ALIGN.lang_en, "English"),
    }
    for code, (individual, label) in languages.items():
        graph.add((individual, RDF.type, language_class))
        graph.add((individual, RDFS.label, Literal(label, lang="en")))
    graph.add((URIRef("http://purl.org/wittgensteinsource/ont/deu"), OWL.sameAs, ALIGN.lang_de))
    graph.add((ALIGN.hasLanguage, RDF.type, OWL.ObjectProperty))
    graph.add((ALIGN.hasLanguage, RDFS.label,
               Literal("resource has a language individual", lang="en")))
    graph.add((language_class, RDFS.comment, Literal(
        "No class counterpart in Wittgensteiniana: language lives there as the "
        "data property schema:inLanguage, normalized here into shared "
        "align:lang_de / align:lang_en individuals.", lang="en")))
    for resource, code in list(graph.subject_objects(IN_LANGUAGE)):
        if str(code) in languages:
            graph.add((resource, ALIGN.hasLanguage, languages[str(code)][0]))


def main():
    graph = load_graph()
    add_ontology_header(graph)
    copy_schema_names_to_labels(graph)
    add_class_mappings(graph)
    add_language_information(graph)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    graph.serialize(str(OUTPUT), format="turtle")
    print(f"{len(graph)} triples -> {OUTPUT}")


main()
