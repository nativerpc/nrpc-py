#
#   Contents:
#
#       ServiceClient
#           __init__
#           dynamic_call
#
from typing import TypeVar, Generic, Type, Any
from .common_base import SocketType

X = TypeVar('X')


class ServiceClient(Generic[X]):
    def __init__(self, socket: Any, clazz: Type[X], client_id=0):
        super().__init__()

        self.socket = socket
        self.clazz = clazz
        self.client_id = client_id
        self.service_name = self.clazz.__name__
        self.service_info = self.socket.known_services[self.service_name]

        for method_name in self.service_info.methods.keys():
            full_name = f'{self.service_name}.{method_name}'
            setattr(
                self.__class__,
                method_name,
                lambda _, params, full_name=full_name:
                    self.dynamic_call(params, full_name)
            )

    def dynamic_call(self, params, full_name):
        if self.socket.socket_type == SocketType.BIND:
            assert self.client_id > 0
            return self.socket.client_call(
                self.client_id,
                full_name,
                params
            )
        else:
            return self.socket.server_call(
                full_name,
                params
            )
