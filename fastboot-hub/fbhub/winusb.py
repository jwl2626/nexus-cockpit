"""Minimal, dependency-free WinUSB access for USB devices on Windows.

The module wraps the small part of SetupAPI / WinUSB / CfgMgr32 that a
fastboot client needs:

* enumerate every present USB device interface
* read the USB device/interface descriptors
* resolve the physical USB topology (``USBROOT(0)#USB(1)#USB(3)``)
* read and write bulk endpoints with timeouts

Only the standard Windows DLLs are used, so the tool runs on a stock
python.org installation without pip packages.
"""

from __future__ import annotations

import ctypes
import re
import uuid
from ctypes import wintypes
from dataclasses import dataclass
from typing import Iterator, Optional

# ---------------------------------------------------------------------------
# DLLs and constants
# ---------------------------------------------------------------------------

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
_winusb = ctypes.WinDLL("winusb", use_last_error=True)
_cfgmgr32 = ctypes.WinDLL("cfgmgr32", use_last_error=True)

GUID_DEVINTERFACE_USB_DEVICE = "{A5DCBF10-6530-11D2-901F-00C04FB951ED}"
# Android's android_winusb.inf registers its bootloader interfaces under this
# class/interface GUID.  Enumerating it as well as the generic USB device GUID
# makes composite devices (where the fastboot function is a child device node)
# visible.
GUID_ANDROID_USB = "{F72FE0D4-CBCB-407d-8814-9ED673D0DD6B}"

DIGCF_PRESENT = 0x00000002
DIGCF_DEVICEINTERFACE = 0x00000010

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x00000080
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

ERROR_INSUFFICIENT_BUFFER = 122
ERROR_NO_MORE_ITEMS = 259
ERROR_SEM_TIMEOUT = 121
ERROR_OPERATION_ABORTED = 995
ERROR_ACCESS_DENIED = 5
ERROR_INVALID_HANDLE = 6
ERROR_NOT_FOUND = 1168
ERROR_GEN_FAILURE = 31

CR_SUCCESS = 0
CR_BUFFER_SMALL = 26
DEVPROP_TYPE_STRING = 0x12
DEVPROP_TYPE_STRING_LIST = 0x2012

USB_DEVICE_DESCRIPTOR_TYPE = 1
USB_STRING_DESCRIPTOR_TYPE = 3

PIPE_TRANSFER_TIMEOUT = 0x03
USB_ENDPOINT_TYPE_BULK = 2

# DEVPKEY_Device_LocationPaths / DEVPKEY_Device_LocationInfo
_LOCATION_PATHS_KEY = ("A45C254E-DF1C-4EFD-8020-67D146A850E0", 37)
_LOCATION_INFO_KEY = ("A45C254E-DF1C-4EFD-8020-67D146A850E0", 15)


# ---------------------------------------------------------------------------
# ctypes structures
# ---------------------------------------------------------------------------

class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    def __init__(self, text: str):
        super().__init__()
        value = uuid.UUID(text)
        self.Data1 = value.time_low
        self.Data2 = value.time_mid
        self.Data3 = value.time_hi_version
        for index, byte in enumerate(value.bytes[8:]):
            self.Data4[index] = byte


class DEVPROPKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", wintypes.ULONG)]

    def __init__(self, guid_text: str, pid: int):
        super().__init__()
        self.fmtid = GUID(guid_text)
        self.pid = pid


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("InterfaceClassGuid", GUID),
        ("Flags", wintypes.DWORD),
        ("Reserved", ctypes.c_void_p),
    ]


class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("ClassGuid", GUID),
        ("DevInst", wintypes.DWORD),
        ("Reserved", ctypes.c_void_p),
    ]


class SP_DEVICE_INTERFACE_DETAIL_DATA_W(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("DevicePath", wintypes.WCHAR * 1),
    ]


