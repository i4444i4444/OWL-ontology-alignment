"""
Convert the draft reference_alignment.json to the OAEI Alignment XML format
expected by OntoAligner's reference parser.
"""

import json
from pathlib import Path

from rdflib import RDF, Graph, Literal, Namespace, URIRef
from rdflib.namespace import XSD

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

ALIGN = Namespace("http://knowledgeweb.semanticweb.org/heterogeneity/alignment")

reference = json.load(open(DATA_DIR / "reference_alignment.json", encoding="utf-8"))

graph = Graph()
graph.bind("align", ALIGN)

alignment = ALIGN["Alignment"]
graph.add((alignment, RDF.type, ALIGN["Alignment"]))
graph.add((alignment, ALIGN.xml, Literal("yes")))
graph.add((alignment, ALIGN.onto1, Literal(reference["meta"]["source_ontology"])))
graph.add((alignment, ALIGN.onto2, Literal(reference["meta"]["target_ontology"])))

for i, mapping in enumerate(reference["class_mappings"]):
    cell = ALIGN[f"Cell_C{i}"]
    graph.add((alignment, ALIGN.map, cell))
    graph.add((cell, RDF.type, ALIGN.Cell))
    graph.add((cell, ALIGN.entity1, URIRef(mapping["source"])))
    graph.add((cell, ALIGN.entity2, URIRef(mapping["target"])))
    graph.add((cell, ALIGN.relation, Literal("=")))
    graph.add((cell, ALIGN.measure, Literal(1.0, datatype=XSD.float)))

output_path = DATA_DIR / "reference.xml"
graph.serialize(destination=str(output_path), format="xml")
print("Wrote", output_path)
