from __future__ import annotations

from astrbot.api import logger

from .config import PluginConfig
from .model import WakeContext
from .step import BaseStep, BlockStep, CommandStep, GateStep, SilenceStep, WakeStep


class Pipeline:
    """
    生产级 Pipeline：

    - 构建 step 实例
    - 统一 initialize / terminate
    - 对外唯一接口：run
    """

    # 默认顺序
    STEP_REGISTRY: list[tuple[str, type[BaseStep]]] = [
        ("gate", GateStep),
        ("block", BlockStep),
        ("wake", WakeStep),
        ("command", CommandStep),
        ("silence", SilenceStep),
    ]

    def __init__(self, config: PluginConfig):
        self.plugin_config = config
        self.cfg = config.pipeline
        self._steps: list[BaseStep] = []
        self._build_steps()

    def _build_steps(self) -> None:
        """
        根据配置构建步骤实例（默认顺序或自定义顺序）
        """
        if self.cfg.lock_order:
            for name, cls in self.STEP_REGISTRY:
                if name in self.cfg._steps:
                    step = cls(self.plugin_config)
                    self._steps.append(step)
        else:
            step_map = dict(self.STEP_REGISTRY)
            for name in self.cfg._steps:
                cls = step_map.get(name)
                if not cls:
                    raise ValueError(f"Unknown pipeline step: {name}")
                step = cls(self.plugin_config)
                self._steps.append(step)

    # =================== Lifecycle =======================

    async def initialize(self) -> None:
        """初始化所有步骤"""
        for step in self._steps:
            await step.initialize()

    async def terminate(self) -> None:
        """终止所有步骤"""
        for step in self._steps:
            await step.terminate()

    # ==================== run =====================

    def _admin_skip(self, step_name: str, is_admin: bool) -> bool:
        if not self.cfg._admin_steps:
            return False
        return is_admin and step_name in self.cfg._admin_steps

    async def run(self, ctx: WakeContext):
        for step in self._steps:
            if self._admin_skip(step.name, ctx.is_admin):
                continue

            result = await step.handle(ctx)

            if result.wake is True:
                if ctx.member:
                    ctx.member.last_wake = ctx.now
                ctx.event.is_at_or_wake_command = True

            elif result.wake is False:
                ctx.event.stop_event()

            if result.msg:
                logger.debug(result.msg)

            if ctx.member:
                ctx.member.can_prolong = result.prolong

            if result.abort:
                break


