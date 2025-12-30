import asyncio
from collections import OrderedDict, deque
from dataclasses import dataclass
from enum import Enum
from typing import TypeVar

from pydantic import BaseModel, ConfigDict, Field

from astrbot.core.message.components import BaseMessageComponent
from astrbot.core.platform.astr_message_event import AstrMessageEvent

K = TypeVar("K")
V = TypeVar("V")


class FixedDict(OrderedDict[K, V]):
    """定长字典"""

    def __init__(self, maxlen: int):
        super().__init__()
        self.maxlen = maxlen

    def __setitem__(self, key: K, value: V):
        if key in self:
            del self[key]
        super().__setitem__(key, value)
        if len(self) > self.maxlen:
            self.popitem(last=False)


class WakeReason(str, Enum):
    """
    唤醒原因
    """

    PREFIX = "prefix"
    AT = "at"
    REPLY = "reply"
    MENTION = "mention"
    PROLONG = "prolong"
    SIMILAR = "similar"
    ASK = "ask"
    BORED = "bored"
    INTEREST = "interest"
    PROB = "prob"

    @property
    def label(self) -> str:
        return {
            WakeReason.PREFIX: "前缀唤醒",
            WakeReason.AT: "艾特唤醒",
            WakeReason.REPLY: "回复唤醒",
            WakeReason.MENTION: "提及唤醒",
            WakeReason.PROLONG: "延续唤醒",
            WakeReason.SIMILAR: "话题相关唤醒",
            WakeReason.ASK: "疑问唤醒",
            WakeReason.BORED: "无聊唤醒",
            WakeReason.INTEREST: "兴趣唤醒",
            WakeReason.PROB: "概率唤醒",
        }[self]


class BlockReason(str, Enum):
    """
    阻塞原因
    """
    SELF="self"
    WHITE_GROUP = "white_group"
    BLACK_GROUP = "black_group"
    BLACK_USER = "black_user"
    WAKE_CD = "wake_cd"
    FORBIDDEN = "forbidden"
    BUILTIN = "builtin"
    SHUTUP = "shutup"
    INSULT = "insult"
    AI = "ai"
    SILENCE = "silence"
    REREAD = "reread"
    PREFIX_CMD = "prefix_cmd"
    PREFIX_LLM = "prefix_llm"

    @property
    def label(self) -> str:
        return {
            BlockReason.SELF: "自唤醒",
            BlockReason.WHITE_GROUP: "非白名单群",
            BlockReason.BLACK_GROUP: "黑名单群",
            BlockReason.BLACK_USER: "黑名单用户",
            BlockReason.WAKE_CD: "唤醒冷却中",
            BlockReason.FORBIDDEN: "包含违禁词",
            BlockReason.BUILTIN: "内置指令拦截",
            BlockReason.SHUTUP: "群聊闭嘴中",
            BlockReason.INSULT: "辱骂触发沉默",
            BlockReason.AI: "疑似 AI 行为",
            BlockReason.SILENCE: "用户沉默中",
            BlockReason.REREAD: "复读消息",
            BlockReason.PREFIX_CMD: "前缀指令拦截",
            BlockReason.PREFIX_LLM: "前缀 LLM 拦截",
        }[self]


class MemberState(BaseModel):
    """
    成员状态
    """

    uid: str
    silence_until: float = 0.0
    last_wake: float = 0.0
    last_wake_reason: WakeReason | None = None
    last_reply: float = 0.0
    lock: asyncio.Lock = Field(default_factory=asyncio.Lock)
    model_config = ConfigDict(arbitrary_types_allowed=True)


class GroupState(BaseModel):
    """
    群组状态
    """

    gid: str
    members: FixedDict[str, MemberState] = Field(
        default_factory=lambda: FixedDict(maxlen=15)
    )
    shutup_until: float = 0.0
    bot_msgs: deque = Field(default_factory=lambda: deque(maxlen=5))
    model_config = ConfigDict(arbitrary_types_allowed=True)


class StateManager:
    """内存状态管理"""

    _groups: dict[str, GroupState] = {}

    @classmethod
    def get_group(cls, gid: str) -> GroupState:
        if gid not in cls._groups:
            cls._groups[gid] = GroupState(gid=gid)
        return cls._groups[gid]


@dataclass
class WakeContext:
    """唤醒上下文"""

    event: AstrMessageEvent
    chain: list[BaseMessageComponent]
    plain: str
    cmd: str | None
    is_admin: bool
    gid: str
    uid: str
    bid: str
    group: GroupState
    member: MemberState
    now: float
