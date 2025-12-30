
from astrbot.core.star.filter.command import CommandFilter
from astrbot.core.star.filter.command_group import CommandGroupFilter
from astrbot.core.star.star_handler import star_handlers_registry


def get_all_commands() -> list[str]:
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
