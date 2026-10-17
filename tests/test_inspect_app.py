import pathlib
import os
import plistlib
import subprocess
import sys
import tempfile
import unittest

from tools.inspect_app import inspect_app
from test_macho import thin


class AppTests(unittest.TestCase):
    @unittest.skipIf(os.geteuid() == 0, 'root can traverse unreadable directories')
    def test_unreadable_directory_does_not_report_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = pathlib.Path(tmp) / 'Fixture.app'
            content = app / 'Contents'
            frameworks = content / 'Frameworks'
            frameworks.mkdir(parents=True)
            (content / 'Info.plist').write_bytes(plistlib.dumps({'CFBundleExecutable': 'Fixture'}))
            (frameworks / 'hidden').write_bytes(thin())
            frameworks.chmod(0)
            try:
                with self.assertRaises(PermissionError):
                    inspect_app(app)
            finally:
                frameworks.chmod(0o700)

    @unittest.skipUnless(sys.platform == 'darwin', 'requires Apple Clang, lipo and nm')
    def test_universal_imports_are_collected_for_each_architecture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            app = root / 'Fixture.app'
            content = app / 'Contents'
            (content / 'MacOS').mkdir(parents=True)
            (content / 'Info.plist').write_bytes(plistlib.dumps({'CFBundleExecutable': 'Fixture'}))
            objects = []
            for arch, symbol in [('x86_64', 'x86_only'), ('arm64', 'arm_only')]:
                source, obj = root / f'{arch}.c', root / f'{arch}.o'
                source.write_text(f'extern void {symbol}(void); void f(void) {{ {symbol}(); }}')
                subprocess.run(['xcrun', 'clang', '-arch', arch, '-c', str(source), '-o', str(obj)], check=True)
                objects.append(str(obj))
            subprocess.run(['xcrun', 'lipo', '-create', *objects, '-output', str(content / 'MacOS/Fixture')], check=True)
            result = inspect_app(app, apple_tools=True)
            slices = {s['architecture']: s for s in result['binaries'][0]['slices']}
            self.assertIn('_x86_only', slices['x86_64']['undefined_symbols'])
            self.assertNotIn('_arm_only', slices['x86_64']['undefined_symbols'])
            self.assertIn('_arm_only', slices['arm64']['undefined_symbols'])
            self.assertNotIn('_x86_only', slices['arm64']['undefined_symbols'])

    def test_ignores_external_symlinks_and_private_plist_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            app = root / 'Fixture.app'
            content = app / 'Contents'
            (content / 'MacOS').mkdir(parents=True)
            (content / 'MacOS' / 'Fixture').write_bytes(thin())
            (content / 'Info.plist').write_bytes(plistlib.dumps({
                'CFBundleExecutable': 'Fixture', 'CFBundleIdentifier': 'org.altrosetta.fixture',
                'ProductKey': 'do-not-collect',
            }))
            outside = root / 'outside'
            outside.write_bytes(thin())
            (content / 'external').symlink_to(outside)
            (content / 'external-dir').symlink_to(root, target_is_directory=True)
            result = inspect_app(app)
            self.assertEqual(len(result['binaries']), 1)
            self.assertNotIn('ProductKey', result['bundle'])
            self.assertNotIn('do-not-collect', str(result))
            self.assertEqual(result['binaries'][0]['path'], 'Contents/MacOS/Fixture')

    def test_rejects_info_plist_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            app = root / 'Fixture.app'
            (app / 'Contents').mkdir(parents=True)
            external = root / 'Info.plist'
            external.write_bytes(plistlib.dumps({'CFBundleExecutable': 'Fixture'}))
            (app / 'Contents' / 'Info.plist').symlink_to(external)
            with self.assertRaises(ValueError):
                inspect_app(app)
