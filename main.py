import time

from astrbot.api.event import filter
from astrbot.api.star import Context, Star
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.message.components import Plain
from astrbot.core.platform.astr_message_event import AstrMessageEvent
from astrbot.core.star.filter.command import CommandFilter
from astrbot.core.star.filter.command_group import CommandGroupFilter
from astrbot.core.star.star_handler import star_handlers_registry

from .core.config import PluginConfig
from .core.model import (
    GroupState,
    MemberState,
    StateManager,
    WakeContext,
)
from .core.pipeline import Pipeline


class WakePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.cfg = PluginConfig(config, context=context)
        self.commands = self._get_all_commands()
        self.pipeline = Pipeline(self.cfg)

    @staticmethod
    def _get_all_commands() -> list[str]:
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
        return commands

    @filter.event_message_type(filter.EventMessageType.ALL, priority=99999)
    async def on_group_msg(self, event: AstrMessageEvent):
        """收到消息后"""
        chain = event.get_messages()
        plains = [seg.text for seg in chain if isinstance(seg, Plain)]
        plain = " ".join(plains).strip()
        first_arg = event.message_str.split(" ", 1)[0]
        cmd = first_arg if first_arg in self.commands else None
        gid = event.get_group_id()
        uid = event.get_sender_id()
        bid = event.get_self_id()
        group = StateManager.get_group(gid) if gid else None
        if group and uid not in group.members:
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
            member=group.members[uid] if group else None,
            now=time.time(),
        )
        await self.pipeline.run(ctx)

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
