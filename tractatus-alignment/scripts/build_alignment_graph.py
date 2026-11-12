import json
from pathlib import Path

from rdflib import OWL, RDF, RDFS, SKOS, Graph, Literal, Namespace, URIRef

DATA = Path(__file__).resolve().parent.parent / "data"
ALIGN = Namespace("http://example.org/tractatus-alignment/")

g = Graph()
for ttl in ("wab_tractatus_subgraph.ttl", "wab_tractatus_comments.ttl",
            "wittgensteiniana_final.ttl", "wittgensteiniana_comments.ttl",
            "tractatus_alignment_layer.ttl"):
    g.parse(str(DATA / ttl), format="turtle")
g.bind("align", ALIGN)


g.add((ALIGN.mergedGraph, RDF.type, OWL.Ontology))
g.add((ALIGN.mergedGraph, RDFS.label,
       Literal("Tractatus alignment graph (WAB + Wittgensteiniana)", lang="en")))
g.add((ALIGN.mergedGraph, OWL.versionInfo, Literal("v1")))
g.add((ALIGN.mergedGraph, RDFS.comment, Literal(
    "Union of both ontologies, their documentation overlays and the bridge "
    "layer (shared TractatusProposition individuals + wab:W-TLP owl:sameAs "
    "witt-iri/tractatus). Class mappings from data/reference_alignment.json "
    "are expressed with skos:exactMatch / skos:closeMatch.", lang="en")))


NAME = URIRef("https://schema.org/name")
for subject, value in list(g.subject_objects(NAME)):
    if not any(g.objects(subject, RDFS.label)):
        g.add((subject, RDFS.label, value))


EQUIVALENT_IDS = {"C1", "C2", "C5"}
SKOS_LEVEL = {"strong": SKOS.exactMatch, "medium": SKOS.closeMatch,
              "weak": SKOS.closeMatch}
for prop in (SKOS.exactMatch, SKOS.closeMatch):
    g.add((prop, RDF.type, OWL.AnnotationProperty))

for mapping in json.load(open(DATA / "reference_alignment.json", encoding="utf-8"))["class_mappings"]:
    source, target = URIRef(mapping["source"]), URIRef(mapping["target"])
    prop = SKOS_LEVEL[mapping["strength"]]
    g.add((source, prop, target))
    g.add((target, prop, source))
    g.add((source, RDFS.comment, Literal(
        f"Reference mapping {mapping['id']} ({mapping['strength']}): "
        f"{mapping['justification']}", lang="en")))
    if mapping["id"] in EQUIVALENT_IDS:
        g.add((source, OWL.equivalentClass, target))
        g.add((target, OWL.equivalentClass, source))


LANGUAGE = URIRef("http://purl.org/wittgensteinsource/ont/scholar/0.1/Language")
langs = {"de": ALIGN.lang_de, "en": ALIGN.lang_en}
for code, individual in langs.items():
    g.add((individual, RDF.type, LANGUAGE))
    g.add((individual, RDFS.label,
           Literal("German" if code == "de" else "English", lang="en")))
g.add((URIRef("http://purl.org/wittgensteinsource/ont/deu"), OWL.sameAs, langs["de"]))
g.add((ALIGN.hasLanguage, RDF.type, OWL.ObjectProperty))
g.add((ALIGN.hasLanguage, RDFS.label,
       Literal("resource has a language individual", lang="en")))
g.add((LANGUAGE, RDFS.comment, Literal(
    "No class counterpart in Wittgensteiniana: language lives there as the "
    "data property schema:inLanguage, normalized here into shared "
    "align:lang_de / align:lang_en individuals.", lang="en")))
for resource, code in list(g.subject_objects(URIRef("https://schema.org/inLanguage"))):
    if str(code) in langs:
        g.add((resource, ALIGN.hasLanguage, langs[str(code)]))

out = DATA.parent / "results" / "protege" / "tractatus_aligned.ttl"
out.parent.mkdir(parents=True, exist_ok=True)
g.serialize(str(out), format="turtle")
print(f"{len(g)} triples -> {out}")
