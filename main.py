import asyncio
import random
import re
import time
from collections import deque

from pydantic import BaseModel, ConfigDict, Field

from astrbot.api import logger
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.message.components import At, Plain, Reply
from astrbot.core.platform.astr_message_event import AstrMessageEvent
from astrbot.core.star.filter.command import CommandFilter
from astrbot.core.star.filter.command_group import CommandGroupFilter
from astrbot.core.star.star_handler import star_handlers_registry

from .interest import Interest
from .sentiment import Sentiment
from .similarity import Similarity

# 内置指令文本
BUILT_CMDS = [
    "llm",
    "t2i",
    "tts",
    "sid",
    "op",
    "wl",
    "dashboard_update",
    "alter_cmd",
    "provider",
    "model",
    "plugin",
    "plugin ls",
    "new",
    "switch",
    "rename",
    "del",
    "reset",
    "history",
    "persona",
    "tool ls",
    "key",
    "websearch",
]


class MemberState(BaseModel):
    uid: str
    silence_until: float = 0.0  # 沉默到何时
    last_wake: float = 0.0  # 最后唤醒bot的时间
    last_wake_reason: str = "" # 最后唤醒bot的原因
    last_reply: float = 0.0 # 最后回复的时间
    pend: deque = Field(default_factory=lambda: deque(maxlen=4))  # 事件缓存
    lock: asyncio.Lock = Field(default_factory=asyncio.Lock)
    model_config = ConfigDict(arbitrary_types_allowed=True)


class GroupState(BaseModel):
    gid: str
    members: dict[str, MemberState] = Field(default_factory=dict)
    shutup_until: float = 0.0  # 闭嘴到何时
    bot_msgs: deque = Field(
        default_factory=lambda: deque(maxlen=5)
    )  # Bot消息缓存，共5条


class StateManager:
    """内存状态管理"""

    _groups: dict[str, GroupState] = {}

    @classmethod
    def get_group(cls, gid: str) -> GroupState:
        if gid not in cls._groups:
            cls._groups[gid] = GroupState(gid=gid)
        return cls._groups[gid]


