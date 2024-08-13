import json
import logging
from pathlib import Path
from typing import Any, TypeVar

import anyio
import asyncssh
from pydantic import TypeAdapter

from wright.device.models._device_data_models import BbpState, PartialBbpStatus

_LOGGER = logging.getLogger()


async def main() -> None:
    host = "bb2305092"
    port = 7910
    username = "root"

    async with asyncssh.connect(
        host,
        port,
        username=username,
    ) as connection:
        while True:
            await run_measure(connection)


def main_sync() -> None:
    _LOGGER.setLevel(logging.DEBUG)
    _LOGGER.addHandler(logging.StreamHandler())
    anyio.run(main)


async def run_measure(connection: asyncssh.SSHClientConnection) -> None:
    """Set the electronics reference data (JSON file).

    Returns the reference data (parsed contents of the JSON file).
    """
    await _start_bbp(connection, program_name="measure")
    with anyio.fail_after(60 * 4):
        await _wait_for_bbp(connection)


async def _start_bbp(
    connection: asyncssh.SSHClientConnection, program_name: str
) -> None:
    """Start the given BBP.

    Note that this simply starts the BBP in the background. It does not wait
    for it to complete.
    """
    py_code = _RUN_BBP.format(program_name=program_name)
    await run_py(connection, py_code)


async def _wait_for_bbp(connection: asyncssh.SSHClientConnection) -> None:
    """Wait until the BBP is done.

    Raises `RuntimeError` if the BBP failed or was cancelled.
    """
    while True:
        status = await run_py_parsed(connection, _GET_BBP_STATUS, PartialBbpStatus)
        bbp_state = status.state
        if bbp_state is BbpState.CANCELLED:
            raise RuntimeError("User cancelled the BBP")
        if bbp_state is BbpState.FAILED:
            raise RuntimeError("The BBP failed")
        if bbp_state is BbpState.COMPLETED:
            break
        await anyio.sleep(2)


async def read_file_as_json(
    connection: asyncssh.SSHClientConnection, file: Path, **kwargs: Any
) -> dict[str, Any]:
    """Read the given file and parse the contents as JSON."""
    text = await read_file_as_text(connection, file)
    result = json.loads(text, **kwargs)
    assert isinstance(result, dict)
    return result


async def read_file_as_text(
    connection: asyncssh.SSHClientConnection, file: Path
) -> str:
    """Read the given file and return its contents as a raw text string."""
    return await run(connection, f"cat {file}")


async def run_py(
    connection: asyncssh.SSHClientConnection, py_code: str, **kwargs: Any
) -> str:
    """Run the given python code and return the response."""
    command = _py_code_to_command(py_code)
    return await run(connection, command, **kwargs)


ParseType = TypeVar("ParseType")


async def run_py_parsed(
    connection: asyncssh.SSHClientConnection,
    py_code: str,
    parse_as: type[ParseType],
    **kwargs: Any,
) -> ParseType:
    """Run the given python code and return the parsed response."""
    command = _py_code_to_command(py_code)
    return await run_parsed(connection, command, parse_as, **kwargs)


async def run_parsed(
    connection: asyncssh.SSHClientConnection,
    command: str,
    parse_as: type[ParseType],
    **kwargs: Any,
) -> ParseType:
    """Run command and wait for the parsed response."""
    response = await run(connection, command, **kwargs)
    return TypeAdapter(parse_as).validate_json(response)


async def run(
    connection: asyncssh.SSHClientConnection, command: str, **kwargs: Any
) -> str:
    """Run command and wait for the response."""
    try:
        process: asyncssh.SSHCompletedProcess = await connection.run(
            command, check=True
        )
    except asyncssh.ProcessError as exc:
        _LOGGER.debug("stdout:\n%s", exc.stdout)
        _LOGGER.debug("stderr:\n%s", exc.stderr)
        raise
    response = process.stdout
    assert isinstance(response, str)
    return response


def _py_code_to_command(py_code: str) -> str:
    return f'python3 << "EOF"\n{py_code}\nEOF'


_PY_PRINT_PROCESSES = """
import psutil
import json

processes = {
    p.pid: p.as_dict(attrs=["name", "cmdline"])
    for p in psutil.process_iter()
}

print(json.dumps(processes))
"""


_RUN_BBP = """
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# Discard previous program (if any)
req = Request(
    url="http://localhost:8082/tasks/program",
    method="DELETE"
)
try:
    with urlopen(req):
        pass
except HTTPError as exc:
    # Discard 404 errors (no previous program)
    if exc.code != 404:
        raise

# Start next program
req = Request(
    url="http://localhost:8082/tasks/program",
    data='{{"name": "{program_name}"}}'.encode("utf-8"),
    method="PUT"
)
with urlopen(req):
    pass
"""

_GET_BBP_STATUS = """
from urllib.request import Request, urlopen
from urllib.error import HTTPError

req = Request(
    url="http://localhost:8082/tasks/program",
    method="GET"
)
with urlopen(req) as io:
    data = io.read()

print(data.decode("utf-8"))
"""


if __name__ == "__main__":
    main_sync()
