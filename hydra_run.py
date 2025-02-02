import json
import os
import shutil
from collections import defaultdict
from typing import Any, cast

import hydra
from omegaconf import DictConfig, OmegaConf

from synchro.config.schemas import (
    InputFileStreamerNodeSchema,
    OutputFileNodeSchema,
    ProcessingGraphConfig,
)
from synchro.config.settings import QualityInfo, SettingsSchema
from synchro.logging import setup_logging

setup_logging()

KEY_TRANSCRIBED_TEXT = "transcribed"
KEY_TRANSLATED_TEXT = "translated"
KEY_CORRECTED_TEXT = "corrected"
KEY_RESULTING_TEXT = "resulting"
KEY_CHANNEL_NAME = "channel"


def file_resolver(path: str) -> bytes:
    with open(path, "rb") as fp:
        return fp.read()


OmegaConf.register_new_resolver(
    "file",
    file_resolver,
)


def split_string_bleu(text: str) -> list[str]:
    text = (
        text.replace("\n", " ")
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
        if isinstance(node, InputFileStreamerNodeSchema | OutputFileNodeSchema):
            file_path = cast(str, node.path)
        if file_path:
            shutil.copy(
                file_path,
                os.path.join(hydra_dir, f"{node_name}_{os.path.basename(file_path)}"),
            )


def provide_bleu_for_text(base: str, resulted: str) -> tuple[float, float]:
    from jiwer import wer
    from nltk.translate.bleu_score import sentence_bleu

    base_split = split_string_bleu(base)
    result_split = split_string_bleu(resulted)
    result = sentence_bleu([base_split], result_split)
    wer_result = wer(" ".join(base), " ".join(resulted))
    return cast(float, result), wer_result


def generate_report_on_bleu(
    reference: str,
    hypothesis: str,
) -> dict[str, str | float]:
    bleu_score, wer_score = provide_bleu_for_text(reference, hypothesis)
    return {
        "reference": reference,
        "hypothesis": hypothesis,
        "bleu_score": bleu_score,
        "wer_score": wer_score,
    }


@hydra.main(version_base=None, config_path="config", config_name="config")
def hydra_app(cfg: DictConfig) -> float:
    hydra_dir: str = hydra.core.hydra_config.HydraConfig.get().runtime.output_dir
    """Start an instance of the Synchro application"""

    pipeline_config = cast(DictConfig, cfg["pipeline"])
    neural_config = cast(DictConfig, cfg["ai"])
    settings_config = cast(DictConfig, cfg["settings"])

    core_config = ProcessingGraphConfig.model_validate(pipeline_config)
    settings = SettingsSchema.model_validate(settings_config)
    neural_config_dict = OmegaConf.to_container(neural_config)

    generated_texts: dict[str, dict[str, str]] = defaultdict(lambda: defaultdict(str))

    def node_event_callback(node_name: str, log: dict[str, Any]) -> None:
        action = log["context"].get("action")
        if action == "got_translation":
            generated_texts[node_name][KEY_TRANSCRIBED_TEXT] += (
                " " + log["context"]["text"]
            )
            generated_texts[node_name][KEY_TRANSLATED_TEXT] += (
                " " + log["context"]["translation"]
            )
            generated_texts[node_name][KEY_CHANNEL_NAME] = log["id"]
        elif action == "got_correction":
            generated_texts[node_name][KEY_CORRECTED_TEXT] += (
                " " + log["context"]["correction"]
            )
        elif action == "synthesizing_text":
            generated_texts[node_name][KEY_RESULTING_TEXT] += (
                " " + log["context"]["text"]
            )

    from synchro.core import CoreManager

    core = CoreManager(core_config, neural_config_dict, settings, node_event_callback)
    core.run()

    persist_files(core_config, hydra_dir)

    # Calculating BLEU
    total_bleu_score = 0.0
    quality_store: dict[str, dict[str, str | dict[str, str | float]]] = defaultdict(
        dict,
    )

    def append_value(
        mode: str,
        expected: str,
        quality_info: QualityInfo,
    ) -> None:
        quality_store[quality_info.node][mode] = generate_report_on_bleu(
            expected,
            generated_texts[quality_info.node][mode],
        )

    for quality_info in settings.metrics.quality:
        append_value(
            KEY_TRANSCRIBED_TEXT,
            quality_info.expected_transcription,
            quality_info,
        )
        append_value(
            KEY_TRANSLATED_TEXT,
            quality_info.expected_translation,
            quality_info,
        )
        append_value(
            KEY_CORRECTED_TEXT,
            quality_info.expected_translation,
            quality_info,
        )
        append_value(
            KEY_RESULTING_TEXT,
            quality_info.expected_translation,
            quality_info,
        )
        quality_store[quality_info.node][KEY_CHANNEL_NAME] = generated_texts[
            quality_info.node
        ][KEY_CHANNEL_NAME]

        total_bleu_score += (
            quality_store[quality_info.node][KEY_RESULTING_TEXT]["bleu_score"]  # type: ignore
            * quality_info.weight
        )

    with open(os.path.join(hydra_dir, "meta_store.json"), "w") as meta_file:
        json.dump(quality_store, meta_file, indent=4, ensure_ascii=False)

    return total_bleu_score


if __name__ == "__main__":
    hydra_app()
