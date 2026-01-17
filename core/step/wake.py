import random

from astrbot.core.message.components import At, Reply

from ..config import PluginConfig
from ..interest import Interest
from ..model import StepName, StepResult, WakeContext
from ..sentiment import sentiment
from ..similarity import Similarity
from .base import BaseStep


class WakeStep(BaseStep):
    name = StepName.WAKE

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.cfg = config.wake
        self.interest = Interest(self.cfg._interest_words)
        self.similarity = Similarity()

    async def handle(self, ctx: WakeContext) -> StepResult:
        # 前置条件：已沉默，禁止一切唤醒
        if ctx.group and ctx.group.shutup_until > ctx.now:
            return StepResult(wake=False, abort=True, msg="已沉默该群聊，禁止唤醒")
        if ctx.member and ctx.member.silence_until > ctx.now:
            return StepResult(wake=False, abort=True, msg="已沉默该用户，禁止唤醒")

        for seg in ctx.chain:
            # 艾特唤醒
            if isinstance(seg, At) and str(seg.qq) == ctx.bid:
                return StepResult(wake=True, msg="艾特唤醒", prolong=True)
            # 引用唤醒
            if isinstance(seg, Reply) and str(seg.sender_id) == ctx.bid:
                return StepResult(wake=True, msg="引用唤醒", prolong=True)
        # 提及唤醒
        if len(self.cfg.names) > 0 and ctx.plain:
            for name in self.cfg.names:
                if name in ctx.plain:
                    return StepResult(wake=True, msg="提及唤醒", prolong=True)
        # 唤醒延长
        if (
            self.cfg.prolong > 0
            and ctx.member
            and ctx.member.can_prolong
            and ctx.now - ctx.member.last_reply <= self.cfg.prolong
        ):
            return StepResult(wake=True, msg="唤醒延长", prolong=True)
        # 相关性唤醒
        if self.cfg.similar < 1 and ctx.group and ctx.group.bot_msgs and ctx.plain:
            sim = self.similarity.similarity(
                ctx.gid, ctx.plain, list(ctx.group.bot_msgs)
            )
            if sim > self.cfg.similar:
                return StepResult(wake=True, msg="相关性唤醒")
        # 答疑唤醒
        if self.cfg.ask < 1 and ctx.plain and sentiment.ask(ctx.plain) > self.cfg.ask:
            return StepResult(wake=True, msg="答疑唤醒")
        # 无聊唤醒
        if (
            self.cfg.bored < 1
            and ctx.plain
            and sentiment.bored(ctx.plain) > self.cfg.bored
        ):
            return StepResult(wake=True, msg="无聊唤醒")
        # 兴趣唤醒
        if (
            self.cfg.interest < 1
            and ctx.plain
            and self.interest.calc_interest(ctx.plain) > self.cfg.interest
        ):
            return StepResult(wake=True, msg="兴趣唤醒")
        # 概率唤醒
        if self.cfg.prob > 0 and random.random() < self.cfg.prob:
            return StepResult(wake=True, msg="概率唤醒")
        return StepResult()
