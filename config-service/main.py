
import os
from pathlib import Path

import yaml
from dotenv import dotenv_values
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware


BASE_DIR = Path(__file__).resolve().parent

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

app = FastAPI(title="Effective Configuration API")

# Allow the assignment page to call this API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def normalize_key(key: str) -> str:
    """Convert configuration keys to lowercase."""
    return key.strip().lower()


def coerce_value(key: str, value):
    """Convert configuration values to their required types."""
    key = normalize_key(key)

    if key in ("port", "workers"):
        return int(value)

    if key == "debug":
        if isinstance(value, bool):
            return value

        return str(value).strip().lower() in {
            "true", "1", "yes", "on"
        }

    return str(value)


def apply_layer(config: dict, values: dict) -> None:
    """Apply one layer without replacing unrelated settings."""
    for key, value in values.items():
        if value is None:
            continue

        key = normalize_key(key)

        if key == "num_workers":
            key = "workers"

        config[key] = coerce_value(key, value)


def load_configuration() -> dict:
    config = DEFAULTS.copy()

    # Layer 2: config.<env>.yaml
    # APP_ENV selects the environment; development is the default.
    environment = os.environ.get("APP_ENV", "development")
    yaml_path = BASE_DIR / f"config.{environment}.yaml"

    if yaml_path.exists():
        with yaml_path.open("r", encoding="utf-8") as file:
            yaml_config = yaml.safe_load(file) or {}

        apply_layer(config, yaml_config)

    # Layer 3: .env
    env_path = BASE_DIR / ".env"
    file_env = dotenv_values(env_path)

    file_config = {
        key[4:].lower(): value
        for key, value in file_env.items()
        if key.startswith("APP_") and key != "APP_ENV"
    }

    # Special alias: NUM_WORKERS -> workers
    if file_env.get("NUM_WORKERS") is not None:
        file_config["num_workers"] = file_env["NUM_WORKERS"]

    apply_layer(config, file_config)

    # Layer 4: actual OS environment variables.
    # These override values loaded from the .env file.
    os_config = {
        key[4:].lower(): value
        for key, value in os.environ.items()
        if key.startswith("APP_") and key != "APP_ENV"
    }

    apply_layer(config, os_config)

    return config


@app.get("/effective-config")
async def effective_config(request: Request):
    config = load_configuration()

    # Layer 5: repeated CLI-style query overrides.
    # Example: ?set=port=9000&set=debug=true
    for item in request.query_params.getlist("set"):
        key, separator, value = item.partition("=")

        if not separator or not key.strip():
            continue

        key = normalize_key(key)

        if key == "num_workers":
            key = "workers"

        config[key] = coerce_value(key, value)

    # Never return the actual API key.
    if "api_key" in config:
        config["api_key"] = "****"

    return config


@app.get("/")
async def root():
    return {
        "message": "Configuration API is running",
        "endpoint": "/effective-config",
    }
