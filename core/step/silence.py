
from ..config import PluginConfig
from ..model import StepName, StepResult, WakeContext
from ..sentiment import sentiment
from .base import BaseStep


class SilenceStep(BaseStep):
    name = StepName.SILENCE

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.cfg = config.silence

    async def handle(self, ctx: WakeContext) -> StepResult:
        # 前置条件：bot 已被唤醒
        if not ctx.event.is_at_or_wake_command:
            return StepResult()

        # 闭嘴沉默
        if self.cfg.shutup < 1 and ctx.plain and ctx.group:
            th = sentiment.shut(ctx.plain)
            if th > self.cfg.shutup:
                seconds = self.cfg.multiple * th
                ctx.group.shutup_until = ctx.now + seconds
                return StepResult(abort=True, msg=f"触发群聊级闭嘴({seconds}秒)")
        # 辱骂沉默
        if self.cfg.insult < 1 and ctx.plain and ctx.member:
            th = sentiment.insult(ctx.plain)
            if th >self.cfg.insult:
                seconds = th * self.cfg.multiple
                ctx.member.silence_until = ctx.now + seconds
                return StepResult(abort=True, msg=f"触发用户级闭嘴({seconds}秒)")
        # 人机沉默
        if self.cfg.ai < 1 and ctx.plain and ctx.member:
            th = sentiment.is_ai(ctx.plain)
            if th > self.cfg.ai:
                seconds = th * self.cfg.multiple
                ctx.member.silence_until = ctx.now + seconds
                return StepResult(abort=True, msg=f"触发人机级闭嘴({seconds}秒)")
        return StepResult()


