import asyncio
import os
import socket

import pytest
from _pytest.capture import CaptureFixture
from exo_rs import (
    NetworkingHandle,
    Pidfile,
    FromSwarm,
)


@pytest.mark.asyncio
async def test_sleep_on_multiple_items() -> None:
    print("PYTHON: starting handle")
    with (
        socket.socket(socket.AF_INET6) as tcp,
        socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as udp,
    ):
        tcp.bind(("::1", 0))
        udp.bind(("::1", 0))
        listen_port, discovery_port = tcp.getsockname()[1], udp.getsockname()[1]
    h = NetworkingHandle.new(
        os.urandom(16).hex().lstrip("0"),
        f"test-{os.urandom(8).hex()}",
        listen_port,
        discovery_port,
    )
    print("PYTHON: handle started")

    rt = asyncio.create_task(_await_recv(h))

    try:
        async with asyncio.timeout(15):
            for _ in range(2):
                await asyncio.sleep(1)
                await h.gossipsub_publish("topic", b"somehting or other")
    finally:
        rt.cancel()
        try:
            await rt
        except asyncio.CancelledError:
            pass


def test_pidfile(capsys: CaptureFixture[str]):
    with capsys.disabled():
        print("\nbefore python")
        scoped_lock_file()
        print("after python")


async def _await_recv(h: NetworkingHandle):
    while True:
        event = await h.recv()
        match event:
            case FromSwarm.Connection() as c:
                print(f"PYTHON: connection update: {c}")
            case FromSwarm.Message() as m:
                print(f"PYTHON: message: {m}")


def scoped_lock_file():
    a = Pidfile("/tmp/lock.pid", 0o0600)


if __name__ == "__main__":
    asyncio.run(test_sleep_on_multiple_items())
