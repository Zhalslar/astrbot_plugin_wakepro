
from astrbot.core.message.components import Plain

from ..config import PluginConfig
from ..model import StepName, StepResult, WakeContext
from .base import BaseStep


class CommandStep(BaseStep):
    name = StepName.COMMAND

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.cfg = config.cmd
        self.wake_prefix = config.wake_prefix

    async def handle(self, ctx: WakeContext) -> StepResult:
        if self.cfg.block_builtin and ctx.cmd and ctx.cmd in self.cfg.builtin_cmds:
            return StepResult(wake=False, abort=True, msg=f"命令 '{ctx.cmd}' 已被禁用")

        seg = ctx.chain[0] if ctx.chain and isinstance(ctx.chain[0], Plain) else None
        if seg and any(seg.text.startswith(p) for p in self.wake_prefix):

            # 屏蔽前缀触发指令
            if ctx.cmd and self.cfg.block_prefix_cmd:
                return StepResult(
                    wake=False, abort=True, msg=f"前缀触发的指令 '{ctx.cmd}' 已被禁用"
                )
            # 屏蔽前缀触发LLM
            if not ctx.cmd and self.cfg.block_prefix_llm:
                return StepResult(wake=False, abort=True, msg="前缀触发的LLM已被禁用")
            # 前缀唤醒
            if ctx.cmd:
                return StepResult(wake=True, msg=f"前缀（{ctx.cmd}）唤醒")

        return StepResult()