class USB_DEVICE_DESCRIPTOR(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("bLength", ctypes.c_ubyte),
        ("bDescriptorType", ctypes.c_ubyte),
        ("bcdUSB", ctypes.c_ushort),
        ("bDeviceClass", ctypes.c_ubyte),
        ("bDeviceSubClass", ctypes.c_ubyte),
        ("bDeviceProtocol", ctypes.c_ubyte),
        ("bMaxPacketSize0", ctypes.c_ubyte),
        ("idVendor", ctypes.c_ushort),
        ("idProduct", ctypes.c_ushort),
        ("bcdDevice", ctypes.c_ushort),
        ("iManufacturer", ctypes.c_ubyte),
        ("iProduct", ctypes.c_ubyte),
        ("iSerialNumber", ctypes.c_ubyte),
        ("bNumConfigurations", ctypes.c_ubyte),
    ]


class USB_INTERFACE_DESCRIPTOR(ctypes.Structure):
    _fields_ = [
        ("bLength", ctypes.c_ubyte),
        ("bDescriptorType", ctypes.c_ubyte),
        ("bInterfaceNumber", ctypes.c_ubyte),
        ("bAlternateSetting", ctypes.c_ubyte),
        ("bNumEndpoints", ctypes.c_ubyte),
        ("bInterfaceClass", ctypes.c_ubyte),
        ("bInterfaceSubClass", ctypes.c_ubyte),
        ("bInterfaceProtocol", ctypes.c_ubyte),
        ("iInterface", ctypes.c_ubyte),
    ]


class WINUSB_PIPE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PipeType", ctypes.c_int),
        ("PipeId", ctypes.c_ubyte),
        ("MaximumPacketSize", ctypes.c_ushort),
        ("Interval", ctypes.c_ubyte),
    ]


# ---------------------------------------------------------------------------
# Function prototypes
# ---------------------------------------------------------------------------

_kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    ctypes.c_void_p,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HANDLE,
]
_kernel32.CreateFileW.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL

_setupapi.SetupDiGetClassDevsW.argtypes = [
    ctypes.POINTER(GUID),
    wintypes.LPCWSTR,
    wintypes.HWND,
    wintypes.DWORD,
]
_setupapi.SetupDiGetClassDevsW.restype = wintypes.HANDLE

_setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(SP_DEVINFO_DATA),
    ctypes.POINTER(GUID),
    wintypes.DWORD,
    ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
]
_setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL

_setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(SP_DEVINFO_DATA),
]
_setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL

_setupapi.SetupDiGetDeviceInstanceIdW.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(SP_DEVINFO_DATA),
    wintypes.LPWSTR,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
]
_setupapi.SetupDiGetDeviceInstanceIdW.restype = wintypes.BOOL

_setupapi.SetupDiDestroyDeviceInfoList.argtypes = [wintypes.HANDLE]
_setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL

