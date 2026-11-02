import json
from pathlib import Path

from ontoaligner import encoder, ontology
from ontoaligner.aligner import (
    SimpleFuzzySMLightweight,
    TokenSetFuzzySMLightweight,
    WeightedFuzzySMLightweight,
)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results" / "fuzzy_properties"

RESULTS_DIR.mkdir(parents=True, exist_ok=True)

FILES = {
    "WAB": DATA_DIR / "wab_tractatus_subgraph.ttl",
    "Wittgensteiniana": DATA_DIR / "wittgensteiniana_final.ttl",
}


def remove_duplicates(properties):
    unique_properties = {}

    for prop in properties:
        unique_properties[prop["iri"]] = prop

    return list(unique_properties.values())


source_parser = ontology.OntologyProperty()
target_parser = ontology.OntologyProperty()

source_data = source_parser.parse(str(FILES["WAB"]))
target_data = target_parser.parse(
    str(FILES["Wittgensteiniana"])
)

source_data = remove_duplicates(source_data)
target_data = remove_duplicates(target_data)

print("WAB properties:", len(source_data))
print("Wittgensteiniana properties:", len(target_data))

property_encoder = encoder.PropertyEncoder()

encoded_data = property_encoder(
    source=source_data,
    target=target_data
)

aligners = {
    "simple_fuzzy": SimpleFuzzySMLightweight(
        fuzzy_sm_threshold=0.5
    ),
    "weighted_fuzzy": WeightedFuzzySMLightweight(
        fuzzy_sm_threshold=0.5
    ),
    "token_set_fuzzy": TokenSetFuzzySMLightweight(
        fuzzy_sm_threshold=0.5
    ),
}

for name, aligner in aligners.items():
    print(f"\nRunning {name}...")

    results = aligner.generate(input_data=encoded_data)

    output_path = RESULTS_DIR / f"{name}.json"

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(
            results,
            file,
            ensure_ascii=False,
            indent=4,
            default=str
        )

    print("Number of matches:", len(results))
    print("Results saved to:", output_path)

print("\nProperty matching completed.")
