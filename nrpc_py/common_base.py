#
#   Contents:
#
#       SocketType
#       ProtocolType
#       FormatType
#       RoutingSocketOptions
#       ServerMessage
#       RoutingMessage
#       WebSocketInfo
#       SocketMetadataInfo
#       ClientInfo
#       ApplicationInfo
#       SchemaInfo
#       FieldType
#       FieldNames
#       DYNAMIC_OBJECT
#       FieldInfo
#       MethodInfo
#       ClassInfo
#       ServiceInfo
#       ServerInfo
#
#       g_all_types
#       g_all_services
#       register_class
#       ClassManager
#       rpcclass
#       construct_item
#       destroy_item
#       construct_json
#       assign_values
#       get_class_string
#       get_simple_type
#
#       init
#       CommandLine
#       is_number
#       find
#       find_all
#       check_serializable
#       ctrl_handler
#
import os
import sys
import inspect
import json
import datetime
from dataclasses import dataclass
from typing import Dict, TypedDict, Type, get_args
from enum import Enum


class SocketType(Enum):
    BIND = 1
    CONNECT = 2


class ProtocolType(Enum):
    TCP = 1
    WS = 2
    HTTP = 3


class FormatType(Enum):
    BINARY = 1
    JSON = 2


@dataclass
class RoutingSocketOptions:
    type: SocketType
    protocol: ProtocolType
    format: FormatType
    caller: str
    types: list
    port: int = 0


class ServerMessage:
    AddClient = b'ServerMessage.AddClient'
    ClientAdded = b'ServerMessage.ClientAdded'
    ValidateClient = b'ServerMessage.ValidateClient'
    ClientValidated = b'ServerMessage.ClientValidated'
    ForwardCall = b'ServerMessage.ForwardCall'


class RoutingMessage:
    GetAppInfo = 'RoutingMessage.GetAppInfo'
    GetSchema = 'RoutingMessage.GetSchema'
    SetSchema = 'RoutingMessage.SetSchema'


class WebSocketInfo:
    pass


class SocketMetadataInfo(TypedDict):
    server_id: int
    client_id: int
    lang: str
    ip_address: str
    main_port: int
    main_port_rev: int
    host: str
    entry_file: str
    start_time: str
    client_signature: str
    client_signature_rev: str
    server_signature: str
    server_signature_rev: str


@dataclass
class ClientInfo:
    client_id: int
    client_signature: bytes
    client_signature_rev: bytes
    client_metadata: SocketMetadataInfo
    connect_time: datetime.datetime
    is_validated: bool
    is_lost: bool


class ApplicationInfo(TypedDict):
    class AppClientInfo(TypedDict):
        client_id: int
        is_validated: bool
        is_lost: bool
        entry_file: str

    server_id: int
    client_id: int
    is_alive: bool
    is_ready: bool
    socket_type: str
    protocol_type: str
    types: int
    services: int
    servers: int
    metadata: SocketMetadataInfo
    this_socket: str
    client_count: int
    clients: list[AppClientInfo]
    client_ids: list[int]
    entry_file: str
    ip_address: str
    port: int
    format: str


class SchemaInfo(TypedDict):
    class SchemaTypeInfo(TypedDict):
        type_name: str
        size: int
        fields: int
        local: bool
        type_errors: str

    class SchemaServiceInfo(TypedDict):
        service_name: str
        methods: int
        local: bool
        has_server: bool
        service_errors: str

    class SchemaFieldInfo(TypedDict):
        type_name: str
        field_name: str
        field_type: str
        id_value: int
        offset: int
        size: int
        local: bool
        field_errors: str

    class SchemaMethodInfo(TypedDict):
        service_name: str
        method_name: str
        request_type: str
        response_type: str
        id_value: int
        local: bool
        method_errors: str

    class SchemaClientInfo(TypedDict):
        main_port: int
        client_id: int
        is_validated: bool
        is_lost: bool
        entry_file: str
        client_metadata: SocketMetadataInfo

    class SchemaServerInfo(TypedDict):
        port: int
        entry_file: str
        server_metadata: SocketMetadataInfo

    server_id: int
    client_id: int
    types: list[SchemaTypeInfo]
    services: list[SchemaServiceInfo]
    fields: list[SchemaFieldInfo]
    methods: list[SchemaMethodInfo]
    metadata: SocketMetadataInfo
    active_client: int
    this_socket: str
    clients: list[SchemaClientInfo]
    servers: list[SchemaServerInfo]
    entry_file: str


