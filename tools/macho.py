"""Inspect Mach-O metadata without mapping or executing guest code."""
import struct


class MachOError(ValueError):
    """A file is not Mach-O or its metadata is malformed."""


THIN = {
    b'\xcf\xfa\xed\xfe': ('<', 64), b'\xfe\xed\xfa\xcf': ('>', 64),
    b'\xce\xfa\xed\xfe': ('<', 32), b'\xfe\xed\xfa\xce': ('>', 32),
}
FAT = {
    b'\xca\xfe\xba\xbe': ('>', False), b'\xbe\xba\xfe\xca': ('<', False),
    b'\xca\xfe\xba\xbf': ('>', True), b'\xbf\xba\xfe\xca': ('<', True),
}
MAGICS = set(THIN) | set(FAT)
CPUS = {7: 'i386', 0x01000007: 'x86_64', 12: 'arm', 0x0100000c: 'arm64', 18: 'ppc', 0x01000012: 'ppc64'}
DYLIBS = {0xc: 'load', 0x80000018: 'weak', 0x8000001f: 'reexport', 0x80000023: 'upward', 0x20: 'lazy'}


def _unpack(fmt, data, offset=0):
    if offset < 0 or offset + struct.calcsize(fmt) > len(data):
        raise MachOError('truncated structure')
    return struct.unpack_from(fmt, data, offset)


def _name(value):
    return value.split(b'\0', 1)[0].decode('utf-8', errors='replace')


def _version(value):
    return f'{value >> 16}.{(value >> 8) & 255}.{value & 255}'


def _string(command, offset, minimum):
    if not minimum <= offset < len(command):
        raise MachOError('invalid load command string offset')
    end = command.find(b'\0', offset)
    if end < 0:
        raise MachOError('unterminated load command string')
    return command[offset:end].decode('utf-8', errors='replace')


