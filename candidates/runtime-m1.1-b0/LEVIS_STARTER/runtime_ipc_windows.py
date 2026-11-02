"""M1.1 native Win32 boundary. Windows only; no fixture/fallback transport.

Single-instance byte pipes retain their first-instance handles until shutdown.
Client rights deliberately exclude FILE_CREATE_PIPE_INSTANCE. A second reserved
control pipe keeps lifecycle commands independent of a stalled data client.
"""
import ctypes as C
from ctypes import wintypes as W
import hashlib
import os
from pathlib import Path
import time

if os.name != 'nt':
    raise RuntimeError('M1.1 requires native Windows')

K = C.WinDLL('kernel32', use_last_error=True)
A = C.WinDLL('advapi32', use_last_error=True)
D = C.WinDLL('crypt32', use_last_error=True)
P = C.c_void_p
INVALID = C.c_void_p(-1).value
CLIENT_RIGHTS = 0x12019b  # Individual pipe rights; excludes append/create-instance.


def bind(lib, name, args, result=W.BOOL):
    f = getattr(lib, name)
    f.argtypes, f.restype = args, result
    return f


close = bind(K, 'CloseHandle', [W.HANDLE])
local_free = bind(K, 'LocalFree', [P], P)
get_process = bind(K, 'GetCurrentProcess', [], W.HANDLE)
open_process = bind(K, 'OpenProcess', [W.DWORD, W.BOOL, W.DWORD], W.HANDLE)
open_token = bind(A, 'OpenProcessToken', [W.HANDLE, W.DWORD, P])
open_thread_token = bind(A, 'OpenThreadToken', [W.HANDLE, W.DWORD, W.BOOL, P])
get_thread = bind(K, 'GetCurrentThread', [], W.HANDLE)
token_info = bind(A, 'GetTokenInformation', [W.HANDLE, W.DWORD, P, W.DWORD, P])
sid_string = bind(A, 'ConvertSidToStringSidW', [P, P])
sddl_sd = bind(A, 'ConvertStringSecurityDescriptorToSecurityDescriptorW', [W.LPCWSTR, W.DWORD, P, P])
set_security = bind(A, 'SetFileSecurityW', [W.LPCWSTR, W.DWORD, P])
create_file = bind(K, 'CreateFileW', [W.LPCWSTR, W.DWORD, W.DWORD, P, W.DWORD, W.DWORD, W.HANDLE], W.HANDLE)
create_pipe = bind(K, 'CreateNamedPipeW', [W.LPCWSTR, W.DWORD, W.DWORD, W.DWORD, W.DWORD, W.DWORD, W.DWORD, P], W.HANDLE)
connect_pipe = bind(K, 'ConnectNamedPipe', [W.HANDLE, P])
disconnect_pipe = bind(K, 'DisconnectNamedPipe', [W.HANDLE])
set_pipe_mode = bind(K, 'SetNamedPipeHandleState', [W.HANDLE, P, P, P])
read_file = bind(K, 'ReadFile', [W.HANDLE, P, W.DWORD, P, P])
write_file = bind(K, 'WriteFile', [W.HANDLE, P, W.DWORD, P, P])
server_pid = bind(K, 'GetNamedPipeServerProcessId', [W.HANDLE, P])
client_pid = bind(K, 'GetNamedPipeClientProcessId', [W.HANDLE, P])
impersonate = bind(A, 'ImpersonateNamedPipeClient', [W.HANDLE])
revert = bind(A, 'RevertToSelf', [])
drive_type = bind(K, 'GetDriveTypeW', [W.LPCWSTR], W.UINT)
attributes = bind(K, 'GetFileAttributesW', [W.LPCWSTR], W.DWORD)
get_security = bind(A, 'GetFileSecurityW', [W.LPCWSTR, W.DWORD, P, W.DWORD, P])
get_dacl = bind(A, 'GetSecurityDescriptorDacl', [P, P, P, P])
get_control = bind(A, 'GetSecurityDescriptorControl', [P, P, P])
get_ace = bind(A, 'GetAce', [P, W.DWORD, P])


def check(value):
    if not value:
        raise C.WinError(C.get_last_error())
    return value


def handle(value):
    if value is None or value == INVALID:
        raise C.WinError(C.get_last_error())
    return value


class SID_ATTR(C.Structure):
    _fields_ = [('sid', P), ('attributes', W.DWORD)]


