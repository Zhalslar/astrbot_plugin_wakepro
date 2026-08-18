from astrbot.core.message.components import At, Reply

from ..config import PluginConfig
from ..model import StepName, StepResult, WakeContext
from .base import BaseStep


class MentionStep(BaseStep):
    name = StepName.MENTION

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.cfg = config.mention

    async def handle(self, ctx: WakeContext) -> StepResult:
        if ctx.debounce_follow_up:
            return StepResult(msg="消息防抖窗口内，沿用已唤醒状态")

        if ctx.cmd:
            return StepResult(msg="指令消息，跳过提及唤醒")

        has_self_reference = False
        has_other_reply = False
        has_other_at = False
        for seg in ctx.chain:
            if isinstance(seg, At):
                if str(seg.qq) == ctx.bid:
                    has_self_reference = True
                elif str(seg.qq) != "all":
                    has_other_at = True
            elif isinstance(seg, Reply):
                if str(seg.sender_id) == ctx.bid:
                    has_self_reference = True
                else:
                    has_other_reply = True

        if has_self_reference:
            for seg in ctx.chain:
                if isinstance(seg, At) and str(seg.qq) == ctx.bid:
                    return StepResult(wake=True, msg="艾特唤醒", prolong=True)
                if (
                    not self.cfg.disable_reply_wake
                    and isinstance(seg, Reply)
                    and str(seg.sender_id) == ctx.bid
                ):
                    return StepResult(wake=True, msg="引用唤醒", prolong=True)

        if (
            self.cfg.disable_reply_other_wake
            and has_other_reply
            and not has_self_reference
        ):
            return StepResult(
                wake=False, abort=True, msg="引用了别人的消息，已跳过唤醒"
            )
        if self.cfg.disable_at_other_wake and has_other_at and not has_self_reference:
            return StepResult(
                wake=False, abort=True, msg="艾特了别人，已跳过唤醒"
            )

        if ctx.plain:
            for name in self.cfg.names:
                if name and name in ctx.plain:
                    return StepResult(wake=True, msg="通用唤醒词唤醒", prolong=True)

            if ctx.is_admin:
                for name in self.cfg.admin_names:
                    if name and name in ctx.plain:
                        return StepResult(wake=True, msg="专属唤醒词唤醒", prolong=True)

        return StepResult()
