"""Artifact-evaluation network blocker loaded by Python's sitecustomize hook."""

from __future__ import annotations

import errno
import json
import os
import socket
import time


if os.environ.get("PYFEX_NETWORK_SANDBOX") == "blocked":
    _LOG_FILE = os.environ.get("PYFEX_NETWORK_BLOCK_LOG_FILE")
    _ORIGINAL_SOCKET = socket.socket
    _NETWORK_FAMILIES = {
        getattr(socket, "AF_INET", object()),
        getattr(socket, "AF_INET6", object()),
    }

    def _jsonable(value: object) -> object:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, (list, tuple)):
            return [_jsonable(item) for item in value]
        if isinstance(value, dict):
            return {str(key): _jsonable(item) for key, item in value.items()}
        return repr(value)

    def _log(action: str, detail: object | None = None) -> None:
        if not _LOG_FILE:
            return
        try:
            parent = os.path.dirname(_LOG_FILE)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(_LOG_FILE, "a", encoding="utf-8") as fp:
                fp.write(
                    json.dumps(
                        {
                            "event": "network_blocked",
                            "action": action,
                            "detail": _jsonable(detail),
                            "pid": os.getpid(),
                            "time": time.time(),
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
        except Exception:
            pass

    def _is_network_family(family: object) -> bool:
        return family in _NETWORK_FAMILIES

    def _blocked(action: str, detail: object | None = None) -> None:
        _log(action, detail)
        raise OSError(errno.ENETUNREACH, f"PyFEX artifact network sandbox blocked {action}")

    def _blocked_dns(action: str, detail: object | None = None) -> None:
        _log(action, detail)
        raise socket.gaierror(socket.EAI_FAIL, f"PyFEX artifact network sandbox blocked {action}")

    class NetworkBlockedSocket(_ORIGINAL_SOCKET):
        def __init__(
            self,
            family: socket.AddressFamily = socket.AF_INET,
            type: socket.SocketKind = socket.SOCK_STREAM,
            proto: int = 0,
            fileno: int | None = None,
        ) -> None:
            if _is_network_family(family):
                _blocked(
                    "socket.socket",
                    {"family": int(family), "type": int(type), "proto": int(proto), "fileno": fileno},
                )
            super().__init__(family, type, proto, fileno)

        def connect(self, address: object) -> None:
            if _is_network_family(self.family) or isinstance(address, tuple):
                _blocked("socket.connect", {"family": int(self.family), "address": address})
            return super().connect(address)

        def connect_ex(self, address: object) -> int:
            if _is_network_family(self.family) or isinstance(address, tuple):
                _log("socket.connect_ex", {"family": int(self.family), "address": address})
                return errno.ENETUNREACH
            return super().connect_ex(address)

        def bind(self, address: object) -> None:
            if _is_network_family(self.family) or isinstance(address, tuple):
                _blocked("socket.bind", {"family": int(self.family), "address": address})
            return super().bind(address)

        def sendto(self, *args: object) -> int:
            address = args[-1] if args else None
            if _is_network_family(self.family) or isinstance(address, tuple):
                _blocked("socket.sendto", {"family": int(self.family), "address": address})
            return super().sendto(*args)

    def _create_connection(address: object, timeout: object = None, source_address: object | None = None) -> None:
        _blocked(
            "socket.create_connection",
            {"address": address, "timeout": timeout, "source_address": source_address},
        )

    def _getaddrinfo(*args: object, **kwargs: object) -> None:
        _blocked_dns("socket.getaddrinfo", {"args": args, "kwargs": kwargs})

    def _gethostbyname(hostname: object) -> None:
        _blocked_dns("socket.gethostbyname", {"hostname": hostname})

    def _gethostbyname_ex(hostname: object) -> None:
        _blocked_dns("socket.gethostbyname_ex", {"hostname": hostname})

    def _gethostbyaddr(host: object) -> None:
        _blocked_dns("socket.gethostbyaddr", {"host": host})

    def _getnameinfo(sockaddr: object, flags: object) -> None:
        _blocked_dns("socket.getnameinfo", {"sockaddr": sockaddr, "flags": flags})

    socket.socket = NetworkBlockedSocket
    socket.SocketType = NetworkBlockedSocket
    socket.create_connection = _create_connection
    socket.getaddrinfo = _getaddrinfo
    socket.gethostbyname = _gethostbyname
    socket.gethostbyname_ex = _gethostbyname_ex
    socket.gethostbyaddr = _gethostbyaddr
    socket.getnameinfo = _getnameinfo
