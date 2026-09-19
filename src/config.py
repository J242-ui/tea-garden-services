"""茶园气象服务系统 - 配置管理。"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

load_dotenv(BASE_DIR / ".env")


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def get_weather_api_key() -> str:
    return os.getenv("QWEATHER_API_KEY", "").strip()


def get_qianfan_api_key() -> str:
    return os.getenv("QIANFAN_API_KEY", "").strip()


def get_qianfan_model() -> str:
    return os.getenv("QIANFAN_MODEL", "ernie-4.0-8k").strip()


def is_demo_mode() -> bool:
    return _env_bool("DEMO_MODE")


def load_gardens() -> list[dict]:
    """从 data/tea_gardens.json 读取茶园配置。"""
    path = DATA_DIR / "tea_gardens.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)["gardens"]


def get_garden(garden_id: str) -> dict | None:
    for g in load_gardens():
        if g["id"] == garden_id:
            return g
    return None
