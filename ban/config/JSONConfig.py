import json


class JSONConfig:
    configuration = None

    @staticmethod
    def load_config(file_path: str = "./config.json") -> None:
        with open(file_path, 'r') as f:
            JSONConfig.configuration = json.load(f)

        if JSONConfig.configuration is None:
            raise Exception(f"configuration file not found on: {file_path}")

    @staticmethod
    def get_config(key: str | None = None) -> str:
        if JSONConfig.configuration is None:
            JSONConfig.load_config()

        if key is None:
            return JSONConfig.configuration

        return JSONConfig.configuration.get(key)
