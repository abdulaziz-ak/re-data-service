from __future__ import annotations

import hashlib
import json
import logging
from typing import Protocol, TypeVar

from pydantic import BaseModel

from re_data.config import Settings

log = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)


class MarketResponseCache(Protocol):
    def build_key(self, endpoint: str, dataset_version: str, params: dict[str, object]) -> str: ...

    def get_model(self, key: str, model_type: type[ModelT]) -> ModelT | None: ...

    def set_model(self, key: str, value: BaseModel) -> None: ...

    def close(self) -> None: ...


class NullMarketResponseCache:
    def build_key(self, endpoint: str, dataset_version: str, params: dict[str, object]) -> str:
        return ""

    def get_model(self, key: str, model_type: type[ModelT]) -> ModelT | None:
        return None

    def set_model(self, key: str, value: BaseModel) -> None:
        return None

    def close(self) -> None:
        return None


class RedisMarketResponseCache:
    def __init__(self, redis_client: object, *, ttl_s: int, namespace: str = "market") -> None:
        self._redis = redis_client
        self._ttl_s = ttl_s
        self._namespace = namespace

    def build_key(self, endpoint: str, dataset_version: str, params: dict[str, object]) -> str:
        payload = json.dumps(params, sort_keys=True, separators=(",", ":"), default=str)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"{self._namespace}:{endpoint}:{dataset_version}:{digest}"

    def get_model(self, key: str, model_type: type[ModelT]) -> ModelT | None:
        try:
            raw = self._redis.get(key)  # type: ignore[attr-defined]
        except Exception as exc:
            log.warning("redis cache get failed for %s: %s", key, exc)
            return None
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            return model_type.model_validate_json(str(raw))
        except Exception as exc:
            log.warning("redis cache payload invalid for %s: %s", key, exc)
            return None

    def set_model(self, key: str, value: BaseModel) -> None:
        try:
            self._redis.setex(  # type: ignore[attr-defined]
                key,
                self._ttl_s,
                value.model_dump_json(),
            )
        except Exception as exc:
            log.warning("redis cache set failed for %s: %s", key, exc)

    def close(self) -> None:
        try:
            self._redis.close()  # type: ignore[attr-defined]
        except Exception as exc:
            log.warning("redis cache close failed: %s", exc)


def create_market_cache(settings: Settings) -> MarketResponseCache:
    if not settings.redis_url:
        return NullMarketResponseCache()

    try:
        from redis import Redis
    except ImportError:
        log.warning("REDIS_URL is set but redis package is not installed")
        return NullMarketResponseCache()

    try:
        client = Redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
    except Exception as exc:
        log.warning("redis unavailable, market cache disabled: %s", exc)
        return NullMarketResponseCache()

    return RedisMarketResponseCache(
        client,
        ttl_s=settings.market_cache_ttl_s,
    )