class GROUPS(C.Structure):
    _fields_ = [('count', W.DWORD), ('groups', SID_ATTR * 1)]


class SA(C.Structure):
    _fields_ = [('length', W.DWORD), ('descriptor', P), ('inherit', W.BOOL)]


class BLOB(C.Structure):
    _fields_ = [('length', W.DWORD), ('data', P)]


protect = bind(D, 'CryptProtectData', [P, W.LPCWSTR, P, P, P, W.DWORD, P])
unprotect = bind(D, 'CryptUnprotectData', [P, P, P, P, P, W.DWORD, P])


def sid_text(sid):
    ptr = P()
    check(sid_string(sid, C.byref(ptr)))
    try:
        return C.wstring_at(ptr)
    finally:
        local_free(ptr)


def info(token, kind):
    size = W.DWORD()
    token_info(token, kind, None, 0, C.byref(size))
    if not 0 < size.value < 1024 * 1024:
        raise RuntimeError('Invalid token information size')
    buf = C.create_string_buffer(size.value)
    check(token_info(token, kind, buf, size, C.byref(size)))
    return buf


def identity(token):
    user = info(token, 1)
    groups = info(token, 2)
    header = C.cast(groups, C.POINTER(GROUPS)).contents
    array = (SID_ATTR * header.count).from_buffer(groups, GROUPS.groups.offset)
    logons = [sid_text(g.sid) for g in array if g.attributes & 0xc0000000 == 0xc0000000]
    if len(logons) != 1:
        raise RuntimeError('Exactly one logon SID required')
    elevated = C.cast(info(token, 20), C.POINTER(W.DWORD)).contents.value
    if elevated:
        raise PermissionError('Elevated coordinator/client is refused')
    return {'user': sid_text(C.cast(user, C.POINTER(SID_ATTR)).contents.sid), 'logon': logons[0]}


def process_identity(pid=None):
    process = get_process() if pid is None else handle(open_process(0x1000, False, pid))
    token = W.HANDLE()
    try:
        check(open_token(process, 8, C.byref(token)))
        if C.cast(info(token, 29), C.POINTER(W.DWORD)).contents.value:
            raise PermissionError('AppContainer token unsupported; use a normal non-elevated Windows terminal')
        return identity(token)
    finally:
        if token.value:
            close(token)
        if pid is not None:
            close(process)


def peer_identity(pipe, server, expected, expected_pid=None):
    pid = W.DWORD()
    check((client_pid if server else server_pid)(pipe, C.byref(pid)))
    if expected_pid is not None and pid.value != expected_pid:
        raise PermissionError('Server PID differs from discovery')
    if process_identity(pid.value) != expected:
        raise PermissionError('Peer user/logon identity mismatch')
    if server:
        check(impersonate(pipe))
        token = W.HANDLE()
        try:
            check(open_thread_token(get_thread(), 8, True, C.byref(token)))
            if identity(token) != expected:
                raise PermissionError('Effective client token mismatch')
        finally:
            if token.value:
                close(token)
            # Failure to revert is fatal to this process, never continue as peer.
            if not revert():
                os._exit(75)
    return pid.value


class Security:
    def __init__(self, sddl):
        self.ptr = P()
        check(sddl_sd(sddl, 1, C.byref(self.ptr), None))
        self.sa = SA(C.sizeof(SA), self.ptr, False)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        local_free(self.ptr)


def profile_sddl(who):
    return f"D:P(A;OICI;FA;;;{who['user']})(A;OICI;FA;;;SY)"


def private_path(path, who):
    with Security(profile_sddl(who)) as security:
        check(set_security(str(path), 0x80000004, security.ptr))


def verify_private(path, who, protected=False):
    size = W.DWORD()
    get_security(str(path), 4, None, 0, C.byref(size))
    if not 0 < size.value <= 65536:
        raise PermissionError('Invalid security descriptor size')
    buf = C.create_string_buffer(size.value)
    check(get_security(str(path), 4, buf, size, C.byref(size)))
    control, revision = W.WORD(), W.DWORD()
    check(get_control(buf, C.byref(control), C.byref(revision)))
    if protected and not control.value & 0x1000:
        raise PermissionError('Profile DACL must be protected')
    present, defaulted, acl = W.BOOL(), W.BOOL(), P()
    check(get_dacl(buf, C.byref(present), C.byref(acl), C.byref(defaulted)))
    if not present.value or not acl.value:
        raise PermissionError('Null/missing DACL refused')
    count = C.c_ushort.from_address(acl.value + 4).value
    allowed = {who['user'], 'S-1-5-18'}
    found = set()
    for i in range(count):
        ace = P();check(get_ace(acl, i, C.byref(ace)))
        if C.c_ubyte.from_address(ace.value).value != 0:
            raise PermissionError('Unexpected ACE type')
        sid = sid_text(ace.value + 8)
        mask = W.DWORD.from_address(ace.value + 4).value
        if sid not in allowed or mask != 0x1f01ff:
            raise PermissionError('Unexpected profile access grant')
        found.add(sid)
    if found != allowed:
        raise PermissionError('Profile ACL incomplete')