def _thin(data):
    if data[:4] not in THIN:
        raise MachOError('invalid Mach-O slice magic')
    endian, bits = THIN[data[:4]]
    header_size = 32 if bits == 64 else 28
    header = _unpack(endian + ('8I' if bits == 64 else '7I'), data)
    _, cpu, subtype, filetype, ncmds, size, flags = header[:7]
    if size > len(data) - header_size or ncmds > size // 8:
        raise MachOError('load commands exceed file bounds')
    result = dict(architecture=CPUS.get(cpu, hex(cpu)), cpu_type=cpu, cpu_subtype=subtype,
                  bits=bits, file_type=filetype, flags=hex(flags), minimum_os=None, sdk=None,
                  dependencies=[], rpaths=[], segments=[], objc_sections=[], entrypoint=None,
                  dylinker=None, code_signature=False, encrypted=False, chained_fixups=False,
                  load_commands=[])
    offset, end = header_size, header_size + size
    for _ in range(ncmds):
        cmd, cmdsize = _unpack(endian + 'II', data, offset)
        if cmdsize < 8 or cmdsize % (8 if bits == 64 else 4) or cmdsize > end - offset:
            raise MachOError('invalid load command size')
        c = data[offset:offset + cmdsize]
        result['load_commands'].append({'command': hex(cmd), 'size': cmdsize})
        if cmd in DYLIBS:
            name_offset, _, current, compatibility = _unpack(endian + '4I', c, 8)
            result['dependencies'].append(dict(name=_string(c, name_offset, 24), kind=DYLIBS[cmd],
                                                current_version=_version(current), compatibility_version=_version(compatibility)))
        elif cmd in (0x8000001c, 0xe):
            name_offset, = _unpack(endian + 'I', c, 8)
            name = _string(c, name_offset, 12)
            if cmd == 0xe:
                result['dylinker'] = name
            else:
                result['rpaths'].append(name)
        elif cmd == 0x24:
            minimum, sdk = _unpack(endian + 'II', c, 8)
            result.update(minimum_os=_version(minimum), sdk=_version(sdk))
        elif cmd == 0x32:
            platform, minimum, sdk, tools = _unpack(endian + '4I', c, 8)
            if 24 + tools * 8 > len(c):
                raise MachOError('truncated build tool list')
            result.update(platform=platform, minimum_os=_version(minimum), sdk=_version(sdk))
        elif cmd == 0x80000028:
            entry, stack = _unpack(endian + 'QQ', c, 8)
            result['entrypoint'] = dict(file_offset=entry, stack_size=stack)
        elif cmd == 0x5:
            flavor, count = _unpack(endian + 'II', c, 8)
            if 16 + count * 4 > len(c):
                raise MachOError('truncated thread state')
            if cpu == 0x01000007 and flavor == 4 and count == 42:
                registers = _unpack(endian + '21Q', c, 16)
                result['entrypoint'] = dict(kind='unixthread', vm_address=hex(registers[16]))
        elif cmd in (0x19, 0x1):
            wide = cmd == 0x19
            values = _unpack(endian + ('II16sQQQQiiII' if wide else 'II16sIIIIiiII'), c)
            _, _, name, vmaddr, vmsize, fileoff, filesize, maxprot, initprot, sections, _ = values
            base, section_size = (72, 80) if wide else (56, 68)
            if base + sections * section_size > len(c):
                raise MachOError('truncated section list')
            if filesize and (fileoff > len(data) or filesize > len(data) - fileoff):
                raise MachOError('segment exceeds file bounds')
            result['segments'].append(dict(name=_name(name), vm_address=hex(vmaddr), vm_size=vmsize,
                                           file_offset=fileoff, file_size=filesize, max_protection=maxprot,
                                           initial_protection=initprot, section_count=sections))
            for i in range(sections):
                pos = base + i * section_size
                sect, seg = _unpack(endian + '16s16s', c, pos)
                address, length = _unpack(endian + ('QQ' if wide else 'II'), c, pos + 32)
                if _name(sect).startswith('__objc_'):
                    result['objc_sections'].append(dict(name=_name(sect), segment=_name(seg), size=length,
                                                        address=hex(address)))
        elif cmd in (0x1d, 0x80000034):
            start, length = _unpack(endian + 'II', c, 8)
            if start > len(data) or length > len(data) - start:
                raise MachOError('linkedit data exceeds file bounds')
            result['code_signature' if cmd == 0x1d else 'chained_fixups'] = length > 0
        elif cmd in (0x21, 0x2c):
            _, _, cryptid = _unpack(endian + 'III', c, 8)
            result['encrypted'] = cryptid != 0
        offset += cmdsize
    if offset != end:
        raise MachOError('load command count and size disagree')
    return result


def parse_macho(data: bytes) -> list[dict]:
    """Return each thin/fat slice's metadata; reject invalid metadata bounds."""
    magic = data[:4]
    if magic in THIN:
        return [_thin(data)]
    if magic not in FAT:
        raise MachOError('not a Mach-O file')
    endian, wide = FAT[magic]
    _, count = _unpack(endian + 'II', data)
    entry_size = 32 if wide else 20
    table_end = 8 + count * entry_size
    if count == 0 or table_end > len(data):
        raise MachOError('invalid fat architecture table')
    slices, ranges = [], []
    for i in range(count):
        values = _unpack(endian + ('IIQQII' if wide else 'IIIII'), data, 8 + i * entry_size)
        cpu, subtype, offset, size, align = values[:5]
        if align > 63 or offset < table_end or offset % (1 << align) or size == 0 or offset > len(data) or size > len(data) - offset:
            raise MachOError('invalid fat slice bounds or alignment')
        if any(offset < stop and offset + size > start for start, stop in ranges):
            raise MachOError('overlapping fat slices')
        s = _thin(data[offset:offset + size])
        if s['cpu_type'] != cpu or s['cpu_subtype'] != subtype:
            raise MachOError('fat architecture metadata disagrees with slice')
        s.update(slice_offset=offset, slice_size=size)
        slices.append(s)
        ranges.append((offset, offset + size))
    return slices