_winusb.WinUsb_Initialize.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
_winusb.WinUsb_Initialize.restype = wintypes.BOOL
_winusb.WinUsb_Free.argtypes = [ctypes.c_void_p]
_winusb.WinUsb_Free.restype = wintypes.BOOL
_winusb.WinUsb_QueryInterfaceSettings.argtypes = [
    ctypes.c_void_p,
    ctypes.c_ubyte,
    ctypes.POINTER(USB_INTERFACE_DESCRIPTOR),
]
_winusb.WinUsb_QueryInterfaceSettings.restype = wintypes.BOOL
_winusb.WinUsb_QueryPipe.argtypes = [
    ctypes.c_void_p,
    ctypes.c_ubyte,
    ctypes.c_ubyte,
    ctypes.POINTER(WINUSB_PIPE_INFORMATION),
]
_winusb.WinUsb_QueryPipe.restype = wintypes.BOOL
_winusb.WinUsb_GetDescriptor.argtypes = [
    ctypes.c_void_p,
    ctypes.c_ubyte,
    ctypes.c_ubyte,
    ctypes.c_ushort,
    ctypes.POINTER(ctypes.c_ubyte),
    wintypes.ULONG,
    ctypes.POINTER(wintypes.ULONG),
]
_winusb.WinUsb_GetDescriptor.restype = wintypes.BOOL
_winusb.WinUsb_ReadPipe.argtypes = [
    ctypes.c_void_p,
    ctypes.c_ubyte,
    ctypes.POINTER(ctypes.c_ubyte),
    wintypes.ULONG,
    ctypes.POINTER(wintypes.ULONG),
    ctypes.c_void_p,
]
_winusb.WinUsb_ReadPipe.restype = wintypes.BOOL
_winusb.WinUsb_WritePipe.argtypes = [
    ctypes.c_void_p,
    ctypes.c_ubyte,
    ctypes.POINTER(ctypes.c_ubyte),
    wintypes.ULONG,
    ctypes.POINTER(wintypes.ULONG),
    ctypes.c_void_p,
]
_winusb.WinUsb_WritePipe.restype = wintypes.BOOL
_winusb.WinUsb_SetPipePolicy.argtypes = [
    ctypes.c_void_p,
    ctypes.c_ubyte,
    wintypes.ULONG,
    wintypes.ULONG,
    ctypes.c_void_p,
]
_winusb.WinUsb_SetPipePolicy.restype = wintypes.BOOL
_winusb.WinUsb_ResetPipe.argtypes = [ctypes.c_void_p, ctypes.c_ubyte]
_winusb.WinUsb_ResetPipe.restype = wintypes.BOOL
_winusb.WinUsb_AbortPipe.argtypes = [ctypes.c_void_p, ctypes.c_ubyte]
_winusb.WinUsb_AbortPipe.restype = wintypes.BOOL

_cfgmgr32.CM_Get_DevNode_PropertyW.argtypes = [
    wintypes.ULONG,
    ctypes.POINTER(DEVPROPKEY),
    ctypes.POINTER(wintypes.ULONG),
    ctypes.POINTER(ctypes.c_ubyte),
    ctypes.POINTER(wintypes.ULONG),
    wintypes.ULONG,
]
_cfgmgr32.CM_Get_DevNode_PropertyW.restype = wintypes.ULONG


# ---------------------------------------------------------------------------
# Errors / data classes
# ---------------------------------------------------------------------------

class WinUsbError(OSError):
    """A Windows API call failed."""

    def __init__(self, operation: str, code: Optional[int] = None):
        self.operation = operation
        self.code = ctypes.get_last_error() if code is None else code
        message = _format_error(self.code)
        super().__init__(f"{operation} failed: {message} (WinError {self.code})")


class WinUsbTimeout(WinUsbError):
    pass


@dataclass(frozen=True)
class UsbInterface:
    """A present USB device interface reported by SetupAPI."""

    path: str
    instance_id: str
    devinst: int
    location_paths: tuple[str, ...]
    location: str


def _format_error(code: int) -> str:
    mapping = {
        ERROR_ACCESS_DENIED: "访问被拒绝（设备可能被其他程序占用，请关闭 fastboot/刷机工具）",
        ERROR_INVALID_HANDLE: "无效的句柄（该设备没有使用 WinUSB 驱动）",
        ERROR_NOT_FOUND: "找不到设备",
        ERROR_SEM_TIMEOUT: "USB 传输超时",
        ERROR_OPERATION_ABORTED: "USB 传输被取消",
        ERROR_GEN_FAILURE: "设备返回错误",
    }
    if code in mapping:
        return f"{mapping[code]} [WinError {code}]"
    try:
        return ctypes.FormatError(code).strip()
    except Exception:
        return f"WinError {code}"


def _last_error() -> int:
    return ctypes.get_last_error()


def _check_error(operation: str) -> None:
    code = _last_error()
    if code == ERROR_SEM_TIMEOUT:
        raise WinUsbTimeout(operation, code)
    raise WinUsbError(operation, code)


