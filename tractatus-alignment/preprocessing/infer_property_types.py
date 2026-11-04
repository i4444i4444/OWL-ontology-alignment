"""
Infer Object/DatatypeProperty types from value usage in the Wittgensteiniana source.
"""

import os

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF

SCHEMA = Namespace("https://schema.org/")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SOURCE = os.path.join(BASE_DIR, "cache", "wittgensteiniana.ttl")
OUTPUT = os.path.join(BASE_DIR, "cache", "wittgensteiniana_modified.ttl")

graph = Graph()
graph.parse(SOURCE, format="turtle")

predicate_types = {}

for subject, predicate, obj in graph:
    if predicate == RDF.type:
        continue
    if predicate == SCHEMA.author:
        continue

    if isinstance(obj, Literal):
        value_type = "datatype"
    elif isinstance(obj, (URIRef, BNode)):
        value_type = "object"
    else:
        continue

    predicate_types.setdefault(predicate, set()).add(value_type)

object_count = 0
datatype_count = 0
mixed = []

for predicate, types in predicate_types.items():
    if types == {"object"}:
        graph.add((predicate, RDF.type, OWL.ObjectProperty))
        object_count += 1

    elif types == {"datatype"}:
        graph.add((predicate, RDF.type, OWL.DatatypeProperty))
        datatype_count += 1

    else:
        mixed.append(str(predicate))

graph.serialize(OUTPUT, format="turtle")

print("file is installed:", OUTPUT)
print("object properties:", object_count)
print("data properties:", datatype_count)
print("predicates needing checking:", len(mixed))

for predicate in mixed:
    print("Проверить:", predicate)