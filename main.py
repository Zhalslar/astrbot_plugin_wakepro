import random
import re
import time
from collections.abc import Callable
from enum import Enum
from typing import Any, TypeAlias

from astrbot.api import logger
from astrbot.api.event import filter
from astrbot.api.star import Context, Star
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.message.components import At, Plain, Reply
from astrbot.core.platform.astr_message_event import AstrMessageEvent

from .core.interest import Interest
from .core.model import (
    BlockReason,
    GroupState,
    MemberState,
    StateManager,
    WakeContext,
    WakeReason,
)
from .core.sentiment import Sentiment
from .core.similarity import Similarity
from .core.utils import BUILT_CMDS, get_all_commands

# ============================================================
# Pipeline Core
# ============================================================


class PhaseStatus(Enum):
    PASS = "pass"
    BLOCK = "block"
    WAKE = "wake"
    SILENCE = "silence"


class StepResult:
    """流水线阶段结果"""

    def __init__(self, status: PhaseStatus, reason: Any = None):
        self.status = status  # 阶段状态
        self.reason = reason  # 阻塞/唤醒原因


StepHandler: TypeAlias = Callable[[WakeContext], StepResult]


class Step:
    """单个流水线步骤"""

    def __init__(self, name: str, handler: StepHandler):
        self.name = name
        self.handler = handler


class Pipeline:
    """顺序执行流水线"""

    def __init__(self, steps: list[Step], admin_steps: list[str]):
        self.steps = steps
        self.admin_steps = admin_steps

    def admin_skip(self, step_name: str, is_admin: bool) -> bool:
        if not self.admin_steps:
            return False
        return is_admin and step_name in self.admin_steps

    def run(self, ctx: WakeContext):
        for step in self.steps:
            if self.admin_skip(step.name, ctx.is_admin):
                continue
            ret = step.handler(ctx)
            reason = getattr(ret.reason, "label", ret.reason)
            if ret.status == PhaseStatus.BLOCK:
                ctx.event.stop_event()
                logger.debug(f"{ctx.uid} 阻塞: {reason}")
                break
            elif ret.status == PhaseStatus.WAKE:
                ctx.member.last_wake = ctx.now
                ctx.member.last_wake_reason = ret.reason
                ctx.event.is_at_or_wake_command = True
                logger.debug(f"{ctx.uid} 唤醒: {reason}")
                break
            elif ret.status == PhaseStatus.SILENCE:
                logger.debug(f"{ctx.uid} 沉默: {reason}")
                break


# ============================================================
# WakePro Plugin (可配置化流水线)
# ============================================================


class WakePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.conf = config
        self.sent = Sentiment()
        self.sim = Similarity()
        self.commands = get_all_commands()
        self.wake_prefix: list[str] = self.context.get_config().get("wake_prefix", [])
        interest_words = [w.split() for w in self.conf["wake"]["interest_words_str"]]
        self.interest = Interest(interest_words)

        self._enabled_steps: list[str] = [
            name.split("(", 1)[0].strip() for name in config["pipeline"]["steps"]
        ]
        self._admin_steps: list[str] = [
            name.split("(", 1)[0].strip() for name in config["pipeline"]["admin_steps"]
        ]
        self.pipeline = self._build_pipeline()

    # ============================================================
    # Pipeline Builder
    # ============================================================
    def _register_steps(self) -> dict[str, Step]:
        return {
            "list": Step("list", self._check_list),
            "block": Step("block", self._check_block),
            "cmd": Step("cmd", self._check_cmd),
            "wake": Step("wake", self._check_wake),
            "silence": Step("silence", self._check_silence),
        }

    def _build_pipeline(self) -> Pipeline:
        step_map = self._register_steps()
        steps: list[Step] = []

        if self.conf["pipeline"]["lock_order"]:
            # 锁定顺序：按注册顺序，但只执行启用的
            for name, step in step_map.items():
                if name in self._enabled_steps:
                    steps.append(step)
        else:
            # 自定义顺序
            for name in self._enabled_steps:
                step = step_map.get(name)
                if not step:
                    raise ValueError(f"Unknown pipeline step: {name}")
                steps.append(step)

        return Pipeline(steps, self._admin_steps)

    # ============================================================
    # Steps
    # ============================================================

    def _check_list(self, ctx: WakeContext) -> StepResult:
        """基础过滤"""
        lconf = self.conf["list"]
        # 过滤自己
        if ctx.uid == ctx.bid:
            return StepResult(PhaseStatus.BLOCK, BlockReason.SELF)
        # 过滤群聊白名单
        if len(lconf["white_groups"]) > 0 and ctx.gid not in lconf["white_groups"]:
            return StepResult(PhaseStatus.BLOCK, BlockReason.WHITE_GROUP)
        # 过滤群聊黑名单
        if ctx.gid in lconf["black_groups"]:
            return StepResult(PhaseStatus.BLOCK, BlockReason.BLACK_GROUP)
        # 过滤用户黑名单
        if ctx.uid in lconf["black_users"]:
            return StepResult(PhaseStatus.BLOCK, BlockReason.BLACK_USER)
        return StepResult(PhaseStatus.PASS)

    def _check_block(self, ctx: WakeContext) -> StepResult:
        """block 规则判断"""
        bconf = self.conf["block"]
        # 违禁词阻塞
        if bconf["keywords"]:
            for w in bconf["keywords"]:
                if w in ctx.plain:
                    return StepResult(PhaseStatus.BLOCK, BlockReason.FORBIDDEN)
        # 复读阻塞
        if bconf["reread"]:
            cleaned = re.sub(r"[^\w\u4e00-\u9fff]", "", ctx.plain).lower()
            for msg in ctx.group.bot_msgs:
                m = re.sub(r"[^\w\u4e00-\u9fff]", "", msg).lower()
                if cleaned == m:
                    return StepResult(PhaseStatus.BLOCK, BlockReason.REREAD)
        # 唤醒CD阻塞
        if bconf["wake_cd"] > 0 and ctx.now - ctx.member.last_wake < bconf["wake_cd"]:
            return StepResult(PhaseStatus.BLOCK, BlockReason.WAKE_CD)
        # 闭嘴机制阻塞
        if ctx.group.shutup_until > ctx.now:
            return StepResult(PhaseStatus.BLOCK, BlockReason.SHUTUP)
        # 沉默机制阻塞
        if ctx.member.silence_until > ctx.now:
            return StepResult(PhaseStatus.BLOCK, BlockReason.SILENCE)
        return StepResult(PhaseStatus.PASS)

    def _check_cmd(self, ctx: WakeContext) -> StepResult:
        """检查指令逻辑"""
        cconf = self.conf["cmd"]
        # 屏蔽内置指令
        if cconf["block_builtin"] and ctx.cmd in BUILT_CMDS:
            return StepResult(PhaseStatus.BLOCK, BlockReason.BUILTIN)

        seg = ctx.chain[0] if ctx.chain and isinstance(ctx.chain[0], Plain) else None
        if not seg or not any(seg.text.startswith(p) for p in self.wake_prefix):
            return StepResult(PhaseStatus.PASS)
        # 屏蔽前缀触发指令
        if ctx.cmd and cconf["block_prefix_cmd"]:
            return StepResult(PhaseStatus.BLOCK, BlockReason.PREFIX_CMD)
        # 屏蔽前缀触发LLM
        if not ctx.cmd and cconf["block_prefix_llm"]:
            return StepResult(PhaseStatus.BLOCK, BlockReason.PREFIX_LLM)
        # 前缀唤醒
        return StepResult(PhaseStatus.WAKE, WakeReason.PREFIX)

    def _check_wake(self, ctx: WakeContext) -> StepResult:
        """唤醒规则判断"""
        wconf = self.conf["wake"]
        for seg in ctx.chain:
            # 艾特唤醒
            if isinstance(seg, At) and str(seg.qq) == ctx.bid:
                return StepResult(PhaseStatus.WAKE, WakeReason.AT)
            # 引用唤醒
            if isinstance(seg, Reply) and str(seg.sender_id) == ctx.bid:
                return StepResult(PhaseStatus.WAKE, WakeReason.REPLY)
        # 提及唤醒
        if len(wconf["names"]) > 0:
            for name in wconf["names"]:
                if name in ctx.plain:
                    return StepResult(PhaseStatus.WAKE, WakeReason.MENTION)
        # 唤醒延长
        if (
            wconf["prolong"] > 0
            and ctx.member.last_wake_reason
            in {WakeReason.AT, WakeReason.REPLY, WakeReason.MENTION}
            and ctx.now - ctx.member.last_reply <= wconf["prolong"]
        ):
            return StepResult(PhaseStatus.WAKE, WakeReason.PROLONG)
        # 相关性唤醒
        if wconf["similar"] < 1 and ctx.group.bot_msgs:
            sim = self.sim.similarity(ctx.gid, ctx.plain, list(ctx.group.bot_msgs))
            if sim > wconf["similar"]:
                return StepResult(PhaseStatus.WAKE, WakeReason.SIMILAR)
        # 答疑唤醒
        if wconf["ask"] < 1 and self.sent.ask(ctx.plain) > wconf["ask"]:
            return StepResult(PhaseStatus.WAKE, WakeReason.ASK)
        # 无聊唤醒
        if wconf["bored"] < 1 and self.sent.bored(ctx.plain) > wconf["bored"]:
            return StepResult(PhaseStatus.WAKE, WakeReason.BORED)
        # 兴趣唤醒
        if (
            wconf["interest"] < 1
            and self.interest.calc_interest(ctx.plain) > wconf["interest"]
        ):
            return StepResult(PhaseStatus.WAKE, WakeReason.INTEREST)
        # 概率唤醒
        if wconf["prob"] > 0 and random.random() < wconf["prob"]:
            return StepResult(PhaseStatus.WAKE, WakeReason.PROB)
        return StepResult(PhaseStatus.PASS)

    def _check_silence(self, ctx: WakeContext) -> StepResult:
        """沉默逻辑"""
        # 闭嘴沉默
        sconf = self.conf["silence"]
        if sconf["shutup"] < 1:
            th = self.sent.shut(ctx.plain)
            if th > sconf["shutup"]:
                ctx.group.shutup_until = ctx.now + th * sconf["multiple"]
                return StepResult(PhaseStatus.SILENCE, BlockReason.SHUTUP)
        # 辱骂沉默
        if sconf["insult"] < 1:
            th = self.sent.insult(ctx.plain)
            if th > sconf["insult"]:
                ctx.member.silence_until = ctx.now + th * sconf["multiple"]
                return StepResult(PhaseStatus.SILENCE, BlockReason.INSULT)
        # 人机沉默
        if sconf["ai"] < 1:
            th = self.sent.is_ai(ctx.plain)
            if th > sconf["ai"]:
                ctx.member.silence_until = ctx.now + th * sconf["multiple"]
                return StepResult(PhaseStatus.SILENCE, BlockReason.AI)
        return StepResult(PhaseStatus.PASS)

    # ============================================================
    # Event Hooks
    # ============================================================

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE, priority=99)
    async def on_group_msg(self, event: AstrMessageEvent):
        """收到群消息后"""
        chain = event.get_messages()
        if not chain:
            return
        plains = [seg.text for seg in chain if isinstance(seg, Plain)]
        plain = " ".join(plains).strip()
        if not plain:
            return
        first_arg = event.message_str.split(" ", 1)[0]
        cmd = (
            first_arg if first_arg in self.commands or first_arg in BUILT_CMDS else None
        )
        gid = event.get_group_id()
        uid = event.get_sender_id()
        bid = event.get_self_id()
        group: GroupState = StateManager.get_group(gid)
        if uid not in group.members:
            group.members[uid] = MemberState(uid=uid)
        ctx = WakeContext(
            event=event,
            chain=chain,
            plain=plain,
            cmd=cmd,
            is_admin=event.is_admin(),
            gid=gid,
            uid=uid,
            bid=bid,
            group=group,
            member=group.members[uid],
            now=time.time(),
        )
        self.pipeline.run(ctx)

    @filter.on_decorating_result(priority=20)
    async def on_decorating_result(self, event: AstrMessageEvent):
        """消息发送前"""
        gid: str = event.get_group_id()
        uid: str = event.get_sender_id()
        result = event.get_result()
        if not gid or not uid or not result:
            return
        g: GroupState = StateManager.get_group(gid)
        g.bot_msgs.append(result.get_plain_text())
        member = g.members.get(uid)
        if not member:
            return
        member.last_reply = time.time()
