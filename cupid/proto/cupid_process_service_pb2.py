# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: cupid/proto/cupid_process_service.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
from google.protobuf import service as _service
from google.protobuf import service_reflection
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor.FileDescriptor(
  name='cupid/proto/cupid_process_service.proto',
  package='apsara.odps.cupid.protocol',
  syntax='proto2',
  serialized_options=_b('B\030CupidProcessServiceProto\200\001\001\210\001\001\220\001\001'),
  serialized_pb=_b('\n\'cupid/proto/cupid_process_service.proto\x12\x1a\x61psara.odps.cupid.protocol\"\'\n\x08\x45nvEntry\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\r\n\x05value\x18\x02 \x01(\t\"A\n\x08\x43hildEnv\x12\x35\n\x07\x65ntries\x18\x01 \x03(\x0b\x32$.apsara.odps.cupid.protocol.EnvEntry2g\n\x0eProcessService\x12U\n\x07Prepare\x12$.apsara.odps.cupid.protocol.ChildEnv\x1a$.apsara.odps.cupid.protocol.ChildEnvB#B\x18\x43upidProcessServiceProto\x80\x01\x01\x88\x01\x01\x90\x01\x01')
)




_ENVENTRY = _descriptor.Descriptor(
  name='EnvEntry',
  full_name='apsara.odps.cupid.protocol.EnvEntry',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='name', full_name='apsara.odps.cupid.protocol.EnvEntry.name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='value', full_name='apsara.odps.cupid.protocol.EnvEntry.value', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto2',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=71,
  serialized_end=110,
)


_CHILDENV = _descriptor.Descriptor(
  name='ChildEnv',
  full_name='apsara.odps.cupid.protocol.ChildEnv',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='entries', full_name='apsara.odps.cupid.protocol.ChildEnv.entries', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto2',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=112,
  serialized_end=177,
)

_CHILDENV.fields_by_name['entries'].message_type = _ENVENTRY
DESCRIPTOR.message_types_by_name['EnvEntry'] = _ENVENTRY
DESCRIPTOR.message_types_by_name['ChildEnv'] = _CHILDENV
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

EnvEntry = _reflection.GeneratedProtocolMessageType('EnvEntry', (_message.Message,), dict(
  DESCRIPTOR = _ENVENTRY,
  __module__ = 'cupid.proto.cupid_process_service_pb2'
  # @@protoc_insertion_point(class_scope:apsara.odps.cupid.protocol.EnvEntry)
  ))
_sym_db.RegisterMessage(EnvEntry)

ChildEnv = _reflection.GeneratedProtocolMessageType('ChildEnv', (_message.Message,), dict(
  DESCRIPTOR = _CHILDENV,
  __module__ = 'cupid.proto.cupid_process_service_pb2'
  # @@protoc_insertion_point(class_scope:apsara.odps.cupid.protocol.ChildEnv)
  ))
_sym_db.RegisterMessage(ChildEnv)


DESCRIPTOR._options = None

_PROCESSSERVICE = _descriptor.ServiceDescriptor(
  name='ProcessService',
  full_name='apsara.odps.cupid.protocol.ProcessService',
  file=DESCRIPTOR,
  index=0,
  serialized_options=None,
  serialized_start=179,
  serialized_end=282,
  methods=[
  _descriptor.MethodDescriptor(
    name='Prepare',
    full_name='apsara.odps.cupid.protocol.ProcessService.Prepare',
    index=0,
    containing_service=None,
    input_type=_CHILDENV,
    output_type=_CHILDENV,
    serialized_options=None,
  ),
])
_sym_db.RegisterServiceDescriptor(_PROCESSSERVICE)

DESCRIPTOR.services_by_name['ProcessService'] = _PROCESSSERVICE

ProcessService = service_reflection.GeneratedServiceType('ProcessService', (_service.Service,), dict(
  DESCRIPTOR = _PROCESSSERVICE,
  __module__ = 'cupid.proto.cupid_process_service_pb2'
  ))

ProcessService_Stub = service_reflection.GeneratedServiceStubType('ProcessService_Stub', (ProcessService,), dict(
  DESCRIPTOR = _PROCESSSERVICE,
  __module__ = 'cupid.proto.cupid_process_service_pb2'
  ))


# @@protoc_insertion_point(module_scope)
