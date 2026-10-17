import struct
import unittest

from tools.macho import MachOError, parse_macho


def thin(cpu=0x01000007, commands=b'', count=0):
    return struct.pack('<8I', 0xfeedfacf, cpu, 3, 2, count, len(commands), 0, 0) + commands


def dylib(name='/usr/lib/libSystem.B.dylib'):
    payload = name.encode() + b'\0'
    size = (24 + len(payload) + 7) & ~7
    return struct.pack('<6I', 0xc, size, 24, 0, 0, 0) + payload.ljust(size - 24, b'\0')


class MachOTests(unittest.TestCase):
    def test_thin_x86_dependency_and_main(self):
        commands = dylib() + struct.pack('<IIQQ', 0x80000028, 24, 4096, 0)
        s = parse_macho(thin(commands=commands, count=2))[0]
        self.assertEqual(s['architecture'], 'x86_64')
        self.assertEqual(s['bits'], 64)
        self.assertEqual(s['dependencies'][0]['name'], '/usr/lib/libSystem.B.dylib')
        self.assertEqual(s['entrypoint']['file_offset'], 4096)

    def test_universal_binary(self):
        x86, arm = thin(), thin(0x0100000c)
        table = struct.pack('>II', 0xcafebabe, 2)
        table += struct.pack('>5I', 0x01000007, 3, 48, len(x86), 0)
        table += struct.pack('>5I', 0x0100000c, 3, 80, len(arm), 0)
        self.assertEqual([s['architecture'] for s in parse_macho(table + x86 + arm)], ['x86_64', 'arm64'])

    def test_truncated_and_non_macho(self):
        for data in [b'', b'nope', thin()[:20], thin(commands=dylib(), count=1)[:-1]]:
            with self.subTest(data=data[:4]), self.assertRaises(MachOError):
                parse_macho(data)

    def test_invalid_command_sizes(self):
        for size in [0, 4, 9, 1024]:
            data = thin(commands=struct.pack('<II', 0xc, size), count=1)
            with self.subTest(size=size), self.assertRaises(MachOError):
                parse_macho(data)

    def test_unterminated_or_header_pointing_dylib_string(self):
        for offset in [0, 24, 200]:
            cmd = struct.pack('<6I', 0xc, 32, offset, 0, 0, 0) + b'xxxxxxxx'
            with self.subTest(offset=offset), self.assertRaises(MachOError):
                parse_macho(thin(commands=cmd, count=1))

    def test_fat_slice_out_of_bounds(self):
        data = struct.pack('>7I', 0xcafebabe, 1, 0x01000007, 3, 4096, 32, 0)
        with self.assertRaises(MachOError):
            parse_macho(data)

    def test_fat_metadata_mismatch(self):
        data = struct.pack('>7I', 0xcafebabe, 1, 0x0100000c, 3, 28, 32, 0) + thin()
        with self.assertRaises(MachOError):
            parse_macho(data)

    def test_32bit_and_big_endian(self):
        data = struct.pack('>7I', 0xfeedface, 18, 0, 2, 0, 0, 0)
        self.assertEqual(parse_macho(data)[0]['bits'], 32)
        self.assertEqual(parse_macho(data)[0]['architecture'], 'ppc')

    def test_build_version_and_objc_section(self):
        build = struct.pack('<6I', 0x32, 24, 1, 0x000a0a00, 0x000b0300, 0)
        segment = struct.pack('<II16sQQQQiiII', 0x19, 152, b'__DATA', 0x100004000, 4096, 0, 0, 3, 3, 1, 0)
        section = struct.pack('<16s16sQQIIIIIIII', b'__objc_classlist', b'__DATA', 0x100004000, 8, 0, 3, 0, 0, 0, 0, 0, 0)
        s = parse_macho(thin(commands=build + segment + section, count=2))[0]
        self.assertEqual(s['minimum_os'], '10.10.0')
        self.assertEqual(s['objc_sections'][0]['name'], '__objc_classlist')

    def test_static_unixthread_entry(self):
        regs = [0] * 21
        regs[16] = 0x100000270
        cmd = struct.pack('<4I21Q', 5, 184, 4, 42, *regs)
        entry = parse_macho(thin(commands=cmd, count=1))[0]['entrypoint']
        self.assertEqual(entry, {'kind': 'unixthread', 'vm_address': '0x100000270'})


if __name__ == '__main__':
    unittest.main()
