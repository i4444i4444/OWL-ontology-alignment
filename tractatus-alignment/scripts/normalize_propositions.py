"""
Build a separate alignment layer for Wittgensteiniana and WAB based on the
shared numbering of Tractatus logico-philosophicus propositions.

What it does:
  1. Reads the two source TTL graphs (they are never modified).
  2. Extracts proposition numbers:
       - Wittgensteiniana: schema:name of http://example.org/wittgensteiniana/Thesis
       - WAB: the trailing number of rdfs:label of wab:Part
  3. Verifies that numbers are unique inside each ontology.
  4. Creates one shared resource align:TractatusProposition per unique number
     (union of both ontologies) with the literal property align:hasNumber.
     Numbers are kept as plain string literals so values like "4.004" are not
     changed by numeric conversion.
  5. Links every source instance to the shared resource via align:denotesProposition.
  6. Saves the alignment layer separately, plus an optional combined view
     (both source graphs + the alignment layer) for Protégé / SPARQL work.

Note on numbers: unlike earlier experiments, single-digit main propositions
("1" ... "7") are included. They are valid TLP numbers and also occur in WAB.
"""

import json
import re
from pathlib import Path

from rdflib import OWL, RDF, RDFS, Graph, Literal, Namespace
from rdflib.namespace import XSD

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results" / "propositions"

WITT_PATH = DATA_DIR / "wittgensteiniana_final.ttl"
WAB_PATH = DATA_DIR / "wab_tractatus_subgraph.ttl"

ALIGNMENT_PATH = DATA_DIR / "tractatus_alignment_layer.ttl"
COMBINED_PATH = DATA_DIR / "tractatus_combined.ttl"

SCHEMA = Namespace("https://schema.org/")
WAB_ONTO = Namespace("http://purl.org/wittgensteinsource/ont/")

ALIGN = Namespace("http://example.org/tractatus-alignment/")

WITT_NS = "http://wittgensteiniana.michelepasin.org/id/unit/"
WAB_NS = "http://purl.org/wittgensteinsource/ont/instances/W-TLP"

# Main propositions ("1", "2", ..., "7") are valid TLP numbers.
NUMBER_PATTERN = re.compile(r"(\d+(?:\.\d+)*)\s*$")


# Extraction


def extract_wittgensteiniana_numbers(graph: Graph) -> dict:
    """Return {proposition_number: thesis_uri} from schema:name of Thesis."""
    WITT_ONTO = Namespace("http://example.org/wittgensteiniana/")
    numbers = {}
    duplicates = []

    theses = set(graph.subjects(RDF.type, WITT_ONTO.Thesis))

    for thesis in sorted(theses, key=str):
        name = graph.value(thesis, SCHEMA.name)
        if name is None:
            raise ValueError(f"Thesis without schema:name: {thesis}")
        number = str(name).strip()
        if not NUMBER_PATTERN.fullmatch(number):
            raise ValueError(f"Unexpected thesis number format: {number!r} at {thesis}")
        if number in numbers:
            duplicates.append(number)
        numbers[number] = thesis

    if duplicates:
        raise ValueError(f"Duplicate Wittgensteiniana numbers: {duplicates}")

    return numbers


def extract_wab_numbers(graph: Graph) -> dict:
    """Return {proposition_number: part_uri} from the rdfs:label tail of Part."""
    numbers = {}
    duplicates = []

    parts = set(graph.subjects(RDF.type, WAB_ONTO.Part))

    for part in sorted(parts, key=str):
        label = graph.value(part, RDFS.label)
        if label is None:
            raise ValueError(f"Part without rdfs:label: {part}")
        match = NUMBER_PATTERN.search(str(label))
        if not match:
            raise ValueError(f"No proposition number in label: {str(label)!r} at {part}")
        number = match.group(1)
        if number in numbers:
            duplicates.append(number)
        numbers[number] = part

    if duplicates:
        raise ValueError(f"Duplicate WAB numbers: {duplicates}")

    return numbers


# Alignment layer


