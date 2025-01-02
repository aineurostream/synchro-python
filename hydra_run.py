import json
from collections import defaultdict

from synchro.logging import setup_logging

from typing import cast, Any

from omegaconf import DictConfig, OmegaConf
import hydra
import shutil
import os

from synchro.config.schemas import ProcessingGraphConfig, InputFileStreamerNodeSchema, OutputFileNodeSchema
from synchro.config.settings import SettingsSchema


def split_string_bleu(text: str) -> list[str]:
    text = (
        text
        .replace("\n", " ")
        .replace(".", " ")
        .replace(",", " ")
        .replace("!", " ")
        .replace("?", " ")
        .replace(":", " ")
    )
    return [word.lower() for word in text.split() if word]

def persist_files(pipeline: ProcessingGraphConfig, hydra_dir: str) -> None:
    for node in pipeline.nodes:
        node_name: str = node.name
        file_path: str = ""
        if isinstance(node, InputFileStreamerNodeSchema):
            file_path = node.path
        elif isinstance(node, OutputFileNodeSchema):
            file_path = node.path
        if file_path:
            shutil.copy(
                file_path,
                os.path.join(hydra_dir, f"{node_name}_{os.path.basename(file_path)}")
            )


@hydra.main(version_base=None, config_path="config", config_name="config")
def hydra_app(cfg: DictConfig) -> float:
    hydra_dir: str = hydra.core.hydra_config.HydraConfig.get().runtime.output_dir
    setup_logging()
    """Start an instance of the Synchro application"""

    pipeline_config = cast(DictConfig, cfg["pipeline"])
    neural_config = cast(DictConfig, cfg["ai"])
    settings_config = cast(DictConfig, cfg["settings"])

    core_config = ProcessingGraphConfig.model_validate(pipeline_config)
    settings = SettingsSchema.model_validate(settings_config)
    neural_config_dict = OmegaConf.to_container(neural_config)

    bleu_cb: dict[str, str] = defaultdict(str)

    def node_event_callback(node_name: str, log: dict[str, Any]) -> None:
        if log["context"].get("action") == "synthesizing_text":
            bleu_cb[node_name] += log["context"]["text"]

    from synchro.core import CoreManager
    core = CoreManager(core_config, neural_config_dict, settings, node_event_callback)
    core.run()

    persist_files(core_config, hydra_dir)

    # Calculating BLEU
    total_bleu_score = 0.0
    bleu_eval: dict[str, dict[str, str | float]] = defaultdict(dict)
    for bleu_experiment in settings.experiments.bleu:
        from nltk.translate.bleu_score import sentence_bleu
        reference = bleu_experiment.expected_text
        hypothesis = bleu_cb[bleu_experiment.node]
        bleu_score = sentence_bleu(
            [split_string_bleu(reference)],
            split_string_bleu(hypothesis),
        )
        total_bleu_score += bleu_score * bleu_experiment.weight
        bleu_eval[bleu_experiment.node] = {
            "reference": reference,
            "hypothesis": hypothesis,
            "bleu_score": bleu_score,
            "weight": bleu_experiment.weight,
        }
        print(f"BLEU for {bleu_experiment.node}: {bleu_score}")

    with open(os.path.join(hydra_dir, "bleu_eval.json"), "w") as bleu_eval_file:
        json.dump(bleu_eval, bleu_eval_file, indent=4)

    return total_bleu_score


if __name__ == "__main__":
    hydra_app()