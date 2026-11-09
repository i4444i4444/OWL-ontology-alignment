"""
Build the Tractatus proposition alignment layer (the bridge overlay file).

Numbers: schema:name of schema:Chapter units (Wittgensteiniana) and the trailing number
in rdfs:label of wab:Part (WAB). Shared numbers become align:TractatusProposition
resources; each source instance links to them via align:denotesProposition.
When running OntoAligner the layer is merged into BOTH ontologies, so the
shared TractatusProposition individuals link the two sides together.
"""

import re
from pathlib import Path

from rdflib import OWL, RDF, RDFS, Graph, Literal, Namespace, URIRef
from rdflib.namespace import XSD

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results" / "propositions"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

ALIGNMENT_PATH = DATA_DIR / "tractatus_alignment_layer.ttl"

SCHEMA = Namespace("https://schema.org/")
ALIGN = Namespace("http://example.org/tractatus-alignment/")
NUMBER = re.compile(r"\d+(?:\.\d+)*\s*$")


def extract_numbers(graph, rdf_type, read):
    """Return {number: uri} for every instance of rdf_type."""
    numbers = {}
    for uri in sorted(set(graph.subjects(RDF.type, rdf_type)), key=str):
        number = str(read(uri)).strip()
        match = NUMBER.search(number)
        if not match:
            raise ValueError(f"No proposition number at {uri}")
        numbers[match.group(0)] = uri
    return numbers


witt = Graph()
witt.parse(str(DATA_DIR / "wittgensteiniana_final.ttl"), format="turtle")
wab = Graph()
wab.parse(str(DATA_DIR / "wab_tractatus_subgraph.ttl"), format="turtle")

witt_numbers = extract_numbers(witt, SCHEMA.Chapter, lambda u: witt.value(u, SCHEMA.name))
wab_numbers = extract_numbers(wab, Namespace("http://purl.org/wittgensteinsource/ont/").Part,
                              lambda u: wab.value(u, RDFS.label))
print(f"Numbers: Wittgensteiniana {len(witt_numbers)}, WAB {len(wab_numbers)}")


def sort_key(number):
    return tuple(int(part) for part in number.split(".")), number


common = set(witt_numbers) & set(wab_numbers)
only_witt = sorted(set(witt_numbers) - set(wab_numbers), key=sort_key)
only_wab = sorted(set(wab_numbers) - set(witt_numbers), key=sort_key)
print(f"Common: {len(common)}, only Witt: {only_witt}, only WAB: {only_wab}")

layer = Graph()
layer.bind("align", ALIGN)
layer.bind("schema", SCHEMA)
layer.bind("wab", Namespace("http://purl.org/wittgensteinsource/ont/"))
layer.bind("rdf", RDF)
layer.bind("rdfs", RDFS)
layer.bind("owl", OWL)
layer.bind("xsd", XSD)

layer.add((ALIGN.TractatusProposition, RDF.type, OWL.Class))
layer.add((ALIGN.TractatusProposition, RDFS.label, Literal("Tractatus proposition", lang="en")))
layer.add((ALIGN.hasNumber, RDF.type, OWL.DatatypeProperty))
layer.add((ALIGN.hasNumber, RDFS.label, Literal("literal proposition number as a string", lang="en")))
layer.add((ALIGN.denotesProposition, RDF.type, OWL.ObjectProperty))
layer.add((ALIGN.denotesProposition, RDFS.label, Literal("source instance denotes a TLP proposition", lang="en")))

for number in sorted(set(witt_numbers) | set(wab_numbers), key=sort_key):
    proposition = ALIGN[f"Prop_{number.replace('.', '_')}"]
    layer.add((proposition, RDF.type, ALIGN.TractatusProposition))
    layer.add((proposition, RDFS.label, Literal(f"Tractatus {number}", lang="en")))
    layer.add((proposition, ALIGN.hasNumber, Literal(number, datatype=XSD.string)))
    if number in witt_numbers:
        layer.add((witt_numbers[number], ALIGN.denotesProposition, proposition))
    if number in wab_numbers:
        layer.add((wab_numbers[number], ALIGN.denotesProposition, proposition))

# The Tractatus itself: the same work lives in both ontologies under
# different IRIs - WAB has a single Werk instance (label mentions 1922 et 1933),
# Wittgensteiniana has the German original id/expression/tractatus plus two
# translation expressions (ogden, pears) which have no WAB counterpart.
# Declare identity for the German original at work level.
W_TLP = URIRef("http://purl.org/wittgensteinsource/ont/instances/W-TLP")
TRACTATUS = URIRef("http://wittgensteiniana.michelepasin.org/id/tractatus")
layer.add((W_TLP, OWL.sameAs, TRACTATUS))

layer.serialize(destination=str(ALIGNMENT_PATH), format="turtle")
print(f"Alignment layer (bridge): {len(layer)} triples -> {ALIGNMENT_PATH.name}")

import json

summary = {
    "wittgensteiniana_unique": len(witt_numbers),
    "wab_unique": len(wab_numbers),
    "common": sorted(common, key=sort_key),
    "only_wittgensteiniana": only_witt,
    "only_wab": only_wab,
    "union": len(set(witt_numbers) | set(wab_numbers)),
    "alignment_layer_triples": len(layer),
}
with open(RESULTS_DIR / "propositions_summary.json", "w", encoding="utf-8") as file:
    json.dump(summary, file, ensure_ascii=False, indent=4)
print("Summary saved -> propositions_summary.json")
