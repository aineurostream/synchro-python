from typing import cast, Any

from omegaconf import DictConfig, OmegaConf
import hydra

from synchro.config.schemas import ProcessingGraphConfig
from synchro.core import CoreManager


@hydra.main(version_base=None)
def hydra_app(cfg: DictConfig) -> None:
    print(OmegaConf.to_yaml(cfg))
    """Start an instance of the Synchro application"""

    pipeline_config = cast(dict[str, Any], cfg["pipeline_config"])
    neural_config = cast(dict[str, Any], cfg["neural_config"])

    core_config = ProcessingGraphConfig.model_validate(pipeline_config)

    core = CoreManager(core_config, neural_config)
    core.run()