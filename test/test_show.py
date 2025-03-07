import nrpc_py
import time
import sys
import os
import subprocess
from nrpc_py import rpcclass


@rpcclass({
    'name': 1,
    'value': 2,
    'newonserver': 3,
})
class HelloRequest:
    name: str = 0
    value: int = 0
    newonserver: int = 0


@rpcclass({
    'summary': 1,
    'echo': 2
})
class HelloResponse:
    summary: str = ''
    echo: HelloRequest = None


@rpcclass({
    'Hello': 1,
    'Hello2': 2,
})
class HelloService:
    def Hello(self, request: HelloRequest) -> HelloResponse:
        pass

    def Hello2(self, request: dict) -> dict:
        pass


class ServerApplication:
    def __init__(self):
        self.sock = None
        self.counter = 0
        self.cmd = nrpc_py.CommandLine({
            'port': 9001,
            'format': 'json',
            'wait': 1000,
            'rate': 1.0,
        })

    def bind(self):
        print(f'START Server started, {self.cmd["port"]}')
        self.sock = nrpc_py.RoutingSocket(
            type=nrpc_py.SocketType.BIND,
            protocol=nrpc_py.ProtocolType.TCP,
            format=nrpc_py.FormatType.JSON,
            caller='test_show_py',
            types=[
                HelloRequest,
                HelloResponse,
                [HelloService, self],
            ]
        )
        self.sock.bind('127.0.0.1', self.cmd['port'])

    def start_client(self):
        dir_name = os.path.dirname(__file__)
        self.client = subprocess.Popen(
            f'python {dir_name}/test_show_client.py port={self.cmd["port"]} '
            f'rate={self.cmd["rate"]} from_server=1',
            shell=False,
        )
        self.client.communicate()
        self.sock.close()

    def Hello(self, request: HelloRequest) -> HelloResponse:
        """HelloService's method"""
        print(f'CALL ServerApplication.Hello, {self.counter}, {request}')
        self.counter += 1
        return HelloResponse(f'test={self.counter}', request)

    def Hello2(self, request: dict) -> dict:
        """HelloService's method"""
        print(f'CALL ServerApplication.Hello2, {self.counter}, {request}')
        self.counter += 1
        return {'summary': f'test={self.counter}', 'echo': request}



if __name__ == '__main__':
    nrpc_py.init()
    app = ServerApplication()
    app.bind()
    app.start_client()