class FieldType(Enum):
    Unknown = 0
    Complex = 1
    Int = 2
    Float = 3
    String = 4
    Json = 5


TypeNames = [
    'unknown',
    'complex',
    'int',
    'float',
    'str',
    'dict'
]
DYNAMIC_OBJECT = 'dict'


class FieldInfo:
    field_name: str
    field_type: str
    id_value: int
    offset: int
    size: int
    local: bool
    field_errors: str

    def __init__(self, field_name: str, field_type: str, id_value: int, offset: int, size: int, local: bool):
        self.field_name = field_name
        self.field_type = field_type
        self.id_value = id_value
        self.offset = offset
        self.size = size
        self.local = local
        self.field_errors = ''


class MethodInfo:
    method_name: str
    request_type: str
    response_type: str
    id_value: int
    local: bool
    method_errors: str

    def __init__(self, method_name, request_type, response_type, id_value, local):
        self.method_name = method_name
        self.request_type = request_type
        self.response_type = response_type
        self.id_value = id_value
        self.local = local
        self.method_errors = ''


class ClassInfo:
    type_name: str
    fields: Dict[str, FieldInfo]
    size: int
    local: bool
    clazz: type
    type_errors: str

    def __init__(self, type_name, fields, size, local, clazz):
        self.type_name = type_name
        self.fields = fields
        self.size = size
        self.local = local
        self.clazz = clazz
        self.type_errors = ''


class ServiceInfo:
    service_name: str
    methods: Dict[str, MethodInfo]
    local: bool
    clazz: type
    service_errors: str

    def __init__(self, service_name, methods, local, clazz):
        self.service_name = service_name
        self.methods = methods
        self.local = local
        self.clazz = clazz
        self.service_errors = ''


class ServerInfo:
    server_name: str
    service_name: str
    instance: any
    methods: Dict[str, MethodInfo]
    server_errors: str

    def __init__(self, server_name, service_name, instance, methods):
        self.server_name = server_name
        self.service_name = service_name
        self.instance = instance
        self.methods = methods
        self.server_errors = ''


g_all_types: Dict[str, ClassInfo] = {}
g_all_services: Dict[str, ServiceInfo] = {}

g_all_types[DYNAMIC_OBJECT] = ClassInfo(
    type_name=DYNAMIC_OBJECT,
    fields={},
    size=-1,
    clazz=dict,
    local=True
)


def register_class(clazz: Type, pending_fields: dict):
    global g_all_types, g_all_services

    type_name = clazz.__name__
    inst = clazz()
    norm_fields = inst.__dict__
    class_fields = [x for x in list(norm_fields.keys()) if not x.startswith('_')]
    class_methods = [f for f in dir(clazz) if not f.startswith('__')]
    field_infos: Dict[str, FieldInfo] = {}
    method_infos: Dict[str, MethodInfo] = {}
    missing_fields = list(class_fields)
    missing_methods = [x for x in list(class_methods) if not x.startswith('_')]
    typed_fields = inspect.get_annotations(clazz)

    assert not (type_name in g_all_types), f'Duplicate type: {type_name}'
    assert missing_fields or missing_methods

    if missing_fields:
        for key, id_value in pending_fields.items():
            assert key in class_fields, f'Mismatched field name! {type_name}.{key}, {clazz.__name__}, {class_fields}'
            field_type = get_simple_type(typed_fields[key])
            field_infos[key] = FieldInfo(
                field_name=key,
                id_value=int(id_value),
                field_type=field_type,
                offset=-1,
                size=-1,
                local=True
            )
            assert field_type
            if key not in missing_fields:
                assert key in missing_fields, f'Duplicate field description! {type_name}.{key}'
            missing_fields.remove(key)

        assert len(missing_fields) == 0, f'Unused fields! {type_name}, {missing_fields}'

        g_all_types[type_name] = ClassInfo(
            type_name=type_name,
            fields=field_infos,
            size=-1,
            clazz=clazz,
            local=True
        )

    else:
        for key, id_value in pending_fields.items():
            if key not in missing_methods:
                assert key in missing_methods, f'Duplicate method description! {type_name}.{key}'
            missing_methods.remove(key)
            handler = getattr(clazz, key)
            sig = inspect.signature(handler)
            params = sig.parameters
            req_type = None
            ret_type = None
            for param_name, param_info in params.items():
                if param_name == 'self':
                    continue
                req_type = get_simple_type(param_info.annotation)
                req_type_nl = req_type[0: len(req_type) - 2] if req_type.endswith('[]') else req_type
                assert req_type_nl in g_all_types, \
                    f'Unknown parameter type! {req_type}'
                break
            ret_type = get_simple_type(sig.return_annotation)
            ret_type_nl = ret_type[0: len(ret_type) - 2] if ret_type.endswith('[]') else ret_type
            assert ret_type_nl in g_all_types
            assert key == handler.__name__
            method_infos[key] = MethodInfo(
                method_name=key,
                request_type=req_type,
                response_type=ret_type,
                id_value=id_value,
                local=True
            )

        assert len(missing_methods) == 0, f'Undeclared methods! {type_name}, {missing_methods}'

        g_all_services[type_name] = ServiceInfo(
            service_name=type_name,
            methods=method_infos,
            local=True,
            clazz=clazz
        )


