#
#   Contents:
#
#       RoutingSocket
#           __init__
#           bind
#           connect
#           cast
#           server_thread
#           client_thread
#           client_call
#           forward_call
#           server_call
#           _incoming_call
#           _add_types
#           _add_server
#           _get_app_info
#           _get_schema
#           _set_schema
#           _assign_values
#           _sync_with_server
#           _sync_with_client
#           _find_new_fields
#           _find_new_methods
#           _find_missing_methods
#           client_id
#           wait
#           close
#
import time
import threading
import inspect
import json
import sys
import os
from typing import Dict, TypeVar, Type
from .common_base import (
    SocketType,
    ProtocolType,
    FormatType,
    RoutingSocketOptions,
    ApplicationInfo,
    SchemaInfo,
    FieldInfo,
    MethodInfo,
    ClassInfo,
    ServiceInfo,
    ServerInfo,
    RoutingMessage,
    ServerMessage,
    DYNAMIC_OBJECT,
    g_all_types,
    g_all_services,
    get_simple_type,
    assign_values,
    find,
    find_all,
)
from .server_socket import ServerSocket
from .client_socket import ClientSocket
from .service_client import ServiceClient
X = TypeVar('X')


class RoutingSocket:
    socket_type: SocketType
    protocol_type: ProtocolType
    format_type: FormatType
    entry_file: str
    ip_address: str
    port: int
    is_alive: bool
    server_socket: ServerSocket | None
    client_socket: ClientSocket | None
    processor: threading.Thread
    known_types: Dict[str, ClassInfo]
    known_services: Dict[str, ServiceInfo]
    known_servers: Dict[str, ServerInfo]
    call_count: int
    do_sync: bool
    is_ready: bool

    def __init__(
            self,
            type: SocketType,
            protocol: ProtocolType = ProtocolType.TCP,
            format: FormatType = FormatType.JSON,
            caller: str = 'unknown',
            types: list = [],
            port: int = 0,
    ):
        options = RoutingSocketOptions(
            type=type,
            protocol=protocol,
            format=format,
            caller=caller,
            types=types,
            port=port
        )
        assert not isinstance(type, RoutingSocketOptions)
        self.socket_type = options.type
        self.protocol_type = options.protocol
        self.format_type = options.format
        self.entry_file = os.path.basename(options.caller)
        self.ip_address = ''
        self.port = options.port
        self.is_alive = True
        self.server_socket = None
        self.client_socket = None
        self.processor = None
        self.known_types = {}
        self.known_services = {}
        self.known_servers = {}
        self.call_count = 0
        self.do_sync = False
        self.is_ready = False

        self.known_types[DYNAMIC_OBJECT] = g_all_types[DYNAMIC_OBJECT]
        
        self._add_types(options.types)

        assert self.known_types[DYNAMIC_OBJECT]

    def bind(self, ip_address='127.0.0.1', port=9000):
        assert self.socket_type == SocketType.BIND

        self.ip_address = ip_address
        self.port = port
        self.server_socket = ServerSocket(ip_address, port, port + 10000, self.entry_file)
        self.server_socket.bind()
        self.processor = threading.Thread(target=self.server_thread)
        self.processor.start()

    def connect(self, ip_address='127.0.0.1', port=9000, wait=True, sync=True):
        assert self.socket_type == SocketType.CONNECT

        self.ip_address = ip_address
        self.port = port
        self.client_socket = ClientSocket(ip_address, port, port + 10000, self.entry_file)
        self.do_sync = sync
        self.processor = threading.Thread(target=self.client_thread)
        self.processor.start()

        if wait:
            while not self.is_ready:
                time.sleep(0.1)

    def cast(self, clazz: Type[X], client_id=0) -> ServiceClient[X]:
        return ServiceClient[X](self, clazz, client_id)

    def server_thread(self):
        assert self.socket_type == SocketType.BIND

        self.is_ready = True

        while self.is_alive:
            client_id, req = self.server_socket.recv_norm()
            if not self.is_alive:
                break
            method_name = req[0].decode()
            command_parameters = json.loads(req[1].decode())

            # print(f"{Fore.BLUE}server{Fore.RESET} received request")
            # print(f"{Fore.BLUE}server{Fore.RESET} responding")

            resp = None
            if method_name == RoutingMessage.GetAppInfo:
                resp = self._get_app_info(command_parameters)
                self.server_socket.send_norm(
                    client_id,
                    [f'response:{method_name}', resp]
                )

            elif method_name == RoutingMessage.GetSchema:
                resp = self._get_schema(command_parameters, active_client_id=client_id)
                self.server_socket.send_norm(
                    client_id,
                    [f'response:{method_name}', resp]
                )

            elif method_name == RoutingMessage.SetSchema:
                resp = self._set_schema(command_parameters)
                self.server_socket.send_norm(
                    client_id,
                    [f'response:{method_name}', resp]
                )

            else:
                resp = self._incoming_call(method_name, command_parameters)
                self.server_socket.send_norm(
                    client_id,
                    [f'response:{method_name}', resp]
                )

    def client_thread(self):
        assert self.socket_type == SocketType.CONNECT
        self.client_socket.connect()

        if self.do_sync:
            assert self.client_socket.is_validated
            self._sync_with_server()
            self._sync_with_client()

        self.is_ready = True

        while self.is_alive:
            req = self.client_socket.recv_rev()
            if not self.is_alive:
                break
            if self.client_socket.is_lost:
                # print('Lost client')
                break
            method_name = req[0].decode()
            command_parameters = json.loads(req[1].decode())

            # Reverse client is bright red
            # print(f"{Fore.RED}client:{client_socket.client_id}{Fore.RESET} received request, {method_name}")
            # print(f"{Fore.RED}client:{client_socket.client_id}{Fore.RESET} responding")

            if method_name == RoutingMessage.GetAppInfo:
                resp = self._get_app_info(command_parameters)
                self.client_socket.send_rev([
                    f'response:{method_name}',
                    resp
                ])

            elif method_name == RoutingMessage.GetSchema:
                resp = self._get_schema(command_parameters)
                self.client_socket.send_rev([
                    f'response:{method_name}',
                    resp
                ])

            elif method_name == RoutingMessage.SetSchema:
                assert False

            else:
                resp = self._incoming_call(method_name, command_parameters)
                self.client_socket.send_rev([
                    f'response:{method_name}',
                    resp
                ])

    def client_call(self, client_id, method_name, params):
        assert self.socket_type == SocketType.BIND
        assert client_id in self.server_socket.get_client_ids()
        server_name = method_name.split('.')[0]
        method_name2 = method_name.split('.')[1]
        method_name3 = f'{server_name}.{method_name2}'
        is_untyped = isinstance(params, dict)

        # Using statically typed input/output claseses
        if not is_untyped:
            method_def = self.known_services[server_name].methods[method_name2]
            req_type = method_def.request_type
            req_type = self.known_types[req_type]
            assert req_type
            assert isinstance(params, req_type.clazz), f'Wrong request type! {params}, {req_type.clazz}'
            params2 = {}
            self._assign_values(method_def.request_type, params, params2, 1)
            params, params2 = params2, params

        # Server rev is dark red
        # print(f"{Style.DIM}{Fore.RED}server{Fore.RESET}{Style.NORMAL} sending request")

        res = None
        with self.server_socket.request_lock:
            self.server_socket.send_rev(
                client_id,
                [method_name3, params]
            )
            res = self.server_socket.recv_rev(client_id)
        if res:
            res = json.loads(res.decode())

        if not is_untyped:
            method_def = self.known_services[server_name].methods[method_name2]
            if method_def.response_type.endswith('[]'):
                res2 = []
                self._assign_values(method_def.response_type, res2, res, 0)
                res = res2
            else:
                ret_type = self.known_types[method_def.response_type]
                res2 = ret_type.clazz()
                self._assign_values(method_def.response_type, res2, res, 0)
                res = res2

        return res

    def forward_call(self, client_id, method_name, params):
        assert self.socket_type == SocketType.CONNECT
        return self.server_call(
            ServerMessage.ForwardCall.decode(),
            {
                'client_id': client_id,
                'method_name': method_name,
                'method_params': params
            }
        )

    def server_call(self, method_name, params):
        assert self.socket_type == SocketType.CONNECT
        assert isinstance(method_name, str)

        self.call_count += 1
        # print(f'Calling {self.call_count}, {server_name}.{method_name}') #, {req_data}')
        server_name = method_name.split('.')[0]
        method_name2 = method_name.split('.')[1]
        method_name3 = f'{server_name}.{method_name2}'
        is_untyped = isinstance(params, dict)

        # Using statically typed input/output claseses
        if not is_untyped:
            method_def = self.known_services[server_name].methods[method_name2]
            req_type = self.known_types[method_def.request_type]
            assert req_type
            assert isinstance(params, req_type.clazz), f'Wrong request type! {params}, {req_type.clazz}'
            params2 = {}
            self._assign_values(method_def.request_type, params, params2, 1)
            params, params2 = params2, params
            
        res = None
        with self.client_socket.request_lock:
            self.client_socket.send_norm(
                [method_name3, params]
            )
            res = self.client_socket.recv_norm()
        if res:
            res = json.loads(res.decode())

        if not is_untyped:
            method_def = self.known_services[server_name].methods[method_name2]
            if method_def.response_type.endswith('[]'):
                res2 = []
                self._assign_values(method_def.response_type, res2, res, 0)
                res = res2
            else:
                ret_type = self.known_types[method_def.response_type]
                res2 = ret_type.clazz()
                self._assign_values(method_def.response_type, res2, res, 0)
                res = res2

        return res

    def _incoming_call(self, method_name, request_data):
        self.call_count += 1
        # print(f'Calling {self.call_count}, {self.socket_type}, {method_name}')

        parts = method_name.split('.')
        assert len(parts) == 2
        assert isinstance(request_data, dict)

        if parts[0] not in self.known_servers or \
                parts[0] not in self.known_services:
            assert parts[0] in self.known_services
            if parts[0] not in self.known_services:
                service_info = self.known_services[parts[0]]
                if not service_info.service_errors:
                    service_info.service_errors = f'\nFailed invokation: {method_name}'
            return {}

        server = self.known_servers[parts[0]]
        service_info = self.known_services[parts[0]]

        if not hasattr(server.instance, parts[1]) or \
                parts[1] not in service_info.methods or \
                service_info.methods[parts[1]].method_errors:
            if parts[1] in service_info.methods:
                method1 = service_info.methods[parts[1]]
                response_type = method1.response_type
                result_obj = [] if response_type.endswith('[]') else self.known_types[response_type].clazz()
                result_data = [] if response_type.endswith('[]') else {}
                self._assign_values(response_type, result_obj, result_data, 1)
                if not method1.method_errors:
                    method1.method_errors = f'\nFailed invokation: {method_name}'
                return result_data
            else:
                if not service_info.service_errors:
                    service_info.service_errors = f'\nFailed invokation: {method_name}'
                return {}

        method1 = service_info.methods[parts[1]]
        method2 = getattr(server.instance, parts[1])
        request_type = method1.request_type
        response_type = method1.response_type

        data_obj = self.known_types[request_type].clazz()
        self._assign_values(request_type, data_obj, request_data, 0)
        result_obj = method2(data_obj)
        result_data = [] if response_type.endswith('[]') else {}
        self._assign_values(response_type, result_obj, result_data, 1)

        return result_data

    def _add_types(self, types):
        if isinstance(types, list) and \
            len(types) == 2 and \
            not isinstance(types[1], type) and \
            not isinstance(types[1], list):
            types = [types]

        for item in types:
            assert not isinstance(item, tuple)
            type_name = \
                item[0].__name__ if isinstance(item, list) else \
                item.__name__
            clazz = \
                item[0] if isinstance(item, list) else \
                item
            server_instance = \
                item[1] if isinstance(item, list) else \
                None
            if type_name in self.known_types or \
               type_name in self.known_services or \
                    type_name in self.known_servers:
                continue

            if type_name in g_all_types:
                assert g_all_types[type_name].fields
                type_info = g_all_types[type_name]
                self.known_types[type_name] = ClassInfo(
                    type_name=type_name,
                    fields={**type_info.fields},
                    size=type_info.size,
                    local=True,
                    clazz=clazz,
                )

            elif type_name in g_all_services:
                assert g_all_services[type_name].methods
                service_info = g_all_services[type_name]
                self.known_services[type_name] = ServiceInfo(
                    service_name=type_name,
                    methods={**service_info.methods},
                    local=True,
                    clazz=clazz
                )

                if server_instance:
                    self._add_server(clazz, server_instance)

            else:
                assert False, f'Missing metadata: {type_name}'

    def _add_server(self, server_type, server_instance):
        server_name = type(server_instance).__name__
        service_name = server_type.__name__
        service_info = self.known_services[service_name]
        assert service_name in self.known_services, f'Unknown server type! {service_name}'
        methods: Dict[str, MethodInfo] = {}
        server_instance.clazz = server_type

        for method_name, method_info in service_info.methods.items():
            handler = None
            service_sig = None
            server_sig = None
            if hasattr(type(server_instance), method_name):
                handler = getattr(type(server_instance), method_name)
                service_sig = inspect.signature(getattr(service_info.clazz, method_name))
                server_sig = inspect.signature(handler)
            else:
                handler = getattr(service_info.clazz, method_name)
                service_sig = inspect.signature(getattr(service_info.clazz, method_name))
                server_sig = inspect.signature(handler)
            service_req_type = None
            server_req_type = None
            for key, item3 in service_sig.parameters.items():
                if key == 'self':
                    continue
                service_req_type = get_simple_type(item3.annotation)
                break
            for key, item3 in server_sig.parameters.items():
                if key == 'self':
                    continue
                server_req_type = get_simple_type(item3.annotation)
                break
            service_res_type = get_simple_type(service_sig.return_annotation)
            server_res_type = get_simple_type(server_sig.return_annotation)

            if service_req_type != server_req_type:
                method_info.method_errors += \
                    f'\nServer signature mismatch! {server_name}, {method_name}, {service_req_type}, {server_req_type}'
                continue
            elif service_res_type != server_res_type:
                method_info.method_errors += \
                    f'\nServer signature mismatch! {server_name}, {method_name}, {service_req_type}, {server_req_type}'
                continue
            elif server_req_type != method_info.request_type:
                method_info.method_errors += \
                    f'\nServer signature mismatch in request! {server_name}, {method_name}, {server_req_type}, {method_info.request_type}'
                continue
            elif server_res_type != method_info.response_type:
                method_info.method_errors += \
                    f'\nServer signature mismatch in response! {server_name}, {method_name}, {server_res_type}, {method_info.response_type}'
                continue
            elif server_req_type not in self.known_types:
                method_info.method_errors += \
                    f'\nUnknown parameter type! {method_name}, {server_req_type}'
                continue

            assert server_res_type[0:-2] if server_res_type.endswith('[]') else server_res_type in self.known_types
            assert handler and handler.__name__ == method_name
                
            methods[method_name] = MethodInfo(
                method_name=method_name,
                request_type=server_req_type,
                response_type=server_res_type,
                id_value=method_info.id_value,
                local=True
            )
        server_info = ServerInfo(
            server_name=server_name,
            service_name=service_name,
            methods=methods,
            instance=server_instance,
        )
        self.known_servers[service_name] = server_info

    def _get_app_info(self, req) -> ApplicationInfo:
        this_socket = ''
        if self.socket_type == SocketType.BIND:
            this_socket = f'{self.server_socket.port}'
        else:
            this_socket = f'{self.client_socket.port}:{self.client_socket.client_id}'

        clients: list[ApplicationInfo.AppClientInfo] = []
        if self.socket_type == SocketType.BIND and req.get('with_clients', False):
            for item in self.server_socket.clients:
                clients.append(ApplicationInfo.AppClientInfo(
                    client_id=item.client_id,
                    is_validated=item.is_validated,
                    is_lost=item.is_lost,
                    entry_file=item.client_metadata['entry_file'],
                ))

        return ApplicationInfo(
            server_id=self.port,
            client_id=0 if self.socket_type == SocketType.BIND else self.client_socket.client_id,
            is_alive=self.is_alive,
            is_ready=self.is_ready,
            types=len(self.known_types),
            services=len(self.known_services),
            servers=len(self.known_servers),
            metadata=self.client_socket.server_metadata if self.socket_type == SocketType.CONNECT else self.server_socket.metadata,
            this_socket=this_socket,
            client_count=0 if self.socket_type == SocketType.CONNECT else len(self.server_socket.clients),
            clients=clients,
            entry_file=self.entry_file,
            ip_address=self.ip_address,
            port=self.port,
            format='json' if self.format_type == FormatType.JSON else 'binary',
        )

    def _get_schema(self, req, active_client_id=None) -> SchemaInfo:
        types: SchemaInfo.SchemaTypeInfo = []
        for key, value in self.known_types.items():
            if key == DYNAMIC_OBJECT:
                continue
            types.append(SchemaInfo.SchemaTypeInfo(
                type_name=key,
                size=-1,
                fields=len(value.fields),
                local=value.local,
                type_errors=value.type_errors,
            ))

        fields: SchemaInfo.SchemaFieldInfo = []
        for key, value in self.known_types.items():
            for key2, field2 in value.fields.items():
                assert field2.field_type
                fields.append(SchemaInfo.SchemaFieldInfo(
                    type_name=key,
                    field_name=field2.field_name,
                    field_type=field2.field_type,
                    id_value=field2.id_value,
                    offset=-1,
                    size=-1,
                    local=field2.local,
                    field_errors=field2.field_errors,
                ))
                assert key2 == field2.field_name

        services: SchemaInfo.SchemaServiceInfo = []
        for service_name, service_info in self.known_services.items():
            services.append(SchemaInfo.SchemaServiceInfo(
                service_name=service_info.service_name,
                methods=len(service_info.methods),
                local=service_info.local,
                has_server=service_info.service_name in self.known_servers,
                service_errors=service_info.service_errors,
            ))
            assert service_name == service_info.service_name

        methods: SchemaInfo.SchemaMethodInfo = []
        for service_name, service_info in self.known_services.items():
            for method_name, method_info in service_info.methods.items():
                methods.append(SchemaInfo.SchemaMethodInfo(
                    service_name=service_info.service_name,
                    method_name=method_name,
                    request_type=method_info.request_type,
                    response_type=method_info.response_type,
                    id_value=method_info.id_value,
                    local=method_info.local,
                    method_errors=method_info.method_errors,
                ))

        clients: SchemaInfo.SchemaClientInfo = []
        if self.socket_type == SocketType.BIND:
            self.server_socket.update()
            for item in self.server_socket.clients:
                clients.append(SchemaInfo.SchemaClientInfo(
                    main_port=self.server_socket.port,
                    client_id=item.client_id,
                    is_validated=item.is_validated,
                    is_lost=item.is_lost,
                    entry_file=item.client_metadata['entry_file'],
                    client_metadata=item.client_metadata,
                ))

        servers: SchemaInfo.SchemaServerInfo = []
        if self.socket_type == SocketType.CONNECT:
            servers.append(SchemaInfo.SchemaServerInfo(
                port=self.client_socket.port,
                entry_file=self.client_socket.server_metadata['entry_file'],
                server_metadata=self.client_socket.server_metadata,
            ))

        this_socket = ''
        if self.socket_type == SocketType.BIND:
            this_socket = f'{self.server_socket.port}'
        else:
            this_socket = f'{self.client_socket.port}:{self.client_socket.client_id}'

        return SchemaInfo(
            server_id=self.port,
            client_id=0 if self.socket_type == SocketType.BIND else self.client_socket.client_id,
            types=types,
            services=services,
            fields=fields,
            methods=methods,
            metadata=self.server_socket.metadata if self.socket_type == SocketType.BIND else self.client_socket.metadata,
            active_client=active_client_id or 0,
            this_socket=this_socket,
            clients=clients,
            servers=servers,
            entry_file=self.entry_file,
        )

    def _set_schema(self, req) -> SchemaInfo:
        added1 = self._find_new_fields(req, True)
        added2 = self._find_new_methods(req, True)

        # print(f'Sync ready: 1, {len(added1)}, {len(added2)}')

        return self._get_schema(req)

    def _assign_values(self, type_name: str, obj_data: any, json_data: dict | list, target: int):
        assign_values(type_name, obj_data, json_data, target)

    def _sync_with_server(self):
        res = self.server_call(RoutingMessage.GetSchema, {})

        self._find_missing_methods(res)
        added1 = self._find_new_fields(res, True)
        added2 = self._find_new_methods(res, True)

        # console.log(f'Sync ready: 2, {len(added1)}, {len(added2)}')

    def _sync_with_client(self):
        req = self._get_schema(None)
        res = self.server_call(RoutingMessage.SetSchema, req)
        added1 = self._find_new_fields(res, False)
        added2 = self._find_new_methods(res, False)
        assert len(added1) == 0
        assert len(added2) == 0
        # console.log(f'Sync ready: 3, {len(added1)}, {len(added2)}')

    def _find_new_fields(self, schema, do_add):
        to_add = []
        for server_type_info in schema['types']:
            type_name = server_type_info['type_name']
            type_fields = find_all(schema['fields'], lambda x: x['type_name'] == type_name)
            assert type_name
            if type_name not in self.known_types:
                pass
            else:
                known_type = self.known_types[type_name]
                for field_info in type_fields:
                    field_name = field_info['field_name']
                    field_type = field_info['field_type']
                    assert field_name
                    assert 'id_value' in field_info
                    if field_name not in known_type.fields:
                        for key2, item2 in known_type.fields.items():
                            if item2.id_value == field_info['id_value']:
                                item2.field_errors += \
                                    f'\nDuplicate id! {type_name}.{field_name}, {key2}={item2.id_value}'
                                continue
                        to_add.append({
                            'type_name': type_name,
                            'field_name': field_name,
                            'field_type': field_type,
                            'id_value': field_info['id_value']
                        })
                    else:
                        assert field_name in known_type.fields
                        if field_info['id_value'] != known_type.fields[field_name].id_value:
                            known_type.fields[field_name].field_errors += \
                                f'\nField numbering mismatch! {type_name}.{field_name}, ' \
                                f'{field_info["id_value"]} != {known_type.fields[field_name].id_value}'
                            continue

        # Add missing fields
        #
        if do_add:
            for item in to_add:
                assert item['type_name'] in self.known_types
                known_fields = self.known_types[item['type_name']]
                assert known_fields
                known_fields.fields[item['field_name']] = FieldInfo(
                    field_name=item['field_name'],
                    field_type=item['type_name'],
                    id_value=item['id_value'],
                    offset=-1,
                    size=-1,
                    local=False
                )

        return to_add

    def _find_new_methods(self, schema, do_add):
        to_add = []
        for service_info in schema['services']:
            service_name = service_info['service_name']
            service_methods = find_all(schema['methods'], lambda x: x['service_name'] == service_name)
            if service_name not in self.known_services:
                pass
            else:
                my_service_info = self.known_services[service_name]
                for method_info in service_methods:
                    method_name = method_info['method_name']
                    assert method_info['id_value'] > 0
                    if method_name not in my_service_info.methods:
                        for key2, item2 in my_service_info.methods.items():
                            key3 = item2.method_name
                            assert key2 == key3
                            if item2.id_value == method_info['id_value']:
                                item2.method_errors += \
                                    f'\nDuplicate id! {service_name}.{method_name}, {item2.id_value}, {method_info["id_value"]}'
                                continue
                        to_add.append({
                            'service_name': service_name,
                            'method_name': method_name,
                            'id_value': method_info['id_value'],
                            'request_type': method_info['request_type'],
                            'response_type': method_info['response_type'],
                        })
                    else:
                        my_method = my_service_info.methods[method_name]
                        if method_info['id_value'] != my_method.id_value:
                            my_method.method_errors += \
                                f'\nMethod numbering mismatch! {service_name}.{method_name}, ' \
                                f'{method_info["id_value"]}, {my_method.id_value}'
                            continue

        # Add missing methods
        #
        if do_add:
            for item in to_add:
                self.known_services[item['service_name']].methods[item['method_name']] = \
                    MethodInfo(
                        method_name=item['method_name'],
                        request_type=item['request_type'],
                        response_type=item['response_type'],
                        id_value=item['id_value'],
                        local=False
                )

        return to_add

    def _find_missing_methods(self, schema):
        for service_name, my_service_info in self.known_services.items():
            remote_service_info = find(schema['services'], lambda x: x['service_name'] == service_name)
            remote_service_methods = find_all(schema['methods'], lambda x: x['service_name'] == service_name)
            if not remote_service_info:
                my_service_info.service_errors += \
                    f'\nMissing remote service! {service_name}'
                continue
            for method_name, my_method_info in my_service_info.methods.items():
                assert my_method_info.id_value > 0
                if not find(remote_service_methods, lambda x: x['method_name'] == method_name):
                    my_method_info.method_errors += \
                        f'\nMissing remote method! {service_name}.{method_name}'
                    continue

    @property
    def client_id(self):
        return self.client_socket.client_id if self.socket_type == SocketType.CONNECT else 0

    def wait(self):
        try:
            if self.socket_type == SocketType.BIND:
                self.server_socket.wait()
            else:
                self.client_socket.wait()
        except KeyboardInterrupt:
            print('Closed with keyboard')
            self.close()
            sys.exit(0)

    def close(self):
        self.is_alive = False
        if self.socket_type == SocketType.BIND:
            self.server_socket.is_alive = False
        else:
            self.client_socket.is_alive = False
        self.processor.join()
        if self.socket_type == SocketType.BIND:
            self.server_socket.close()
        else:
            self.client_socket.close()
        self.server_socket = None
        self.client_socket = None