# ---------------------------------------------------------------------------
# Device tree helpers
# ---------------------------------------------------------------------------

def _parse_location_paths(paths: tuple[str, ...]) -> Optional[str]:
    """Convert a Windows location path into a stable, unique USB address.

    Example:
        ``PCIROOT(0)#PCI(1D00)#USBROOT(0)#USB(1)#USB(3)`` -> ``1D00:0-1.3``

    The PCI slot is included because a machine can have several USB host
    controllers and Windows numbers the root hubs from zero on each one.
    Without the controller prefix, two devices on different controllers could
    receive the same address.
    """
    for raw in paths:
        match = re.search(r"USBROOT\((\d+)\)", raw, re.IGNORECASE)
        if not match:
            continue
        root_hub = int(match.group(1))
        pci_slots = re.findall(r"PCI\(([0-9A-Fa-f]+)\)", raw, re.IGNORECASE)
        prefix = pci_slots[-1].upper() if pci_slots else "USB"
        ports = [int(item) for item in re.findall(r"USB\((\d+)\)", raw, re.IGNORECASE)]
        if ports:
            return f"{prefix}:{root_hub}-{'.'.join(str(port) for port in ports)}"
        return f"{prefix}:{root_hub}"
    return None


def _get_property_strings(devinst: int, key: tuple[str, int]) -> tuple[str, ...]:
    prop_key = DEVPROPKEY(key[0], key[1])
    prop_type = wintypes.ULONG()
    size = wintypes.ULONG(1024)

    for _ in range(4):
        buffer = (ctypes.c_ubyte * size.value)()
        result = _cfgmgr32.CM_Get_DevNode_PropertyW(
            devinst,
            ctypes.byref(prop_key),
            ctypes.byref(prop_type),
            buffer,
            ctypes.byref(size),
            0,
        )
        if result == CR_SUCCESS:
            raw = bytes(buffer[: size.value])
            text = raw.decode("utf-16-le", errors="ignore")
            return tuple(item for item in text.split("\x00") if item)
        if result == CR_BUFFER_SMALL:
            # ``size`` now contains the required size.
            continue
        return ()
    return ()


def _fallback_location(instance_id: str, devinst: int) -> str:
    """Best-effort stable label when LocationPaths is unavailable."""
    match = re.search(r"&([0-9a-fA-F]+)&0&(\d+)$", instance_id)
    if match:
        return f"loc-{match.group(2)}-{match.group(1)[-4:]}"
    return f"devinst-{devinst}"


