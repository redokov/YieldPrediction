from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Конфигурация RLM"""
    buffer_meters: int = 500
    max_cloud_cover: int = 30
    contour_linewidth: int = 3
    save_rgb_no_contour: bool = True
    ini_file: str = "rlm.ini"
    default_start_date: str = "2024-04-01"
    default_end_date: str = "2024-04-30"
    copernicus_username: Optional[str] = None
    copernicus_password: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    litellm_model: str = "openrouter/qwen/qwen3-70b"

    model_config = {
        "env_file": ".env",
        "env_prefix": "RLM_",
        "extra": "ignore"
    }



def _load_ini():
    from pathlib import Path
    import configparser, os
    ini = Path(settings.ini_file) if hasattr(settings,'ini_file') else Path('rlm.ini')
    if not ini.exists():
        return
    cfg = configparser.ConfigParser()
    cfg.read(ini, encoding='utf-8')
    for sec in cfg.sections():
        for key in cfg[sec]:
            val = cfg[sec][key]
            if hasattr(settings, key):
                current = getattr(settings, key)
                if isinstance(current, bool):
                    setattr(settings, key, cfg.getboolean(sec, key))
                elif isinstance(current, int):
                    setattr(settings, key, cfg.getint(sec, key))
                elif isinstance(current, float):
                    setattr(settings, key, cfg.getfloat(sec, key))
                else:
                    setattr(settings, key, val)

settings = Settings()
_load_ini()
