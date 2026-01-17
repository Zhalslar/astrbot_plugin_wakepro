# config.py
from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any, get_type_hints

from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.star.context import Context

# ==================================================
# 基础 Section
# ==================================================


class Section:
    """
    强类型配置节点
    - 字段由注解声明
    - 数据直接映射到底层 dict
    """

    __slots__ = ("_data",)

    def __init__(self, data: MutableMapping[str, Any]):
        object.__setattr__(self, "_data", data)

        hints = get_type_hints(self.__class__)
        for key in hints:
            if key not in data:
                raise KeyError(f"缺少配置字段: {key}")

    def __getattr__(self, key: str) -> Any:
        try:
            return self._data[key]
        except KeyError:
            raise AttributeError(key) from None

    def __setattr__(self, key: str, value: Any) -> None:
        if key.startswith("_"):
            object.__setattr__(self, key, value)
        else:
            self._data[key] = value

    def raw(self) -> MutableMapping[str, Any]:
        return self._data


# ==================================================
# Section 定义
# ==================================================


class PipelineConfig(Section):
    lock_order: bool
    steps: list[str]
    admin_steps: list[str]

    def __init__(self, data: MutableMapping[str, Any]):
        super().__init__(data)

        self._steps = self._normalize(self.steps)
        self._admin_steps = self._normalize(self.admin_steps)

    @staticmethod
    def _normalize(steps: list[str]) -> list[str]:
        return [s.split("(", 1)[0].strip() for s in steps]

    def is_enabled_step(self, step: str) -> bool:
        return step in self._steps

    def is_admin_step(self, step: str) -> bool:
        return step in self._admin_steps


class GateConfig(Section):
    block_self: bool
    block_qqbot: bool
    white_users: list[str]
    white_groups: list[str]
    black_users: list[str]
    black_groups: list[str]


class BlockConfig(Section):
    keywords: list[str]
    reread: bool
    wake_cd: float


class CmdConfig(Section):
    builtin_cmds: list[str]
    block_builtin: bool
    block_prefix_cmd: bool
    block_prefix_llm: bool


class WakeConfig(Section):
    names: list[str]
    prolong: float
    similar: float
    ask: float
    bored: float
    interest_words_str: list[str]
    interest: float
    prob: float

    def __init__(self, data: MutableMapping[str, Any]):
        super().__init__(data)
        self._interest_words = [w.split() for w in self.interest_words_str]


class SilenceConfig(Section):
    shutup: float
    insult: float
    ai: float
    multiple: float


# ==================================================
# Facade
# ==================================================


class TypedConfigFacade:
    __annotations__: dict[str, type]

    def __init__(self, cfg: AstrBotConfig):
        object.__setattr__(self, "_cfg", cfg)

        hints = get_type_hints(self.__class__)
        for key, tp in hints.items():
            if key.startswith("_"):
                continue
            if not isinstance(tp, type) or not issubclass(tp, Section):
                continue
            if key not in cfg:
                raise KeyError(f"缺少配置段: {key}")

            section = tp(cfg[key])
            object.__setattr__(self, key, section)

    def __getattr__(self, key: str) -> Any:
        return self._cfg[key]

    def save(self):
        self._cfg.save_config()


# ==================================================
# 插件配置入口
# ==================================================


class PluginConfig(TypedConfigFacade):
    pipeline: PipelineConfig
    gate: GateConfig
    block: BlockConfig
    cmd: CmdConfig
    wake: WakeConfig
    silence: SilenceConfig

    def __init__(self, config: AstrBotConfig, *, context: Context):
        super().__init__(config)
        self.context = context
        self.wake_prefix: list[str] = self.context.get_config().get("wake_prefix", [])
        self.admins_id: list[str] = context.get_config().get("admins_id", [])