def _enumerate_guid(guid_text: str) -> Iterator[UsbInterface]:
    class_guid = GUID(guid_text)
    handle = _setupapi.SetupDiGetClassDevsW(
        ctypes.byref(class_guid),
        None,
        None,
        DIGCF_PRESENT | DIGCF_DEVICEINTERFACE,
    )
    if handle == INVALID_HANDLE_VALUE or not handle:
        return

    try:
        index = 0
        while True:
            interface_data = SP_DEVICE_INTERFACE_DATA()
            interface_data.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
            if not _setupapi.SetupDiEnumDeviceInterfaces(
                handle,
                None,
                ctypes.byref(class_guid),
                index,
                ctypes.byref(interface_data),
            ):
                code = _last_error()
                if code == ERROR_NO_MORE_ITEMS:
                    break
                raise WinUsbError("SetupDiEnumDeviceInterfaces", code)

            device_info = SP_DEVINFO_DATA()
            device_info.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)
            required = wintypes.DWORD()
            _setupapi.SetupDiGetDeviceInterfaceDetailW(
                handle,
                ctypes.byref(interface_data),
                None,
                0,
                ctypes.byref(required),
                ctypes.byref(device_info),
            )
            if required.value == 0:
                index += 1
                continue

            detail_buffer = ctypes.create_string_buffer(required.value)
            detail = ctypes.cast(
                detail_buffer, ctypes.POINTER(SP_DEVICE_INTERFACE_DETAIL_DATA_W)
            )
            # 32-bit Windows wants 6, 64-bit Windows wants 8.  ctypes' struct
            # size rounds up on 32-bit, so calculate it explicitly.
            detail.contents.cbSize = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
            if not _setupapi.SetupDiGetDeviceInterfaceDetailW(
                handle,
                ctypes.byref(interface_data),
                detail,
                required.value,
                None,
                ctypes.byref(device_info),
            ):
                code = _last_error()
                if code == ERROR_NO_MORE_ITEMS:
                    break
                # A single broken device must not abort the whole scan.
                index += 1
                continue

            instance_buffer = ctypes.create_unicode_buffer(512)
            instance_id = ""
            if _setupapi.SetupDiGetDeviceInstanceIdW(
                handle,
                ctypes.byref(device_info),
                instance_buffer,
                len(instance_buffer),
                None,
            ):
                instance_id = instance_buffer.value

            location_paths = _get_property_strings(device_info.DevInst, _LOCATION_PATHS_KEY)
            if not location_paths:
                location_paths = _get_property_strings(device_info.DevInst, _LOCATION_INFO_KEY)
            location = _parse_location_paths(location_paths)
            if location is None:
                location = _fallback_location(instance_id, device_info.DevInst)

            device_path = ctypes.wstring_at(ctypes.addressof(detail.contents) + 4)
            yield UsbInterface(
                path=device_path,
                instance_id=instance_id,
                devinst=device_info.DevInst,
                location_paths=location_paths,
                location=location,
            )
            index += 1
    finally:
        _setupapi.SetupDiDestroyDeviceInfoList(handle)


def enumerate_usb_interfaces() -> Iterator[UsbInterface]:
    """Yield every present USB device interface (may include non-WinUSB).

    Both the generic USB device interface GUID and Android's USB interface GUID
    are scanned, then de-duplicated by device path.
    """
    seen: set[str] = set()
    for guid_text in (GUID_DEVINTERFACE_USB_DEVICE, GUID_ANDROID_USB):
        try:
            iterator = _enumerate_guid(guid_text)
            for interface in iterator:
                if interface.path in seen:
                    continue
                seen.add(interface.path)
                yield interface
        except WinUsbError:
            # The Android GUID is missing on machines without the Android USB
            # driver; that must not hide the generic scan.
            if guid_text == GUID_DEVINTERFACE_USB_DEVICE:
                raise


# ---------------------------------------------------------------------------
# WinUSB device
# ---------------------------------------------------------------------------

def _get_descriptor(winusb_handle: ctypes.c_void_p, desc_type: int, index: int,
                    lang_id: int, length: int = 255) -> bytes:
    buffer = (ctypes.c_ubyte * length)()
    transferred = wintypes.ULONG()
    if not _winusb.WinUsb_GetDescriptor(
        winusb_handle,
        desc_type,
        index,
        lang_id,
        buffer,
        length,
        ctypes.byref(transferred),
    ):
        return b""
    return bytes(buffer[: transferred.value])


def _decode_string(raw: bytes) -> Optional[str]:
    if len(raw) < 4:
        return None
    length = min(raw[0], len(raw))
    if length < 4:
        return None
    try:
        return raw[2:length].decode("utf-16-le", errors="ignore").rstrip("\x00")
    except Exception:
        return None


