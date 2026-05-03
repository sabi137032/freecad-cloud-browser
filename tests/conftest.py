import os
import pytest
from core.config_store import ConfigStore
from core.file_cache import FileCache


@pytest.fixture()
def config_store(tmp_path):
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    return ConfigStore(config_path=str(cfg_dir / "config.json"))


@pytest.fixture()
def cache(tmp_path):
    return FileCache(cache_dir=str(tmp_path / "cache"))