def build_alignment_layer(witt_numbers: dict, wab_numbers: dict) -> Graph:
    layer = Graph()

    layer.bind("align", ALIGN)
    layer.bind("schema", SCHEMA)
    layer.bind("wab", WAB_ONTO)
    layer.bind("rdf", RDF)
    layer.bind("rdfs", RDFS)
    layer.bind("owl", OWL)
    layer.bind("xsd", XSD)

    layer.add((ALIGN.TractatusProposition, RDF.type, OWL.Class))
    layer.add(
        (ALIGN.TractatusProposition, RDFS.label, Literal("Tractatus proposition", lang="en"))
    )

    layer.add((ALIGN.hasNumber, RDF.type, OWL.DatatypeProperty))
    layer.add(
        (ALIGN.hasNumber, RDFS.label, Literal("literal proposition number as a string", lang="en"))
    )

    layer.add((ALIGN.denotesProposition, RDF.type, OWL.ObjectProperty))
    layer.add(
        (
            ALIGN.denotesProposition,
            RDFS.label,
            Literal("source instance denotes a TLP proposition", lang="en"),
        )
    )

    all_numbers = sorted(set(witt_numbers) | set(wab_numbers), key=proposition_sort_key)

    for number in all_numbers:
        proposition = ALIGN[f"Prop_{number.replace('.', '_')}"]

        layer.add((proposition, RDF.type, ALIGN.TractatusProposition))
        layer.add((proposition, RDFS.label, Literal(f"Tractatus {number}", lang="en")))
        # Keep the number as a plain string literal ("xsd:string"-compatible),
        # so values like "4.004" are preserved verbatim.
        layer.add((proposition, ALIGN.hasNumber, Literal(number, datatype=XSD.string)))

        if number in witt_numbers:
            layer.add((witt_numbers[number], ALIGN.denotesProposition, proposition))

        if number in wab_numbers:
            layer.add((wab_numbers[number], ALIGN.denotesProposition, proposition))

    return layer, all_numbers


def proposition_sort_key(number: str):
    """Deterministic ordering: split '4.004' into numeric parts."""
    return tuple(int(part) for part in number.split("."))


# Main


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading Wittgensteiniana...")
    witt = Graph()
    witt.parse(str(WITT_PATH), format="turtle")
    print(f"  {len(witt):,} triples")

    print("Loading WAB fragment...")
    wab = Graph()
    wab.parse(str(WAB_PATH), format="turtle")
    print(f"  {len(wab):,} triples")

    print("Extracting proposition numbers...")
    witt_numbers = extract_wittgensteiniana_numbers(witt)
    wab_numbers = extract_wab_numbers(wab)

    print(f"  Wittgensteiniana: {len(witt_numbers)} unique numbers")
    print(f"  WAB:              {len(wab_numbers)} unique numbers")

    common = set(witt_numbers) & set(wab_numbers)
    only_witt = set(witt_numbers) - set(wab_numbers)
    only_wab = set(wab_numbers) - set(witt_numbers)

    print(f"  Common:           {len(common)}")
    print(f"  Only Witt:        {sorted(only_witt, key=proposition_sort_key)}")
    print(f"  Only WAB:         {sorted(only_wab, key=proposition_sort_key)}")

    print("Building alignment layer...")
    layer, all_numbers = build_alignment_layer(witt_numbers, wab_numbers)
    print(f"  {len(layer):,} triples, {len(all_numbers)} shared propositions")

    print(f"\nSaving alignment layer -> {ALIGNMENT_PATH}")
    layer.serialize(destination=str(ALIGNMENT_PATH), format="turtle")

    print(f"Saving combined view -> {COMBINED_PATH}")
    combined = Graph()
    for triple in witt:
        combined.add(triple)
    for triple in wab:
        combined.add(triple)
    for triple in layer:
        combined.add(triple)
    print(f"  {len(combined):,} triples")
    combined.serialize(destination=str(COMBINED_PATH), format="turtle")

    summary = {
        "wittgensteiniana_unique": len(witt_numbers),
        "wab_unique": len(wab_numbers),
        "common": sorted(common, key=proposition_sort_key),
        "only_wittgensteiniana": sorted(only_witt, key=proposition_sort_key),
        "only_wab": sorted(only_wab, key=proposition_sort_key),
        "union": len(all_numbers),
        "alignment_layer_triples": len(layer),
        "combined_triples": len(combined),
    }

    summary_path = RESULTS_DIR / "propositions_summary.json"
    with open(summary_path, "w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=4)
    print(f"\nSummary saved -> {summary_path}")

    print("Done.")


if __name__ == "__main__":
    main()
