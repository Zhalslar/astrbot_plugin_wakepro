from __future__ import annotations

from astrbot.api import logger

from .config import PluginConfig
from .model import WakeContext
from .step import (
    BaseStep,
    BlockStep,
    CommandStep,
    DebounceStep,
    SilenceStep,
    WakeStep,
)


class Pipeline:
    """
    生产级 Pipeline：

    - 构建 step 实例
    - 统一 initialize / terminate
    - 对外唯一接口：run
    """

    STEP_REGISTRY: list[type[BaseStep]] = [
        DebounceStep,
        BlockStep,
        WakeStep,
        CommandStep,
        SilenceStep,
    ]

    def __init__(self, config: PluginConfig):
        self.plugin_config = config
        self._steps: list[BaseStep] = []
        self._debounce_step: DebounceStep | None = None
        self._build_steps()

    def _build_steps(self) -> None:
        for cls in self.STEP_REGISTRY:
            step = cls(self.plugin_config)
            if isinstance(step, DebounceStep):
                self._debounce_step = step
            self._steps.append(step)

    # ==================== run =====================

    async def run(self, ctx: WakeContext):
        for step in self._steps:
            if not self.plugin_config.pipeline.is_enabled_step(step.name):
                continue
            if self.plugin_config.pipeline.in_whitelist(
                step.name, ctx.umo, ctx.uid, ctx.gid
            ):
                logger.debug(f"步骤 {step.name} 被白名单跳过")
                continue
            if self.plugin_config.pipeline.in_blacklist(
                step.name, ctx.umo, ctx.uid, ctx.gid
            ):
                logger.debug(f"步骤 {step.name} 被黑名单跳过")
                continue
            # 执行
            result = await step.handle(ctx)
            # 标记唤醒
            if result.wake is True:
                if ctx.member:
                    ctx.member.last_wake = ctx.now
                ctx.event.is_at_or_wake_command = True
                if self._debounce_step:
                    await self._debounce_step.activate_window(ctx)
            # 停止事件传播
            elif result.wake is False:
                ctx.event.stop_event()
            # 日志
            if result.msg:
                logger.debug(result.msg)
            # 记录延长唤醒
            if ctx.member:
                ctx.member.can_prolong = result.prolong
            # 中断流水线
            if result.abort:
                break
