import nrpc_py
import os
import subprocess
from nrpc_py import rpcclass
from dataclasses import field
import nrpc_py


@rpcclass({
    'name': 1,
    'value': 2,
    'newonserver': 3,
})
class ChildInfo:
    name: str = 0
    value: int = 0
    newonserver: int = 0


@rpcclass({
    'summary': 1,
    'values': 2,
    'echos': 3
})
class ParentInfo:
    summary: str = ''
    values: list[int] = field(default_factory=list)
    echos: list[ChildInfo] = field(default_factory=list)


@rpcclass({
    'Hello': 1,
    'Hello2': 2,
})
class HelloService:
    def Hello(self, request: ParentInfo) -> ParentInfo:
        pass

    def Hello2(self, request: ParentInfo) -> list[ParentInfo]:
        pass


class ServerApplication:
    def __init__(self):
        self.counter = 0

    def start(self):
        cmd = nrpc_py.CommandLine({
            'port': 9002,
            'format': 'json',
            'wait': 10,
        })

        print(f'START Server started, {cmd["port"]}')

        sock = nrpc_py.RoutingSocket(
            type=nrpc_py.SocketType.BIND,
            protocol=nrpc_py.ProtocolType.TCP,
            format=nrpc_py.FormatType.JSON,
            caller='test_array_py_server',
            types=[
                ChildInfo,
                ParentInfo,
                [HelloService, self],
            ]
        )

        sock.bind('127.0.0.1', cmd['port'])

        dir_name = os.path.dirname(__file__)
        self.client = subprocess.Popen(
            f'python {dir_name}/test_array_client.py port={cmd["port"]} from_server=1',
            shell=False,
        )
        self.client.communicate()

        sock.close()

    def Hello(self, request: ParentInfo) -> ParentInfo:
        """HelloService's method"""
        print(f'CALL HelloServer.Hello, {self.counter}, {request}')
        self.counter += 1
        return ParentInfo(summary=f'test={self.counter}', values=[2, 3, 4], echos=[*request.echos])

    def Hello2(self, request: ParentInfo) -> list[ParentInfo]:
        """HelloService's method"""
        print(f'CALL HelloServer.Hello2, {self.counter}, {request}')
        self.counter += 1
        return [ParentInfo(summary=f'test={self.counter}', values=[2, 3, 4], echos=[*request.echos])]


if __name__ == '__main__':
    nrpc_py.init()
    app = ServerApplication()
    app.start()
