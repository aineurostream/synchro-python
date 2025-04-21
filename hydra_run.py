import json
import os
import shutil
from collections import defaultdict
from collections.abc import Callable
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

        if isinstance(node, InputFileStreamerNodeSchema):
            file_path = cast(str, node.path)
        elif isinstance(node, OutputFileNodeSchema):
            node_path = str(node.path)
            if "$WORKING_DIR" in node_path:
                node_path = node_path.replace("$WORKING_DIR", hydra_dir)
            file_path = node_path

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


def initialize_configs(
    cfg: DictConfig,
) -> tuple[ProcessingGraphConfig, SettingsSchema, Any]:
    pipeline_config = cast(DictConfig, cfg["pipeline"])
    neural_config = cast(DictConfig, cfg["ai"])
    settings_config = cast(DictConfig, cfg["settings"])

    core_config = ProcessingGraphConfig.model_validate(pipeline_config)
    settings = SettingsSchema.model_validate(settings_config)
    neural_config_dict = OmegaConf.to_container(neural_config)

    return core_config, settings, neural_config_dict


def create_node_event_callback(
    generated_texts: dict[str, dict[str, str]],
) -> Callable[[str, dict[str, Any]], None]:
    def node_event_callback(node_name: str, log: dict[str, Any]) -> None:
        context = log["context"]
        action = context.get("action")

        if node_name not in generated_texts:
            generated_texts[node_name] = defaultdict(str)

        generated_texts[node_name][KEY_CHANNEL_NAME] = log["id"]
        if context.get("sub_action") == "fail":
            return

        action_mapping = {
            "transcription": (KEY_TRANSCRIBED_TEXT, "text"),
            "translation": (KEY_TRANSLATED_TEXT, "translation"),
            "correction": (KEY_CORRECTED_TEXT, "correction"),
            "synthesis": (KEY_RESULTING_TEXT, "text"),
        }

        if action in action_mapping:
            key, field = action_mapping[action]
            if field in context:
                generated_texts[node_name][key] += " " + context[field]

    return node_event_callback


def calculate_quality_metrics(
    generated_texts: dict[str, dict[str, str]],
    settings: SettingsSchema,
    hydra_dir: str,
) -> float:
    total_bleu_score = 0.0
    quality_store: dict[str, dict[str, str | dict[str, str | float]]] = defaultdict(
        dict,
    )

    for quality_info in settings.metrics.quality:
        append_quality_values(quality_info, generated_texts, quality_store)
        quality_store[quality_info.node][KEY_CHANNEL_NAME] = generated_texts[
            quality_info.node
        ][KEY_CHANNEL_NAME]

        resulting_part = quality_store[quality_info.node].get(KEY_RESULTING_TEXT)
        if isinstance(resulting_part, dict):
            score = resulting_part["bleu_score"]
            total_bleu_score += float(score) * quality_info.weight

    with open(
        os.path.join(hydra_dir, "meta_store.json"),
        "w",
        encoding="utf-8",
    ) as meta_file:
        json.dump(quality_store, meta_file, indent=4, ensure_ascii=False)

    return total_bleu_score


def append_quality_values(
    quality_info: QualityInfo,
    generated_texts: dict[str, dict[str, str]],
    quality_store: dict[str, dict[str, str | dict[str, str | float]]],
) -> None:
    append_value(
        KEY_TRANSCRIBED_TEXT,
        quality_info.expected_transcription,
        quality_info,
        generated_texts,
        quality_store,
    )
    append_value(
        KEY_TRANSLATED_TEXT,
        quality_info.expected_translation,
        quality_info,
        generated_texts,
        quality_store,
    )
    append_value(
        KEY_CORRECTED_TEXT,
        quality_info.expected_translation,
        quality_info,
        generated_texts,
        quality_store,
    )
    append_value(
        KEY_RESULTING_TEXT,
        quality_info.expected_translation,
        quality_info,
        generated_texts,
        quality_store,
    )


def append_value(
    mode: str,
    expected: str,
    quality_info: QualityInfo,
    generated_texts: dict[str, dict[str, str]],
    quality_store: dict[str, dict[str, str | dict[str, str | float]]],
) -> None:
    node = quality_info.node

    if node not in generated_texts:
        available_nodes = ", ".join(list(generated_texts.keys()))
        raise ValueError(
            f"Node '{node}' not found in generated_texts. "
            f"Available nodes: [{available_nodes}]",
        )

    node_texts = generated_texts[node]
    if mode not in node_texts:
        return

    try:
        quality_store[node][mode] = generate_report_on_bleu(
            expected,
            node_texts[mode],
        )
    except Exception as e:
        raise RuntimeError(
            "Failed to calculate BLEU score for "
            f"node '{node}', mode '{mode}': {e!s}",
        ) from e


@hydra.main(version_base=None, config_path="config", config_name="config")
def hydra_app(cfg: DictConfig) -> float:
    hydra_dir: str = hydra.core.hydra_config.HydraConfig.get().runtime.output_dir

    core_config, settings, neural_config_dict = initialize_configs(cfg)
    generated_texts: dict[str, dict[str, str]] = {}
    node_event_callback = create_node_event_callback(generated_texts)

    from synchro.core import CoreManager

    core = CoreManager(
        pipeline_config=core_config,
        neuro_config=neural_config_dict,
        settings=settings,
        events_cb=node_event_callback,
        working_dir=hydra_dir,
    )
    core.run()

    persist_files(core_config, hydra_dir)

    return calculate_quality_metrics(generated_texts, settings, hydra_dir)


if __name__ == "__main__":
    hydra_app()
