import json

import rag_config
from ontoaligner import ontology
from ontoaligner.encoder import ConceptParentRAGEncoder
from ontoaligner.postprocess import (
    rag_heuristic_postprocessor,
    rag_hybrid_postprocessor,
)
from ontoaligner.utils import metrics, xmlify

rag_config.prepare_temp_ontologies()

task = ontology.GenericOMDataset()
datasets = {
    key: task.collect(
        source_ontology_path=str(source),
        target_ontology_path=str(target),
        reference_matching_path=str(rag_config.DATA_DIR / "reference.xml"),
    )
    for key, (source, target) in rag_config.DIRECTIONS.items()
}

reference = datasets["wab2witt"]["reference"]

for encoder_name, encoder_model in (("concept_parent", ConceptParentRAGEncoder()),):
    run_dir = rag_config.RESULTS_DIR / encoder_name
    run_dir.mkdir(parents=True, exist_ok=True)

    positives = {}
    for direction, dataset in datasets.items():
        encoded = encoder_model(source=dataset["source"], target=dataset["target"])

        model = rag_config.QwenLLMBERTRetrieverRAG(retriever_config=rag_config.RETRIEVER_CONFIGS[direction], llm_config=rag_config.LLM_CONFIG)
        model.load(llm_path=rag_config.LLM_PATH, ir_path=rag_config.IR_PATH)
        predicts = model.generate(input_data=encoded)

        dir_dir = run_dir / direction
        dir_dir.mkdir(parents=True, exist_ok=True)
        with open(dir_dir / "predictions.json", "w", encoding="utf-8") as file:
            json.dump(predicts, file, ensure_ascii=False, indent=4, default=str)

        matched_files = {}
        for mode, postprocessor in (
            ("heuristic", rag_heuristic_postprocessor),
            ("hybrid", rag_hybrid_postprocessor),
        ):
            if mode == "heuristic":
                matchings, _ = postprocessor(predicts=predicts, topk_confidence_ratio=3, topk_confidence_score=3)
            else:
                matchings, _ = postprocessor(predicts=predicts, ir_score_threshold=0.1, llm_confidence_th=0.8)
            with open(dir_dir / f"{mode}_matchings.json", "w", encoding="utf-8") as file:
                json.dump(matchings, file, ensure_ascii=False, indent=4, default=str)
            xml_str = xmlify.xml_alignment_generator(matchings=matchings)
            with open(dir_dir / f"{mode}_matchings.xml", "w", encoding="utf-8") as file:
                file.write(xml_str)
            matched_files[mode] = matchings

        positives[direction] = matched_files
        print(f"{encoder_name}/{direction}: heuristic {len(matched_files['heuristic'])}, "
              f"hybrid {len(matched_files['hybrid'])}")

    bidirectional = {}
    for mode in ("heuristic", "hybrid"):
        fw_rows = [rag_config.swapped(r) for r in positives["wab2witt"][mode]]
        rev_rows = [rag_config.swapped(r) for r in positives["witt2wab"][mode]]
        fw_pairs = {rag_config.canonical_pair(r) for r in fw_rows}
        rev_pairs = {rag_config.canonical_pair(r) for r in rev_rows}
        both_rows = [{"source": s, "target": t, "relation": "="}
                     for s, t in sorted(fw_pairs & rev_pairs, key=str)]
        entry = {"fw": metrics.evaluation_report(predicts=fw_rows, references=reference),
                 "rev": metrics.evaluation_report(predicts=rev_rows, references=reference),
                 "both": metrics.evaluation_report(predicts=both_rows, references=reference)}
        bidirectional[mode] = entry
        with open(run_dir / f"bidirectional_{mode}.json", "w", encoding="utf-8") as file:
            json.dump(both_rows, file, ensure_ascii=False, indent=4, default=str)
        with open(run_dir / f"bidirectional_{mode}.xml", "w", encoding="utf-8") as file:
            file.write(xmlify.xml_alignment_generator(matchings=both_rows))
        print(f"\n=== {encoder_name} / {mode} bidirectional ===")
        print(" fw:", entry["fw"])
        print(" rev:", entry["rev"])
        print(" both:", entry["both"])

    with open(run_dir / "bidirectional_summary.json", "w", encoding="utf-8") as file:
        json.dump(bidirectional, file, ensure_ascii=False, indent=4, default=str)

print("\nSaved -> results/rag/")
