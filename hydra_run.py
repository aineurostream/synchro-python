from typing import cast, Any

from omegaconf import DictConfig, OmegaConf
import hydra

from synchro.config.schemas import ProcessingGraphConfig
from synchro.config.settings import SettingsSchema
from synchro.core import CoreManager


@hydra.main(version_base=None, config_path="config", config_name="config")
def hydra_app(cfg: DictConfig) -> None:
    print(OmegaConf.to_yaml(cfg))
    """Start an instance of the Synchro application"""

    pipeline_config = cast(DictConfig, cfg["pipeline"])
    neural_config = cast(DictConfig, cfg["ai"])
    settings_config = cast(DictConfig, cfg["settings"])

    core_config = ProcessingGraphConfig.model_validate(pipeline_config)
    settings = SettingsSchema.model_validate(settings_config)
    neural_config_dict = OmegaConf.to_container(neural_config)

    core = CoreManager(core_config, neural_config_dict, settings)
    core.run()

if __name__ == "__main__":
    hydra_app()