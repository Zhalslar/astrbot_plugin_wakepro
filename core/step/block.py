import re

from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)

from ..config import PluginConfig
from ..model import StepName, StepResult, WakeContext
from .base import BaseStep

# 机器人账号区间（闭区间）
BOT_RANGES: list[tuple[int, int]] = [
    (3328144510, 3328144510),
    (2854196301, 2854216399),
    (66600000, 66600000),
    (3889000000, 3889999999),
    (4010000000, 4019999999),
]


class BlockStep(BaseStep):
    name = StepName.BLOCK

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.cfg = config.block

    @staticmethod
    def _is_qqbot(uid: int | str) -> bool:
        """
        判断是否为 qqbot 账号

        :param uid: 用户 ID（支持 str / int）
        :return: 是否为 bot
        """
        try:
            uid = int(uid)
        except (TypeError, ValueError):
            return False

        for start, end in BOT_RANGES:
            if start <= uid <= end:
                return True
        return False

    async def handle(self, ctx: WakeContext) -> StepResult:
        # 白名单检查
        if self.in_whitelist(ctx):
            return StepResult(wake=False, abort=True, msg="白名单会话，跳过阻塞判断")
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
        # 过滤QQ机器人
        if (
            self.cfg.block_qqbot
            and isinstance(ctx.event, AiocqhttpMessageEvent)
            and self._is_qqbot(ctx.uid)
        ):
            return StepResult(wake=False, abort=True, msg="过滤QQ机器人")
        # 复读阻塞
        if self.cfg.reread and ctx.plain and ctx.group:
            cleaned = re.sub(r"[^\w\u4e00-\u9fff]", "", ctx.plain).lower()
            for msg in ctx.group.bot_msgs:
                if not msg:
                    continue
                m = re.sub(r"[^\w\u4e00-\u9fff]", "", msg).lower()
                if cleaned == m:
                    return StepResult(wake=False, abort=True, msg=f"已阻止复读: {msg}")

        # 违禁词阻塞
        if self.cfg.keywords and ctx.plain:
            for w in self.cfg.keywords:
                if w in ctx.plain:
                    return StepResult(wake=False, abort=True, msg=f"包含违禁词: {w}")
        return StepResult()
