import json
from pathlib import Path


class Config:
    def __init__(self):
        self.config_file = Path.cwd() / "config.json"
        self.data = self.load_config()

    def load_config(self) -> dict:
        if self.config_file.exists():
            return json.loads(self.config_file.read_text())
        return {}

    def save_config(self) -> None:
        self.config_file.write_text(json.dumps(self.data, indent=4))

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value) -> None:
        self.data[key] = value
        self.save_config()