class WinUsbDevice:
    """An opened USB device whose first interface is claimed by WinUSB."""

    def __init__(self, interface: UsbInterface):
        self.interface = interface
        self.handle = None
        self.winusb = ctypes.c_void_p()
        self.device_descriptor: Optional[USB_DEVICE_DESCRIPTOR] = None
        self.interface_descriptor: Optional[USB_INTERFACE_DESCRIPTOR] = None
        self.ep_in = 0
        self.ep_out = 0
        self.max_packet_in = 0
        self.max_packet_out = 0
        self._read_timeout_ms = 15000
        self._write_timeout_ms = 60000
        self.serial: Optional[str] = None
        self.product: Optional[str] = None
        self.manufacturer: Optional[str] = None
        self._open()

    # -- lifecycle ---------------------------------------------------------
    def _open(self) -> None:
        handle = _kernel32.CreateFileW(
            self.interface.path,
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            None,
        )
        if handle == INVALID_HANDLE_VALUE or not handle:
            _check_error("打开 USB 设备")
        self.handle = handle

        winusb_handle = ctypes.c_void_p()
        if not _winusb.WinUsb_Initialize(handle, ctypes.byref(winusb_handle)):
            self._close_handle()
            _check_error("WinUsb_Initialize")
        self.winusb = winusb_handle

        descriptor = USB_INTERFACE_DESCRIPTOR()
        if not _winusb.WinUsb_QueryInterfaceSettings(
            self.winusb, 0, ctypes.byref(descriptor)
        ):
            self.close()
            _check_error("WinUsb_QueryInterfaceSettings")
        self.interface_descriptor = descriptor

        for index in range(1, descriptor.bNumEndpoints + 1):
            pipe = WINUSB_PIPE_INFORMATION()
            if not _winusb.WinUsb_QueryPipe(
                self.winusb, 0, index, ctypes.byref(pipe)
            ):
                continue
            if pipe.PipeType != USB_ENDPOINT_TYPE_BULK:
                continue
            if pipe.PipeId & 0x80:
                if not self.ep_in:
                    self.ep_in = pipe.PipeId
                    self.max_packet_in = pipe.MaximumPacketSize
                    self._set_timeout(pipe.PipeId, self._read_timeout_ms)
            else:
                if not self.ep_out:
                    self.ep_out = pipe.PipeId
                    self.max_packet_out = pipe.MaximumPacketSize
                    self._set_timeout(pipe.PipeId, self._write_timeout_ms)

        raw = _get_descriptor(self.winusb, USB_DEVICE_DESCRIPTOR_TYPE, 0, 0,
                              ctypes.sizeof(USB_DEVICE_DESCRIPTOR))
        if len(raw) >= ctypes.sizeof(USB_DEVICE_DESCRIPTOR):
            parsed = USB_DEVICE_DESCRIPTOR.from_buffer_copy(raw)
            self.device_descriptor = parsed
            self.serial = self._read_string(parsed.iSerialNumber)
            self.product = self._read_string(parsed.iProduct)
            self.manufacturer = self._read_string(parsed.iManufacturer)

    def _read_string(self, index: int) -> Optional[str]:
        if not index:
            return None
        # Use the first language ID advertised by the device.
        lang_id = 0x0409
        header = _get_descriptor(self.winusb, USB_STRING_DESCRIPTOR_TYPE, 0, 0, 255)
        if len(header) >= 4 and header[1] == USB_STRING_DESCRIPTOR_TYPE:
            lang_id = int.from_bytes(header[2:4], "little")
        raw = _get_descriptor(self.winusb, USB_STRING_DESCRIPTOR_TYPE, index, lang_id, 255)
        return _decode_string(raw)

    def _set_timeout(self, pipe_id: int, milliseconds: int) -> None:
        value = wintypes.ULONG(milliseconds)
        _winusb.WinUsb_SetPipePolicy(
            self.winusb,
            pipe_id,
            PIPE_TRANSFER_TIMEOUT,
            ctypes.sizeof(value),
            ctypes.byref(value),
        )

    def _close_handle(self) -> None:
        if self.handle and self.handle != INVALID_HANDLE_VALUE:
            _kernel32.CloseHandle(self.handle)
        self.handle = None

    def close(self) -> None:
        if self.winusb:
            if self.ep_in:
                _winusb.WinUsb_AbortPipe(self.winusb, self.ep_in)
            if self.ep_out:
                _winusb.WinUsb_AbortPipe(self.winusb, self.ep_out)
            _winusb.WinUsb_Free(self.winusb)
            self.winusb = ctypes.c_void_p()
        self._close_handle()

    def __enter__(self) -> "WinUsbDevice":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # -- descriptors -------------------------------------------------------
    @property
    def is_fastboot(self) -> bool:
        desc = self.interface_descriptor
        return bool(
            desc
            and desc.bInterfaceClass == 0xFF
            and desc.bInterfaceSubClass == 0x42
            and desc.bInterfaceProtocol == 0x03
            and self.ep_in
            and self.ep_out
        )

    @property
    def vendor_id(self) -> int:
        return self.device_descriptor.idVendor if self.device_descriptor else 0

    @property
    def product_id(self) -> int:
        return self.device_descriptor.idProduct if self.device_descriptor else 0

    @property
    def display_name(self) -> str:
        name = self.product or "Android"
        return f"{name} ({self.vendor_id:04x}:{self.product_id:04x})"

    # -- I/O ---------------------------------------------------------------
    def read(self, size: int = 64, timeout_ms: Optional[int] = None) -> bytes:
        if not self.ep_in:
            raise WinUsbError("read", ERROR_INVALID_HANDLE)
        if timeout_ms is not None and timeout_ms != self._read_timeout_ms:
            self._read_timeout_ms = int(timeout_ms)
            self._set_timeout(self.ep_in, self._read_timeout_ms)
        buffer = (ctypes.c_ubyte * size)()
        transferred = wintypes.ULONG()
        ok = _winusb.WinUsb_ReadPipe(
            self.winusb,
            self.ep_in,
            buffer,
            size,
            ctypes.byref(transferred),
            None,
        )
        if not ok:
            code = _last_error()
            _winusb.WinUsb_ResetPipe(self.winusb, self.ep_in)
            if code == ERROR_SEM_TIMEOUT:
                raise WinUsbTimeout("WinUsb_ReadPipe", code)
            raise WinUsbError("WinUsb_ReadPipe", code)
        if transferred.value == 0:
            raise WinUsbError("WinUsb_ReadPipe", ERROR_GEN_FAILURE)
        return bytes(buffer[: transferred.value])

    def write(self, data: bytes) -> int:
        if not self.ep_out:
            raise WinUsbError("write", ERROR_INVALID_HANDLE)
        total = 0
        while total < len(data):
            chunk = data[total:]
            buffer = (ctypes.c_ubyte * len(chunk)).from_buffer_copy(chunk)
            transferred = wintypes.ULONG()
            ok = _winusb.WinUsb_WritePipe(
                self.winusb,
                self.ep_out,
                buffer,
                len(chunk),
                ctypes.byref(transferred),
                None,
            )
            if not ok:
                code = _last_error()
                _winusb.WinUsb_ResetPipe(self.winusb, self.ep_out)
                if code == ERROR_SEM_TIMEOUT:
                    raise WinUsbTimeout("WinUsb_WritePipe", code)
                raise WinUsbError("WinUsb_WritePipe", code)
            if transferred.value == 0:
                raise WinUsbError("WinUsb_WritePipe", ERROR_GEN_FAILURE)
            total += transferred.value
        return total


def probe_fastboot_devices() -> list[WinUsbDevice]:
    """Open every WinUSB device and keep the fastboot ones.

    Caller owns the returned devices and must close them.
    """
    result: list[WinUsbDevice] = []
    for interface in enumerate_usb_interfaces():
        try:
            device = WinUsbDevice(interface)
        except (WinUsbError, OSError):
            continue
        if device.is_fastboot:
            result.append(device)
        else:
            device.close()
    return result


if __name__ == "__main__":
    for item in enumerate_usb_interfaces():
        print(item.location, item.instance_id, item.path)