class ClassManager():
    def __init__(self, fields: Dict):
        self.pending_fields_ = fields

    def __call__(self, clazz):
        clazz = dataclass(clazz)
        register_class(clazz, self.pending_fields_)
        return clazz


def rpcclass(fields_or_class=None):
    if isinstance(fields_or_class, type):
        clazz = fields_or_class
        return ClassManager({})(clazz)
    else:
        fields = fields_or_class
        return ClassManager(fields)


def construct_item(type_name, args):
    global g_all_types
    if type_name.endswith('[]'):
        child_type = type_name[0: len(type_name) - 2]
        assert child_type in g_all_types
        assert isinstance(args, list)
        result = []
        for item in args:
            result.append(construct_item(child_type, item))
        return result

    assert type_name in g_all_types
    info = g_all_types[type_name]
    result = info.clazz()
    assign_values(type_name, result, args, 0)
    return result


def destroy_item(type_name, args):
    assert False


def construct_json(item):
    json_data = {}
    assign_values(type(item).__name__, item, json_data, 1)
    return json_data


def assign_values(type_name, obj_data, json_data, target):
    global g_all_types

    if type_name.endswith('[]'):
        type_name_nl = type_name[0: len(type_name) - 2]
        assert isinstance(obj_data, list)
        assert isinstance(json_data, list)

        if type_name_nl in g_all_types:
            class_info_nl = g_all_types[type_name_nl]
            assert class_info_nl
            if target == 0:
                obj_data.clear()
                for item in json_data:
                    child_data = class_info_nl.clazz()
                    assign_values(type_name_nl, child_data, item, 0)
                    obj_data.append(child_data)
            else:
                json_data.clear()
                for item in obj_data:
                    child_data = {}
                    assign_values(type_name_nl, item, child_data, 1)
                    json_data.append(child_data)

        else:
            assert type_name_nl in ['int', 'float', 'bool', 'str'], \
                f'Mismatch array type: {type_name_nl}'

            if target == 0:
                obj_data.clear()
                obj_data.extend(json_data)
            else:
                json_data.clear()
                json_data.extend(obj_data)
        return

    assert type_name in g_all_types
    class_info = g_all_types[type_name]

    if type_name == DYNAMIC_OBJECT:
        if target == 0:
            for key, value in json_data.items():
                obj_data[key] = value
        else:
            for key, value in obj_data.items():
                json_data[key] = value
        return

    for item in class_info.fields.values():
        if target == 0 and item.field_name not in json_data:
            # keep default
            pass

        elif not item.local:
            # skip
            pass

        elif item.field_type.endswith('[]'):
            if target == 0:
                if obj_data.__dict__[item.field_name] is None:
                    obj_data.__dict__[item.field_name] = []
                child_data = obj_data.__dict__[item.field_name]
                assign_values(item.field_type, child_data, json_data[item.field_name], 0)
            else:
                child_data = obj_data.__dict__[item.field_name]
                if child_data:
                    json_data[item.field_name] = []
                    assign_values(item.field_type, child_data, json_data[item.field_name], 1)

        elif item.field_type in g_all_types:
            child_type = g_all_types[item.field_type]
            assert item.field_name in obj_data.__dict__
            if target == 0 and obj_data.__dict__[item.field_name] is None:
                obj_data.__dict__[item.field_name] = child_type.clazz()
            if target == 1 and obj_data.__dict__[item.field_name] is None:
                continue
            child_data = obj_data.__dict__[item.field_name]
            if target == 0:
                assign_values(item.field_type, child_data, json_data[item.field_name], 0)
            else:
                json_data[item.field_name] = {}
                assign_values(item.field_type, child_data, json_data[item.field_name], 1)

        elif item.field_type == 'int' or \
                item.field_type == 'float' or \
                item.field_type == 'dict' or \
                item.field_type == 'list' or \
                item.field_type == 'bool' or \
                item.field_type == 'str':

            if target == 0:
                obj_data.__dict__[item.field_name] = json_data[item.field_name]
            else:
                json_data[item.field_name] = obj_data.__dict__[item.field_name]

            value = json_data[item.field_name]
            if item.field_type == 'dict':
                assert isinstance(value, dict)
            elif item.field_type == 'list':
                assert isinstance(value, list)
            elif item.field_type == 'str':
                assert isinstance(value, str), f'Mismatch value type: {item.field_name}, str, {type(value)}, {value}'
            elif item.field_type == 'int':
                assert isinstance(value, int)
            elif item.field_type == 'float':
                # TODO: disallow int
                assert isinstance(value, float) or isinstance(value, int), f'Invalid float type: {type(value)}'
            elif item.field_type == 'bool':
                assert isinstance(value, bool)

        else:
            assert False, f'Unknown field type: {item.field_type}, {item.field_name}, {class_info.type_name}'


