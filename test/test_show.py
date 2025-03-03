import nrpc_py
import time
import sys
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
    'name': 1,
    'value': 2,
    'newonclient': 4,
})
class HelloRequest_Client:
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
    'summary': 1,
    'echo': 2
})
class HelloResponse_Client:
    summary: str = ''
    echo: HelloRequest_Client = None


@rpcclass({
    'Hello': 1,
    'Hello2': 2,
})
class HelloService:
    def Hello(self, request: HelloRequest) -> HelloResponse:
        pass

    def Hello2(self, request: HelloRequest) -> list[HelloResponse]:
        pass


@rpcclass({
    'Hello': 1,
    # 'Hello2': 2,
})
class HelloService_Client:
    def Hello(self, request: HelloRequest_Client) -> HelloResponse_Client:
        pass

    # def Hello2(self, request: HelloRequest_Client) -> list[HelloResponse_Client]:
    #     pass


class HelloServer:
    def __init__(self):
        self.counter = 0

    def Hello(self, request: HelloRequest) -> HelloResponse:
        print(f'CALL HelloServer.Hello, {self.counter}, {request}')
        self.counter += 1
        return HelloResponse(f'test={self.counter}', request)

    def Hello2(self, request: HelloRequest) -> list[HelloResponse]:
        print(f'CALL HelloServer.Hello2, {self.counter}, {request}')
        self.counter += 1
        return [HelloResponse(f'test={self.counter}', request)]


def start():
    cmd = nrpc_py.CommandLine(line=sys.argv, fields={
        'port': 9001,
        'format': 'json',
        'wait': 10,
    })

    sock1 = nrpc_py.RoutingSocket(nrpc_py.RoutingSocketOptions(
        type=nrpc_py.SocketType.BIND,
        protocol=nrpc_py.ProtocolType.TCP,
        format=nrpc_py.FormatType.JSON,
        caller='test_show_py_server',
        types=[
            HelloRequest,
            HelloResponse,
            [HelloService, HelloServer()],
        ]
    ))
    sock2 = nrpc_py.RoutingSocket(nrpc_py.RoutingSocketOptions(
        type=nrpc_py.SocketType.CONNECT,
        protocol=nrpc_py.ProtocolType.TCP,
        format=nrpc_py.FormatType.JSON,
        caller='test_show_py_client',
        types=[
            HelloRequest_Client,
            HelloResponse_Client,
            HelloService_Client,
        ],
        drop_postfix='_Client'
    ))

    sock1.bind('127.0.0.1', cmd['port'])
    print(f'START Server started, {cmd["port"]}')
    sock2.connect('127.0.0.1', cmd['port'], wait=True, sync=True)
    print(f'START Client started, {cmd["port"]}')

    start = time.time()
    while time.time() - start < cmd['wait']:
        res = sock2.server_call('HelloService_Client.Hello', {'name': 'tester1'})
        print(f'SEND Hello, 1, {res}')

        req = HelloRequest_Client(name='tester2', value=234)
        res = sock2.server_call('HelloService_Client.Hello', req)
        print(f'SEND Hello, 2, {res}')

        req = HelloRequest_Client(name='tester3', value=444)
        res = sock2.cast(HelloService_Client).Hello(req)
        print(f'SEND Hello, 3, {res}')

        # req = HelloRequest_Client(name='tester4', value=555)
        # res = sock2.cast(HelloService_Client).Hello2(req)
        # print(f'SEND Hello, 4, {res}')

        time.sleep(1.0)

    sock2.close()
    sock1.close()


if __name__ == '__main__':
    start()
