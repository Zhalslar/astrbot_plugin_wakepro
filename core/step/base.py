from abc import ABC, abstractmethod

from ..config import PluginConfig
from ..model import StepName, StepResult, WakeContext


class BaseStep(ABC):
    """
    所有步骤的基类。
    子类必须实现 handle()
    """

    #: 步骤名（必须覆盖）
    name: StepName

    def __init__(self, config: PluginConfig):
        self.plugin_config = config

    @abstractmethod
    async def handle(self, ctx: WakeContext) -> StepResult:
        """
        处理单次步骤的核心逻辑。
        参数
        ----
        ctx : WakeContext
            上游传递的上下文对象，只读，不应在此方法内直接替换。
        返回
        ----
        StepResult
            用于指示当前步骤的处理结果和后续调度行为的枚举/数据结构。
            典型约定包括：
            - wake: True 表示唤醒, False 表示阻塞, None 表示跳过；
            - abort: 中止当前流水线，不再调度后续步骤；
            - prolong: 需要延长/挂起本步骤（例如等待外部事件或定时任务），
              调度器应在约定的时间或条件满足后再次唤醒当前步骤。
            如需向下游传递数据，请通过 ctx 的字段或在 StepResult 中约定的字段返回，
            并在具体子类或实现类的文档中说明返回值与数据约定。
        """
        ...  # 子类必须覆盖此处

    async def initialize(self) -> None: ...
    async def terminate(self) -> None: ...
