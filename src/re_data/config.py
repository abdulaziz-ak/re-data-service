from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SQM_TO_SQFT = Decimal("10.7639104167")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )

    benchmarks_csv_paths: str = Field(default="", validation_alias="BENCHMARKS_CSV_PATHS")
    index_csv_path: str = Field(
        default="/data/Residential_Sale_Index.csv",
        validation_alias="INDEX_CSV_PATH",
    )
    dld_area_unit: str = Field(default="sqm", validation_alias="DLD_AREA_UNIT")
    ppsf_min: Decimal = Field(default=Decimal("100"), validation_alias="PPSF_MIN")
    ppsf_max: Decimal = Field(default=Decimal("20000"), validation_alias="PPSF_MAX")
    port: int = Field(default=8001, validation_alias="PORT")
    app_env: str = Field(default="local", validation_alias="APP_ENV")

    @field_validator("dld_area_unit", mode="before")
    @classmethod
    def _norm_unit(cls, v: object) -> str:
        return str(v or "sqm").strip().lower()

    @field_validator("ppsf_min", "ppsf_max", mode="before")
    @classmethod
    def _to_decimal(cls, v: object) -> Decimal:
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v).strip())

    def transaction_paths(self) -> list[Path]:
        raw = self.benchmarks_csv_paths.strip()
        if not raw:
            return []
        paths: list[Path] = []
        for part in raw.split(";"):
            part = part.strip().strip('"')
            if part:
                paths.append(Path(part))
        return paths

    def index_path(self) -> Path | None:
        raw = self.index_csv_path.strip().strip('"')
        if not raw:
            return None
        return Path(raw)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
