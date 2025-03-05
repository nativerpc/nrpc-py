import nrpc_py
import time
import sys
import subprocess
from nrpc_py import rpcclass


@rpcclass({
    'name': 1,
    'value': 2,
    'newonclient': 4,
})
class HelloRequest:
    name: str = 0
    value: int = 0
    newonclient: int = 0


@rpcclass({
    'summary': 1,
    'echo': 2
})
class HelloResponse:
    summary: str = ''
    echo: HelloRequest = None


@rpcclass({
    'Hello': 1,
    # 'Hello2': 2,
})
class HelloService:
    def Hello(self, request: HelloRequest) -> HelloResponse:
        pass

    # def Hello2(self, request: HelloRequest) -> list[HelloResponse]:
    #     pass


class ClientApplication:
    def __init__(self):
        self.sock = None
        self.counter = 0
        self.cmd = nrpc_py.CommandLine({
            'port': 9001,
            'from_server': False,
            'wait': 10,
            'rate': 1.0,
        })

    def connect(self):
        print(f'START Client started, {self.cmd["port"]}')
        self.sock = nrpc_py.RoutingSocket(nrpc_py.RoutingSocketOptions(
            type=nrpc_py.SocketType.CONNECT,
            protocol=nrpc_py.ProtocolType.TCP,
            format=nrpc_py.FormatType.JSON,
            caller='client_application_py',
            types=[
                HelloRequest,
                HelloResponse,
                HelloService,
            ]
        ))
        self.sock.connect('127.0.0.1', self.cmd['port'], wait=True, sync=True)

    def main_loop(self):
        start = time.time()
        while time.time() - start < self.cmd['wait']:
            time.sleep(1.0 / self.cmd['rate'])
            
            res = self.sock.server_call('HelloService.Hello', {'name': 'tester1'})
            print(f'SEND HelloService.Hello, 1, {res}')

            req = HelloRequest(name='tester2', value=234)
            res = self.sock.server_call('HelloService.Hello', req)
            print(f'SEND HelloService.Hello, 2, {res}')

            req = HelloRequest(name='tester3', value=444)
            res = self.sock.cast(HelloService).Hello(req)
            print(f'SEND HelloService.Hello, 3, {res}')

            # req = HelloRequest(name='tester4', value=555)
            # res = self.sock.cast(HelloService).Hello2(req)
            # print(f'SEND Hello, 4, {res}')

        self.sock.close()


if __name__ == '__main__':
    nrpc_py.init()
    app = ClientApplication()
    app.connect()
    app.main_loop()
