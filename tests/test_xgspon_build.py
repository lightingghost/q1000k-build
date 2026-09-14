#!/usr/bin/env python3
"""Exercise checkout isolation and build guards with disposable Git repositories."""
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/q1000k-xgspon-build.py'
BUILD = runpy.run_path(str(SCRIPT))


class BuildTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='q1000k-build-test.')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / 'repository'
        subprocess.run(['git', 'init', '-q', '-b', 'q1000k-dev', str(self.repo)], check=True)
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        (self.repo / 'Makefile').write_text('all:\n\t@true\n')
        (self.repo / '.gitignore').write_text('/.config\n/files\n')
        self.commit('base')
        self.base = self.git('rev-parse', 'HEAD')
        self.git('checkout', '-qb', 'q1000k-xgspon')
        for name in BUILD['PACKAGE_PATHS']:
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('# fixture\n')
        self.commit('packages')
        self.revision = self.git('rev-parse', 'HEAD')
        (self.repo / 'checkpoint').write_text('later checkpoint\n')
        self.commit('later')
        self.tip = self.git('rev-parse', 'HEAD')
        self.output = self.root / 'build'

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True).strip()

    def commit(self, title):
        self.git('add', '--all')
        self.git('commit', '-qm', title)

    def command(self, *args, success=True):
        result = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def prepare(self, revision=None, success=True):
        return self.command('prepare', '--repo', self.repo, '--revision', revision or self.revision,
                            self.output, success=success)

    def resolve(self):
        config = self.output / 'openwrt/.config'
        config.write_text('CONFIG_HAVE_DOT_CONFIG=y\n' + config.read_text())

    def test_pinned_ancestor_is_detached_and_source_is_unchanged(self):
        self.prepare()
        clone = self.output / 'openwrt'
        self.assertEqual(subprocess.check_output(['git', '-C', str(clone), 'rev-parse', 'HEAD'],
                                                text=True).strip(), self.revision)
        self.assertEqual(subprocess.run(['git', '-C', str(clone), 'symbolic-ref', '-q', 'HEAD']).returncode, 1)
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.tip)
        self.assertEqual(self.git('rev-parse', 'q1000k-dev'), self.base)
        self.assertEqual(self.git('status', '--porcelain'), '')
        manifest = json.loads((self.output / 'selection.json').read_text())
        self.assertEqual(manifest['revision'], self.revision)
        self.assertEqual(manifest['branch'], 'q1000k-xgspon')
        self.assertEqual(manifest['required_config']['CONFIG_PACKAGE_q1000k-xgspon-service'], 'y')
        self.command('verify', self.output, success=False)
        self.resolve()
        self.command('verify', self.output)

    def test_invalid_revision_never_creates_output(self):
        for value in ('HEAD', '--help', self.revision[:12], 'f' * 39, 'F' * 40, '$(touch sentinel)'):
            with self.subTest(value=value):
                self.prepare(value, success=False)
                self.assertFalse(self.output.exists())

    def test_existing_directory_is_preserved(self):
        self.output.mkdir()
        sentinel = self.output / 'sentinel'
        sentinel.write_text('preserve me')
        self.prepare(success=False)
        self.assertEqual(sentinel.read_text(), 'preserve me')
        self.assertEqual(list(self.output.iterdir()), [sentinel])

    def test_other_branch_revision_is_rejected(self):
        self.git('checkout', '-qb', 'unrelated', self.base)
        (self.repo / 'unrelated').write_text('other branch\n')
        self.commit('unrelated')
        self.prepare(self.git('rev-parse', 'HEAD'), success=False)
        self.assertFalse((self.output / 'selection.json').exists())
        self.assertFalse((self.output / 'openwrt/.config').exists())

    def test_common_base_without_packages_is_rejected(self):
        self.prepare(self.base, success=False)
        self.assertFalse((self.output / 'selection.json').exists())

    def test_configuration_loss_is_reported(self):
        self.prepare()
        self.resolve()
        path = self.output / 'openwrt/.config'
        initial = path.read_text()
        for option in ('CONFIG_PACKAGE_kmod-airoha-xpon-en757x',
                       'CONFIG_PACKAGE_q1000k-xgspon-service', 'CONFIG_BROKEN',
                       'CONFIG_TARGET_airoha_an7581_DEVICE_quantum_q1000k-ubi'):
            with self.subTest(option=option):
                path.write_text(initial.replace(option + '=y', '# ' + option + ' is not set'))
                result = self.command('verify', self.output, success=False)
                self.assertIn(option, result.stderr)

    def test_changed_source_and_manifest_are_rejected(self):
        self.prepare()
        self.resolve()
        source = self.output / 'openwrt'
        path = source / 'Makefile'
        initial = path.read_text()
        path.write_text('# changed\n')
        self.command('verify', self.output, success=False)
        path.write_text(initial)
        self.command('verify', self.output)
        # A new untracked patch can change compiled code without git diff.
        added = source / 'package/kernel/airoha-pon/extra.patch'
        added.write_text('untracked source input\n')
        self.command('verify', self.output, success=False)
        added.unlink()
        self.command('verify', self.output)
        subprocess.run(['git', '-C', str(source), 'checkout', '-q', '--detach', self.tip], check=True)
        self.command('verify', self.output, success=False)
        subprocess.run(['git', '-C', str(source), 'checkout', '-q', '--detach', self.revision], check=True)
        manifest = self.output / 'selection.json'
        data = json.loads(manifest.read_text())
        data['required_config'] = {}
        manifest.write_text(json.dumps(data))
        self.command('verify', self.output, success=False)


if __name__ == '__main__':
    unittest.main()
