from typing import cast

from omegaconf import DictConfig, OmegaConf
import hydra

from synchro.config.schemas import ProcessingGraphConfig
from synchro.core import CoreManager


@hydra.main(version_base=None)
def hydra_app(cfg: DictConfig) -> None:
    print(OmegaConf.to_yaml(cfg))
    """Start an instance of the Synchro application"""

    graph_file = cast(str, cfg["graph_file"])

    with open(graph_file) as config_file:
        core_config = ProcessingGraphConfig.model_validate_json(
            config_file.read(),
        )

    core = CoreManager(core_config)
    core.run()