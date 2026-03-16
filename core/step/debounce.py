from __future__ import annotations

from astrbot.core.message.components import At, BaseMessageComponent, Plain, Reply
from astrbot.core.pipeline.process_stage import follow_up as process_follow_up

from ..config import PluginConfig
from ..model import PendingWakeRequest, StateManager, StepName, StepResult, WakeContext
from .base import BaseStep


class DebounceStep(BaseStep):
    name = StepName.DEBOUNCE

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.cfg = config.debounce

    async def handle(self, ctx: WakeContext) -> StepResult:
        if self.cfg.listen_seconds <= 0:
            return StepResult()
        if not ctx.uid:
            return StepResult()

        key = StateManager.get_pending_key(ctx.umo, ctx.uid)
        pending = await StateManager.claim_pending_request(
            key,
            now=ctx.now,
            window=self.cfg.listen_seconds,
            current_event=ctx.event,
        )

        if not pending:
            return StepResult()

        self._stop_previous_event(pending.event)
        ctx.debounce_follow_up = True
        self._detach_active_runner(ctx.umo)
        ctx.chain = self._merge_chain(pending.chain, ctx.chain)
        ctx.plain = self._merge_plain(pending.plain, ctx.plain)
        self._apply_merged_message(ctx)

        merged_count = pending.merged_count + 1
        ctx.debounce_merged_count = merged_count
        if self._should_continue_listening(merged_count):
            await StateManager.register_pending_request(
                key,
                PendingWakeRequest(
                    event=ctx.event,
                    chain=list(ctx.chain),
                    plain=ctx.plain,
                    created_at=ctx.now,
                    merged_count=merged_count,
                ),
                window=self.cfg.listen_seconds,
            )
            msg = f"已合并同用户 {merged_count} 条连续消息"
        else:
            msg = f"已合并同用户 {merged_count} 条连续消息，达到上限后立即发起请求"
        return StepResult(wake=True, msg=msg)

    async def activate_window(self, ctx: WakeContext) -> None:
        if self.cfg.listen_seconds <= 0 or not ctx.uid:
            return
        if not ctx.debounce_follow_up:
            message_type = self._detect_message_type(ctx)
            if message_type not in self.cfg.message_types:
                return
        if not self._should_continue_listening(ctx.debounce_merged_count):
            return

        key = StateManager.get_pending_key(ctx.umo, ctx.uid)
        await StateManager.register_pending_request(
            key,
            PendingWakeRequest(
                event=ctx.event,
                chain=list(ctx.chain),
                plain=ctx.plain,
                created_at=ctx.now,
                merged_count=ctx.debounce_merged_count,
            ),
            window=self.cfg.listen_seconds,
        )

    @staticmethod
    def _detect_message_type(ctx: WakeContext) -> str:
        if ctx.cmd:
            return "command"
        if any(isinstance(seg, At) and str(seg.qq) == ctx.bid for seg in ctx.chain):
            return "at"
        if any(
            isinstance(seg, Reply) and str(seg.sender_id) == ctx.bid
            for seg in ctx.chain
        ):
            return "reply"
        return "normal"

    @staticmethod
    def _stop_previous_event(event) -> None:
        event.set_extra("agent_stop_requested", True)
        event.stop_event()

    @staticmethod
    def _detach_active_runner(umo: str) -> None:
        active_runners = getattr(process_follow_up, "_ACTIVE_AGENT_RUNNERS", None)
        if isinstance(active_runners, dict):
            active_runners.pop(umo, None)

    def _should_continue_listening(self, merged_count: int) -> bool:
        max_merge_count = int(self.cfg.max_merge_count)
        return max_merge_count <= 0 or merged_count < max_merge_count

    @staticmethod
    def _merge_plain(previous_plain: str, current_plain: str) -> str:
        parts = [
            part.strip() for part in (previous_plain, current_plain) if part.strip()
        ]
        return "\n".join(parts)

    def _merge_chain(
        self,
        previous_chain: list[BaseMessageComponent],
        current_chain: list[BaseMessageComponent],
    ) -> list[BaseMessageComponent]:
        merged = list(previous_chain)
        if merged and current_chain:
            merged.append(Plain("\n", convert=False))
        merged.extend(current_chain)
        return merged

    def _apply_merged_message(self, ctx: WakeContext) -> None:
        ctx.event.message_obj.message = list(ctx.chain)
        ctx.event.message_obj.message_str = ctx.plain
        ctx.event.message_str = ctx.plain
