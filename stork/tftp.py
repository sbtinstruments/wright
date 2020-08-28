import asyncio
import logging

import tftpy

_LOGGER = logging.getLogger(__name__)


class AsyncTFTPServer(tftpy.TftpServer):
    def __init__(self, host, port, root_dir):
        super().__init__(root_dir)
        self._serve_task = None
        self._host = host
        self._port = port

    async def __aenter__(self):
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(None, self.listen, self._host, self._port)
        self._serve_task = asyncio.ensure_future(future)
        return self

    async def __aexit__(self, *args):
        _LOGGER.info("Stopping TFTP server...")
        self.stop(now=True)
        await self._serve_task