@register("astrbot_plugin_wakepro", "Zhalslar", "...", "...")
class WakeProPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.conf = config
        self.sent = Sentiment()
        self.sim = Similarity()
        self.commands = self._get_all_commands()
        self.wake_prefix = self.context.get_config().get("wake_prefix")
        interest_words_str: list[str] = self.conf["interest_words_str"]
        interest_words_list: list[list[str]] = [
            words_str.split() for words_str in interest_words_str
        ]
        self.interest = Interest(interest_words_list)

    def _get_all_commands(self) -> list[str]:
        """遍历所有注册的处理器获取所有命令"""
        commands = []
        for handler in star_handlers_registry:
            for fl in handler.event_filters:
                if isinstance(fl, CommandFilter):
                    commands.append(fl.command_name)
                    break
                elif isinstance(fl, CommandGroupFilter):
                    commands.append(fl.group_name)
                    break
        logger.debug(f"插件的指令列表：{commands}")
        return commands

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE, priority=99)
    async def on_group_msg(self, event: AstrMessageEvent):
        """主入口"""
        chain = event.get_messages()
        bid: str = event.get_self_id()
        gid: str = event.get_group_id()
        uid: str = event.get_sender_id()
        msg: str = event.message_str
        g: GroupState = StateManager.get_group(gid)

        # 只处理文本
        if not msg:
            return

        # 群聊黑白名单 / 用户黑名单
        if uid == bid:
            return
        if self.conf["group_whitelist"] and gid not in self.conf["group_whitelist"]:
            logger.debug(f"群组{gid}未在白名单中, 忽略此次唤醒")
            return
        if gid in self.conf["group_blacklist"] and not event.is_admin():
            logger.debug(f"群组{gid}已处于黑名单中, 忽略此次唤醒")
            event.stop_event()
            return
        if uid in self.conf.get("user_blacklist", []):
            logger.debug(f"用户{uid}已处于黑名单中, 忽略此次唤醒")
            event.stop_event()
            return

        # 更新成员状态
        if uid not in g.members:
            g.members[uid] = MemberState(uid=uid)

        member = g.members[uid]
        now = time.time()

        # 记录阻止原因，只有在会触发唤醒时才真正阻止事件传播
        # Record blocking reason, only actually block event propagation if wake would be triggered
        block_reason = None

        # 唤醒CD检查
        if now - member.last_wake < self.conf["wake_cd"]:
            logger.debug(f"{uid} 处于唤醒CD中, 记录阻止原因")
            block_reason = "wake_cd"

        # 唤醒违禁词检查
        if not block_reason and self.conf["wake_forbidden_words"]:
            for word in self.conf["wake_forbidden_words"]:
                if not event.is_admin() and word in event.message_str:
                    logger.debug(f"{uid} 消息中含有唤醒屏蔽词, 记录阻止原因")
                    block_reason = "forbidden_word"
                    break

        # 屏蔽内置指令
        if not block_reason and self.conf["block_builtin"]:
            if not event.is_admin() and event.message_str in BUILT_CMDS:
                logger.debug(f"{uid} 触发内置指令, 记录阻止原因")
                block_reason = "builtin_cmd"

        # 闭嘴检查
        if not block_reason and g.shutup_until > now:
            logger.debug(f"Bot处于闭嘴中, 记录阻止{uid}的原因")
            block_reason = "shutup"

        # 沉默检查（辱骂/人机）
        if not block_reason and not event.is_admin() and member.silence_until > now:
            logger.debug(f"处于沉默中, 记录阻止{uid}的原因")
            block_reason = "silence"

        # 复读屏蔽
        if not block_reason and self.conf["block_reread"]:
            cleaned_msg = re.sub(r"[^\w\u4e00-\u9fff]", "", msg).lower()
            cleaned_bot_msgs = [
                re.sub(r"[^\w\u4e00-\u9fff]", "", bmsg).lower() for bmsg in g.bot_msgs
            ]
            if cleaned_msg in cleaned_bot_msgs:
                logger.debug(
                    f"{uid} 发送了与Bot缓存消息相同的内容（忽略符号和空格），记录阻止原因"
                )
                block_reason = "reread"

        # 判断是否是指令
        cmd = msg.split(" ", 1)[0]
        is_cmd = cmd in self.commands or cmd in BUILT_CMDS

        # 消息缓存与合并
        if not is_cmd:
            event.set_extra("orig_message", event.message_str)
            event.set_extra("timestamp", now)
            async with member.lock:
                if (
                    member.pend
                    and now - member.pend[-1].get_extra("timestamp")  # type: ignore
                    < self.conf["pend_cd"]
                ):
                    msgs: list[str] = [
                        e.get_extra("orig_message") or "" for e in member.pend
                    ]  # type: ignore
                    for e in member.pend:
                        e.stop_event()
                    event.message_str = "。".join(msgs + [event.message_str])
                    logger.debug(
                        f"已合并{len(member.pend)}条缓存消息：{event.message_str}"
                    )

        # 各类唤醒条件
        wake = event.is_at_or_wake_command
        reason = ""

        # 前缀唤醒
        if isinstance(self.wake_prefix, list) and self.wake_prefix:
            full_msg = next((seg.text for seg in chain if isinstance(seg, Plain)), "")
            for prefix in self.wake_prefix:
                if not full_msg.startswith(prefix):
                    continue

                # 屏蔽前缀指令
                if  self.conf["block_prefix_cmd"] and not event.is_admin() and is_cmd:
                    logger.debug(f"{uid} 触发前缀指令, 忽略此次唤醒")
                    event.stop_event()
                    return

                # 屏蔽前缀 LLM（即非指令）
                if self.conf["block_prefix_llm"] and not event.is_admin() and not is_cmd:
                    logger.debug(f"{uid} 触发前缀LLM, 忽略此次唤醒")
                    event.stop_event()
                    return

                # 通过所有过滤，执行唤醒
                wake = True
                reason = "prefix"
                logger.debug(f"{uid} 触发前缀唤醒：{prefix}")
                break

        # At唤醒
        for seg in chain:
            if isinstance(seg, At) and str(seg.qq) == bid:
                wake = True
                reason = "at"
                logger.debug(f"{uid} 触发At唤醒")
                break
            elif isinstance(seg, Reply) and str(seg.sender_id) == bid:
                wake = True
                reason = "reply"
                logger.debug(f"{uid} 触发引用回复唤醒")
                break

        # 提及唤醒
        if not wake and self.conf["mention_wake"]:
            names = [n for n in self.conf["mention_wake"] if n]
            for n in names:
                if n and n in msg:
                    wake = True
                    reason = "mention"
                    logger.debug(f"{uid} 触发提及唤醒：{n}")
                    break

        # 唤醒延长（如果已经处于唤醒状态且在 wake_extend 秒内，每个用户单独延长唤醒时间）
        if (
            not wake
            and self.conf["wake_extend"]
            and member.last_wake_reason in ["at", "reply", "mention"]
            and (now - member.last_reply) <= int(self.conf["wake_extend"] or 0)
        ):
            wake = True
            reason = "prolong"
            logger.debug(
                f"{uid} 唤醒延长, 时间为上次llm回复后的第{now - member.last_reply}秒"
            )

        # 话题相关性唤醒
        if not wake and self.conf["relevant_wake"] and g.bot_msgs:
            simi = self.sim.similarity(
                group_id=gid, user_msg=msg, bot_msgs=list(g.bot_msgs)
            )
            logger.debug(f"话题相关度:{simi}")
            if simi > self.conf["relevant_wake"]:
                wake = True
                reason = "similar"
                logger.debug(f"{uid} 触发话题相关性唤醒, 相关度：{simi}")

        # 答疑唤醒
        if (
            not wake
            and self.conf["ask_wake"]
            and (ask_th := self.sent.ask(msg)) > self.conf["ask_wake"]
        ):
            wake = True
            reason = "ask"
            logger.debug(f"{uid} 触发答疑唤醒, 疑问值：{ask_th}")

        # 无聊唤醒
        if (
            not wake
            and self.conf["bored_wake"]
            and (bored_th := self.sent.bored(msg)) > self.conf["bored_wake"]
        ):
            wake = True
            reason = "bored"
            logger.debug(f"{uid} 触发无聊唤醒, 无聊值：{bored_th}")

        # 兴趣唤醒
        if (
            not wake
            and self.conf["interest_wake"]

        ):
            interest_th = self.interest.calc_interest(msg)
            logger.debug(f"兴趣值：{interest_th}")
            if interest_th > self.conf["interest_wake"]:
                wake = True
                reason = "interest"
                logger.debug(f"{uid} 触发兴趣唤醒, 兴趣值：{interest_th}")

        # 概率唤醒
        if (
            not wake
            and self.conf["prob_wake"]
            and random.random() < self.conf["prob_wake"]
        ):
            wake = True
            reason = "prob"
            logger.debug(f"{uid} 触发概率唤醒")

        # 应用阻止规则（只有在会触发唤醒时才真正阻止事件传播到其他插件）
        # Apply blocking rules (only stop event if it would trigger wake)
        if wake and block_reason:
            logger.debug(f"{uid} 触发了唤醒但因 {block_reason} 被阻止")
            event.stop_event()
            return

        # 触发唤醒
        if wake:
            # 缓存消息
            if cmd not in self.commands:
                member.pend.append(event)
                logger.debug(f"已添加event到缓存：{len(member.pend)}")

            # 触发唤醒
            event.is_at_or_wake_command = True
            # 记录唤醒时间
            member.last_wake = now
            # 记录原因
            member.last_wake_reason = reason


        # 闭嘴机制(对当前群聊闭嘴)
        if self.conf["shutup"]:
            shut_th = self.sent.shut(msg)
            if shut_th > self.conf["shutup"]:
                silence_sec = shut_th * self.conf["silence_multiple"]
                g.shutup_until = now + silence_sec
                reason = f"闭嘴沉默{silence_sec}秒"
                logger.debug(f"[wakepro] 群({gid}){reason}：{msg}")
                event.stop_event()
                return

        # 辱骂沉默机制(对单个用户沉默)
        if self.conf["insult"]:
            insult_th = self.sent.insult(msg)
            if insult_th > self.conf["insult"]:
                silence_sec = insult_th * self.conf["silence_multiple"]
                member.silence_until = now + silence_sec
                reason = "insult"
                logger.info(f"[wakepro] 群({gid})用户({uid}){reason}：{msg}")
                # event.stop_event() 本轮对话不沉默，方便回怼
                return

        # AI沉默机制(对单个用户沉默)
        if self.conf["ai"]:
            ai_th = self.sent.is_ai(msg)
            if ai_th > self.conf["ai"]:
                silence_sec = ai_th * self.conf["silence_multiple"]
                member.silence_until = now + silence_sec
                reason = "silence"
                logger.info(f"[wakepro] 群({gid})用户({uid}){reason}：{msg}")
                event.stop_event()
                return

    @filter.on_decorating_result(priority=20)
    async def on_message(self, event: AstrMessageEvent):
        """发送消息前，缓存bot消息，清空用户消息缓存"""
        gid: str = event.get_group_id()
        uid: str = event.get_sender_id()
        result = event.get_result()
        if not gid or not uid or not result:
            return
        g: GroupState = StateManager.get_group(gid)
        # 缓存bot消息
        g.bot_msgs.append(result.get_plain_text())
        member = g.members.get(uid)
        if not member:
            return
        # 记录回复时间
        member.last_reply = time.time()
        # 清空用户消息缓存
        async with member.lock:
            member.pend.clear()
