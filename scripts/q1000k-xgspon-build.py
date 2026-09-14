#!/usr/bin/env python3
"""Prepare and verify an isolated, explicitly pinned experimental OpenWrt build."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'user/q1000k-xgspon'
BRANCH = 'q1000k-xgspon'
PACKAGE_PATHS = (
    'package/kernel/q1000k-pon-control/Makefile',
    'package/kernel/q1000k-omci/Makefile',
    'package/kernel/airoha-pon/Makefile',
    'package/network/utils/q1000k-xgspon/Makefile',
    'package/network/utils/q1000k-omci-tools/Makefile',
    'package/network/utils/q1000k-xgspon-service/Makefile',
    'package/network/utils/q1000k-xgspon-wan/Makefile',
    'package/luci-app-econet-xpon/Makefile',
)


def git(source, *args):
    return subprocess.check_output(['git', '-C', str(source), *args], text=True).strip()


def settings():
    values = {}
    for line in (PROFILE / 'settings.ini').read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        key, sep, value = line.partition('=')
        words = shlex.split(value)
        if not sep or key not in ('REPO_URL', 'REPO_BRANCH') or len(words) != 1 or key in values:
            raise ValueError('Invalid experimental settings.ini')
        values[key] = words[0]
    if values.get('REPO_BRANCH') != BRANCH or not values.get('REPO_URL'):
        raise ValueError('Experimental settings must select q1000k-xgspon')
    return values


def profile(kind='experimental'):
    base = ROOT / ('user/q1000k-xgspon/bench.config' if kind == 'bench' else 'user/q1000k/config.diff')
    if kind not in ('experimental', 'bench'):
        raise ValueError('Unknown build profile')
    return (base.read_text().rstrip() + '\n' + (PROFILE / 'config.diff').read_text())


def config_values(text):
    result = {}
    for line in text.splitlines():
        if line.startswith('CONFIG_') and '=' in line:
            key, value = line.split('=', 1)
            if key in result:
                raise ValueError('Duplicate configuration symbol: ' + key)
            result[key] = value
        elif line.startswith('# CONFIG_') and line.endswith(' is not set'):
            key = line[2:-11]
            if key in result:
                raise ValueError('Duplicate configuration symbol: ' + key)
            result[key] = 'n'
    return result


def check_source(source, revision):
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('A full, lowercase 40-character source commit is required')
    git(source, 'cat-file', '-e', revision + '^{commit}')
    git(source, 'merge-base', '--is-ancestor', revision, 'origin/' + BRANCH)
    if git(source, 'rev-parse', 'HEAD') != revision:
        raise ValueError('Source HEAD does not match the selected revision')
    if git(source, 'status', '--porcelain', '--untracked-files=all'):
        raise ValueError('Source has tracked or untracked changes')
    for name in PACKAGE_PATHS:
        if not (source / name).is_file():
            raise ValueError('Selected source lacks ' + name)


def prepare(args):
    if not re.fullmatch(r'[0-9a-f]{40}', args.revision):
        raise ValueError('A full, lowercase 40-character source commit is required')
    values = settings()
    repo = args.repo or values['REPO_URL']
    # Convert a local source to an absolute path before changing directories.
    if Path(repo).exists():
        repo = str(Path(repo).resolve())
    seed = profile(args.profile)
    required = config_values(seed)
    output = args.directory.absolute()
    output.mkdir()  # Refuse even an empty existing directory; never overwrite a build.
    source = output / 'openwrt'
    subprocess.run(['git', 'clone', '--no-checkout', '--single-branch', '--branch', BRANCH,
                    '--', repo, str(source)], check=True)
    # Verify membership before checking out or publishing a configuration.
    git(source, 'merge-base', '--is-ancestor', args.revision, 'origin/' + BRANCH)
    git(source, 'checkout', '--detach', args.revision)
    check_source(source, args.revision)
    if args.profile == 'bench' and not (source / 'package/network/utils/q1000k-xgspon-bench/Makefile').is_file():
        raise ValueError('Selected revision lacks the RAM bench implementation')
    (source / '.config').write_text(seed)
    (source / 'files').mkdir(exist_ok=True)
    (source / 'files/build_info').write_text(
        f'Experimental Q1000K XGS-PON ({args.profile})\nSource: {repo}\nBranch: {BRANCH}\n'
        f'Revision: {args.revision}\nPON activation and hardware acceptance are separate.\n')
    manifest = dict(schema_version=1, source=repo, branch=BRANCH, revision=args.revision,
                    profile_sha256=hashlib.sha256(seed.encode()).hexdigest(),
                    required_config=required, profile=args.profile)
    (output / 'selection.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Prepared {source} at {args.revision}. Run feeds setup and make defconfig, then verify.')


def verify(args):
    output = args.directory.absolute()
    manifest = json.loads((output / 'selection.json').read_text())
    if manifest.get('schema_version') != 1 or manifest.get('branch') != BRANCH:
        raise ValueError('Invalid experimental build manifest')
    source = output / 'openwrt'
    check_source(source, manifest['revision'])
    seed = profile(manifest.get('profile', 'experimental'))
    if manifest.get('profile_sha256') != hashlib.sha256(seed.encode()).hexdigest():
        raise ValueError('Builder profile changed; prepare a new build with that profile')
    required = config_values(seed)
    if manifest.get('required_config') != required:
        raise ValueError('Build manifest does not match the experimental profile')
    actual = config_values((source / '.config').read_text())
    if actual.get('CONFIG_HAVE_DOT_CONFIG') != 'y':
        raise ValueError('Run make defconfig before verification')
    missing = [key for key, value in required.items() if actual.get(key, 'n') != value]
    if missing:
        raise ValueError('Resolved configuration changed required symbols: ' + ', '.join(missing))
    print(f'Verified {manifest["revision"]} on {BRANCH}; experimental packages are selected.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare', help='create a fresh source checkout and package profile')
    p.add_argument('--repo', help='source URL or local repository (default: experimental settings.ini)')
    p.add_argument('--revision', required=True, help='exact source commit on q1000k-xgspon')
    p.add_argument('--profile', choices=('experimental', 'bench'), default='experimental',
                   help='bench builds only a NAND-disabled, TX-inhibited RAM image at 192.168.0.1')
    p.add_argument('directory', type=Path, help='new build directory; must not exist')
    p.set_defaults(run=prepare)
    p = commands.add_parser('verify', help='check revision and resolved package selections before building')
    p.add_argument('directory', type=Path)
    p.set_defaults(run=verify)
    args = parser.parse_args()
    try:
        args.run(args)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Error: {error}\n')


if __name__ == '__main__':
    main()
