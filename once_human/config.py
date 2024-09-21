import json
import os
from dataclasses import InitVar, field, dataclass
from functools import lru_cache

import tomllib


@dataclass
class DatabaseSettings:
    dialect: str


@dataclass
class GoogleSheet:
    id: int
    headers: int = 1
    sync_mode: str = "BATCH"

    def url(self, document_id):
        sync_mode_str = (
            f"sync_mode={self.sync_mode}" if self.sync_mode != "BIDIRECTIONAL" else ""
        )
        headers_str = f"headers={self.headers}"
        id_str = f"gid={self.id}#gid={self.id}"
        query_str = "&".join([sync_mode_str, headers_str, id_str])
        url = f"https://docs.google.com/spreadsheets/d/{document_id}/edit?{query_str}"

        return url


@dataclass
class GoogleSheetsDatabaseSettings(DatabaseSettings):
    document_id: str

    service_account_path: InitVar[str]
    sheets_config: InitVar[dict[str, int | dict[str, int | str]]]
    service_account: dict[str, str] = field(init=False)
    sheets: dict[str, GoogleSheet] = field(init=False)

    def catalog(self):
        catalog = {
            name: self.sheets[name].url(self.document_id) for name in self.sheets.keys()
        }
        return catalog

    def __post_init__(self, service_account_path, sheets_config):
        with open(os.path.join("..", service_account_path)) as fp:
            self.service_account = json.load(fp)

        sheets = {}
        for sheet_name, data in sheets_config.items():
            if isinstance(data, int):
                sheets[sheet_name] = GoogleSheet(id=data)
            else:
                sheets[sheet_name] = GoogleSheet(**data)
        self.sheets = sheets


@dataclass
class Settings:
    db: DatabaseSettings


@lru_cache
def load_config() -> Settings:
    default_config_dir = os.path.dirname(os.path.abspath(__file__))
    default_config_file = os.path.join(default_config_dir, "..", "config.toml")
    config_file = os.getenv("ONCE_HUMAN_CONFIG_FILE", default_config_file)
    with open(config_file, "rb") as fp:
        data = tomllib.load(fp)

    db_dialect = data["db"]["dialect"]
    if db_dialect == "gsheets":
        cls = GoogleSheetsDatabaseSettings
        data["db"][db_dialect]["sheets_config"] = data["db"][db_dialect].pop("sheets")
    else:
        cls = None
    db_settings = cls(db_dialect, **data["db"][db_dialect])

    settings = Settings(db_settings)

    return settings


config = load_config()
