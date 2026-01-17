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


class GateStep(BaseStep):
    name = StepName.GATE

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.cfg = config.gate

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
        # 过滤自己
        if self.cfg.block_self and ctx.uid == ctx.bid:
            return StepResult(wake=False, abort=True, msg="过滤自己的消息")
        # 过滤QQ机器人
        if (
            self.cfg.block_qqbot
            and isinstance(ctx.event, AiocqhttpMessageEvent)
            and self._is_qqbot(ctx.uid)
        ):
            return StepResult(wake=False, abort=True, msg="过滤QQ机器人")
        # 过滤用户白名单
        if len(self.cfg.white_users) > 0 and ctx.uid not in self.cfg.white_users:
            return StepResult(wake=False, abort=True, msg="过滤用户白名单")
        # 过滤群聊白名单
        if (
            len(self.cfg.white_groups) > 0
            and ctx.gid
            and ctx.gid not in self.cfg.white_groups
        ):
            return StepResult(wake=False, abort=True, msg="过滤群聊白名单")
        # 过滤用户黑名单
        if len(self.cfg.black_users) > 0 and ctx.uid in self.cfg.black_users:
            return StepResult(wake=False, abort=True, msg="过滤用户黑名单")
        # 过滤群聊黑名单
        if (
            len(self.cfg.black_groups) > 0
            and ctx.gid
            and ctx.gid in self.cfg.black_groups
        ):
            return StepResult(wake=False, abort=True, msg="过滤群聊黑名单")
        return StepResult()