def get_class_string(type_name, obj_data):
    global g_all_types
    if type_name.endswith('[]'):
        result = '['
        child_type = type_name[0: len(type_name) - 2]
        assert child_type in g_all_types
        assert isinstance(obj_data, list)
        for item in obj_data:
            if len(result) > 30:
                result += '...'
                break
            result += f'{get_class_string(child_type, item)}, '

        if result.endswith(', '):
            result = result[0: len(result) - 2]

        result += ']'
        return result

    assert type_name in g_all_types
    info = g_all_types[type_name]
    result = f'{type_name}('

    for key, field_info in info.fields.items():
        if len(result) > 30:
            result += '...'
            break

        value = getattr(obj_data, key)

        if field_info.field_type in g_all_types:
            result += f'{get_class_string(field_info.field_type, value)}, '

        elif field_info.field_type == 'string':
            result += f"'{value}', "
        else:
            result += f'{value}, '

    if result.endswith(', '):
        result = result[0: len(result) - 2]

    result += ')'
    return result


def get_simple_type(item):
    """Converts 'list[X]' into 'X[]'."""
    if item.__name__ == 'list' and \
            len(get_args(item)) == 1:
        return f'{get_args(item)[0].__name__}[]'
    else:
        return item.__name__


def init():
    """Initialize NPRC library"""
    pass


class CommandLine(Dict[str, any]):
    def __init__(self, fields: Dict[str, any]):
        for name, value in fields.items():
            self[name] = value

        cmd_line = sys.argv
        for item in cmd_line[1:]:
            if '=' not in item or item.startswith('-'):
                continue
            key = item[0: item.index('=')]
            value = item[item.index('=') + 1:]
            field_type = type(fields[key]).__name__ if key in fields else None
            if field_type == 'int':
                value = int(value)
            elif field_type == 'float':
                value = float(value)
            elif field_type == 'bool':
                value = value in ['1', 'true', 'True']
            assert key in fields, f'Unknown command line field: {key}'
            self[key] = value

        for item in cmd_line[1:]:
            if not item.startswith('--'):
                continue
            key = item[2:]
            value = True
            assert key in fields, f'Unknown command line field: {key}'
            field_type = type(fields[key]).__name__ if key in fields else None
            assert field_type == 'bool'
            self[key] = value

    def as_string(self, delim=' '):
        parts = []
        for key, value in self.items():
            parts.append(f'{key}={value}')
        return delim.join(parts)


def is_number(text):
    try:
        int(text)
        return True
    except Exception:
        pass
    return False


def find(iterable, function):
    for item in iterable:
        if function(item):
            return item
    return None


def find_all(iterable, function):
    result = []
    for item in iterable:
        if function(item):
            result.append(item)
    return result


def check_serializable(data):
    try:
        json.dumps(data)
    except:  # noqa
        print(f'Cannot serialize: {type(data)}, {data}')
        raise


def ctrl_handler():
    pass


if os.name == 'nt':
    import ctypes
    CTRL_C_EVENT = 0
    # ctypes.windll.kernel32.SetConsoleCtrlHandler(None, False)

    @ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_ulong)
    def _ctrl_handler(event):
        if event == CTRL_C_EVENT:
            print('Keyboard exit')
            os._exit(0)
            return 1
        return 0
    ctypes.windll.kernel32.SetConsoleCtrlHandler(_ctrl_handler, True)
