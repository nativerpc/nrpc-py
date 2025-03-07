import nrpc_py

@nrpc_py.rpcclass({
    'x': 1,
    'y': 2,
    'z': 3,
})
class TestClass:
    x: str = 0
    y: int = 0
    z: float = 0.0

@nrpc_py.rpcclass({
    'test1': 1,
    'test2': 2,
})
class TestService:
    def test1(self, request: TestClass) -> TestClass:
        pass

    def test2(self, request: dict) -> dict:
        pass


class TestApplication:
    def start(self):
        sock = nrpc_py.RoutingSocket(
            type=nrpc_py.SocketType.BIND,
            protocol=nrpc_py.ProtocolType.TCP,
            format=nrpc_py.FormatType.JSON,
            caller='test_build_py',
            types=[
                TestClass,
                [TestService, self]
            ],
        )
        print(f'SOCK {sock}')
        sock = nrpc_py.RoutingSocket(
            type=nrpc_py.SocketType.CONNECT,
            protocol=nrpc_py.ProtocolType.TCP,
            format=nrpc_py.FormatType.JSON,
            caller='test_build_py',
            types=[
                TestClass,
                [TestService, self]
            ],
        )
        print(f'SOCK {sock}')

    def test1(self, request: TestClass) -> TestClass:
        pass

    def test2(self, request: dict) -> dict:
        pass

if __name__ == '__main__':
    nrpc_py.init()
    app = TestApplication()
    app.start()
