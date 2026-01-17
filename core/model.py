import asyncio
from collections import OrderedDict, deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

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


class MemberState(BaseModel):
    """
    成员状态
    """

    uid: str
    """成员ID"""
    silence_until: float = 0.0
    """沉默到期时间"""
    last_speak: float = 0.0
    """上次发言时间"""
    last_wake: float = 0.0
    """上次唤醒时间"""
    can_prolong: bool = False
    """是否可以延长唤醒"""
    last_reply: float = 0.0
    """上次回复时间"""
    lock: asyncio.Lock = Field(default_factory=asyncio.Lock)
    """成员锁"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    """模型配置"""

class GroupState(BaseModel):
    """
    群组状态
    """

    gid: str
    """群组 ID"""
    members: FixedDict[str, MemberState] = Field(
        default_factory=lambda: FixedDict(maxlen=15)
    )
    """群组成员状态"""
    shutup_until: float = 0.0
    """闭嘴到期时间"""
    bot_msgs: deque = Field(default_factory=lambda: deque(maxlen=5))
    """机器人消息缓存队列"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    """模型配置"""


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
    """事件"""
    chain: list[BaseMessageComponent]
    """消息链"""
    plain: str
    """纯文本消息"""
    cmd: str | None
    """命令"""
    is_admin: bool
    """是否为管理员事件"""
    gid: str
    """群组 ID"""
    uid: str
    """用户 ID"""
    bid: str
    """Bot ID"""
    group: GroupState | None
    """群组状态"""
    member: MemberState | None
    """成员状态"""
    now: float
    """当前时间戳"""


class StepName(str, Enum):
    GATE = "gate"
    BLOCK = "block"
    COMMAND = "command"
    SILENCE = "silence"
    WAKE = "wake"


@dataclass(slots=True)
class StepResult:
    wake: bool | None = None
    """是否唤醒, True 表示唤醒, False 表示阻塞, None 表示跳过"""
    abort: bool = False
    """是否需要中断处理"""
    msg: str | None = None
    """附加消息"""
    data: Any | None = None
    """携带的上下文信息"""
    prolong: bool = False
    """是否可以延长唤醒"""
