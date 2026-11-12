import json

import rag_config
from ontoaligner import ontology
from ontoaligner.encoder import ConceptParentRAGEncoder
from ontoaligner.postprocess import rag_heuristic_postprocessor, rag_hybrid_postprocessor
from ontoaligner.utils import metrics, xmlify

ENCODER_NAME = "concept_parent"
DIRECTIONS = ("wab2witt", "witt2wab")
MODES = ("heuristic", "hybrid")


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4, default=str)


def save_text(path, text):
    with open(path, "w", encoding="utf-8") as file:
        file.write(text)


def load_datasets():
    task = ontology.GenericOMDataset()
    datasets = {}
    for direction in DIRECTIONS:
        source, target = rag_config.DIRECTIONS[direction]
        datasets[direction] = task.collect(
            source_ontology_path=str(source),
            target_ontology_path=str(target),
            reference_matching_path=str(rag_config.DATA_DIR / "reference.xml"),
        )
    return datasets


def postprocess_predictions(predicts, mode):
    if mode == "heuristic":
        matchings, _ = rag_heuristic_postprocessor(
            predicts=predicts,
            topk_confidence_ratio=3,
            topk_confidence_score=3,
        )
    else:
        matchings, _ = rag_hybrid_postprocessor(
            predicts=predicts,
            ir_score_threshold=0.1,
            llm_confidence_th=0.8,
        )
    return matchings


def run_direction(encoder, direction, dataset, run_dir):
    encoded = encoder(source=dataset["source"], target=dataset["target"])

    model = rag_config.QwenLLMBERTRetrieverRAG(
        retriever_config=rag_config.RETRIEVER_CONFIGS[direction],
        llm_config=rag_config.LLM_CONFIG,
    )
    model.load(llm_path=rag_config.LLM_PATH, ir_path=rag_config.IR_PATH)
    predicts = model.generate(input_data=encoded)

    direction_dir = run_dir / direction
    direction_dir.mkdir(parents=True, exist_ok=True)
    save_json(direction_dir / "predictions.json", predicts)

    matchings_by_mode = {}
    for mode in MODES:
        matchings = postprocess_predictions(predicts, mode)
        save_json(direction_dir / f"{mode}_matchings.json", matchings)
        xml_text = xmlify.xml_alignment_generator(matchings=matchings)
        save_text(direction_dir / f"{mode}_matchings.xml", xml_text)
        matchings_by_mode[mode] = matchings

    print(f"{ENCODER_NAME}/{direction}: heuristic {len(matchings_by_mode['heuristic'])}, "
          f"hybrid {len(matchings_by_mode['hybrid'])}")
    return matchings_by_mode


def canonical_pairs(rows):
    pairs = set()
    for row in rows:
        pairs.add(rag_config.canonical_pair(row))
    return pairs


def compare_bidirectional(positives, mode, reference, run_dir):
    fw_rows = []
    for row in positives["wab2witt"][mode]:
        fw_rows.append(rag_config.swapped(row))
    rev_rows = []
    for row in positives["witt2wab"][mode]:
        rev_rows.append(rag_config.swapped(row))

    shared_pairs = canonical_pairs(fw_rows) & canonical_pairs(rev_rows)
    both_rows = []
    for source_uri, target_uri in sorted(shared_pairs, key=str):
        both_rows.append({"source": source_uri, "target": target_uri, "relation": "="})

    report = {
        "fw": metrics.evaluation_report(predicts=fw_rows, references=reference),
        "rev": metrics.evaluation_report(predicts=rev_rows, references=reference),
        "both": metrics.evaluation_report(predicts=both_rows, references=reference),
    }
    save_json(run_dir / f"bidirectional_{mode}.json", both_rows)
    xml_text = xmlify.xml_alignment_generator(matchings=both_rows)
    save_text(run_dir / f"bidirectional_{mode}.xml", xml_text)

    print(f"\n=== {ENCODER_NAME} / {mode} bidirectional ===")
    print(" fw:", report["fw"])
    print(" rev:", report["rev"])
    print(" both:", report["both"])
    return report


def main():
    rag_config.prepare_temp_ontologies()

    datasets = load_datasets()
    reference = datasets["wab2witt"]["reference"]

    run_dir = rag_config.RESULTS_DIR / ENCODER_NAME
    run_dir.mkdir(parents=True, exist_ok=True)

    encoder = ConceptParentRAGEncoder()
    positives = {}
    for direction in DIRECTIONS:
        positives[direction] = run_direction(encoder, direction, datasets[direction], run_dir)

    bidirectional = {}
    for mode in MODES:
        bidirectional[mode] = compare_bidirectional(positives, mode, reference, run_dir)

    save_json(run_dir / "bidirectional_summary.json", bidirectional)
    print("\nSaved -> results/rag/")


main()