def canonical_profile(path):
    p = Path(os.path.abspath(path))
    if str(p).startswith('\\\\') or drive_type(p.anchor) != 3:
        raise ValueError('Profile must be on a local fixed drive')
    for part in reversed([p, *p.parents]):
        a = attributes(str(part))
        if a != 0xffffffff and a & 0x400:
            raise ValueError('Reparse-point profile/ancestor refused')
    return p


def dpapi(data, decrypt=False):
    source = C.create_string_buffer(data)
    src, dst = BLOB(len(data), C.cast(source, P)), BLOB()
    if decrypt:
        check(unprotect(C.byref(src), None, None, None, None, 1, C.byref(dst)))
    else:
        check(protect(C.byref(src), 'LEVIS M1.1 profile', None, None, None, 1, C.byref(dst)))
    try:
        return C.string_at(dst.data, dst.length)
    finally:
        local_free(dst.data)


class ProfileLock:
    def __init__(self, profile):
        # No share-read/write/delete. Lock file is never removed/replaced.
        self.h = handle(create_file(str(profile / 'writer.lock'), 0xc0000000, 0, None, 4, 0x80, None))

    def close(self):
        if self.h is not None:
            close(self.h)
            self.h = None


def pipe_name(profile, who, control=False):
    key = (str(profile).casefold() + who['user'] + who['logon']).encode()
    suffix = '-control' if control else '-data'
    return '\\\\.\\pipe\\LEVIS-M11-' + hashlib.sha256(key).hexdigest()[:40] + suffix


def new_pipe(name, who):
    # Logon-only client DACL; process-token checks additionally require user SID.
    with Security(f"D:P(A;;0x{CLIENT_RIGHTS:08x};;;{who['logon']})") as security:
        return handle(create_pipe(name, 3 | 0x80000, 1 | 8, 1, 65536, 65536, 1000, C.byref(security.sa)))


def open_pipe(name, timeout=5):
    end = time.monotonic() + timeout
    while True:
        h = create_file(name, CLIENT_RIGHTS, 0, None, 3, 0x110000, None)
        if h is not None and h != INVALID:
            mode = W.DWORD(1)
            try:
                check(set_pipe_mode(h, C.byref(mode), None, None))
                return h
            except BaseException:
                close(h)
                raise
        error = C.get_last_error()
        if error not in (2, 231) or time.monotonic() > end:
            raise C.WinError(error)
        time.sleep(.01)


def accept(h, stopping):
    while not stopping.is_set():
        if connect_pipe(h, None):
            return True
        error = C.get_last_error()
        if error == 535:
            return True
        if error not in (536, 232):
            raise C.WinError(error)
        if error == 232:
            disconnect_pipe(h)
        time.sleep(.01)
    return False


def read_exact(h, size, deadline):
    result = bytearray()
    while len(result) < size:
        buf = C.create_string_buffer(min(65536, size - len(result)))
        count = W.DWORD()
        ok = read_file(h, buf, len(buf), C.byref(count), None)
        if not ok and C.get_last_error() != 232:
            raise C.WinError(C.get_last_error())
        if count.value:
            result.extend(buf.raw[:count.value])
        else:
            time.sleep(.005)
        if time.monotonic() > deadline:
            raise TimeoutError('Pipe read deadline')
    return bytes(result)


def write_all(h, data, deadline):
    pos = 0
    while pos < len(data):
        chunk = data[pos:pos+16384]
        buf, count = C.create_string_buffer(chunk), W.DWORD()
        check(write_file(h, buf, len(chunk), C.byref(count), None))
        pos += count.value
        if not count.value:
            time.sleep(.005)
        if time.monotonic() > deadline:
            raise TimeoutError('Pipe write deadline')
