import logging

import anyio
from anyio.streams.memory import MemoryObjectReceiveStream

from ..progress import StatusMap
from .models import RunStatus
from .widgets._run_status_widget import RunStatusWidget


async def monitor_run_progress(
    progress_receive_stream: MemoryObjectReceiveStream[StatusMap],
    run_status_widget: RunStatusWidget,
) -> None:
    status_map: StatusMap = {}
    progress_tg = anyio.create_task_group()

    async def _receive_status() -> None:
        nonlocal status_map
        async with progress_receive_stream:
            async for status_map in progress_receive_stream:
                run_status_map = RunStatus.from_progress_status_map(status_map)
                run_status_widget.setStatusMap(run_status_map)
        progress_tg.cancel_scope.cancel()

    async def _update_status() -> None:
        while True:
            run_status_map = RunStatus.from_progress_status_map(status_map)
            run_status_widget.setStatusMap(run_status_map)
            await anyio.sleep(1)

    async with progress_tg:
        progress_tg.start_soon(_receive_status)
        progress_tg.start_soon(_update_status)
