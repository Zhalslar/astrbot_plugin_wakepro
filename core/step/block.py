import re

from ..config import PluginConfig
from ..model import StepName, StepResult, WakeContext
from .base import BaseStep


class BlockStep(BaseStep):
    name = StepName.BLOCK

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.cfg = config.block

    async def handle(self, ctx: WakeContext) -> StepResult:
        # 违禁词阻塞
        if self.cfg.keywords and ctx.plain:
            for w in self.cfg.keywords:
                if w in ctx.plain:
                    return StepResult(wake=False, abort=True, msg=f"包含违禁词: {w}")
        # 复读阻塞
        if self.cfg.reread and ctx.plain and ctx.group:
            cleaned = re.sub(r"[^\w\u4e00-\u9fff]", "", ctx.plain).lower()
            for msg in ctx.group.bot_msgs:
                if not msg:
                    continue
                m = re.sub(r"[^\w\u4e00-\u9fff]", "", msg).lower()
                if cleaned == m:
                    return StepResult(wake=False, abort=True, msg=f"已阻止复读: {msg}")
        # 唤醒CD阻塞
        if (
            self.cfg.wake_cd > 0
            and ctx.member
            and ctx.now - ctx.member.last_wake < self.cfg.wake_cd
        ):
            return StepResult(
                wake=False,
                abort=True,
                msg=f"唤醒冷却中({self.cfg.wake_cd}秒)，已阻止唤醒",
            )

        return StepResult()
