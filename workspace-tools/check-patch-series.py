#!/usr/bin/env python3
"""Check every numbered patch on a fresh pinned XNU checkout, with no skips.

This checks patch application, not compilation. Only the two HFS files that
patches modify are downloaded; full SDK and staged dependencies are needed
for the macOS build.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

def main():
    scratch = ROOT / 'toolchain' / 'tmp'
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='patch-check-', dir=scratch) as directory:
        tree = Path(directory) / 'xnu'
        subprocess.run(['git', 'clone', '--quiet', '--shared', '--no-hardlinks',
            str(ROOT / 'toolchain/xnu-baseline'), str(tree)], check=True)
        subprocess.run(['git', 'checkout', '--quiet', 'xnu-8796.141.3'], cwd=tree, check=True)
        for name in ['hfs_catalog.c', 'hfs_vfsutils.c']:
            target = tree / 'bsd/sweet_hfs/core' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            url = 'https://raw.githubusercontent.com/apple-oss-distributions/hfs/31d5ec238dfab485e78a9a30b8b92d13e8914f03/core/' + name
            with urllib.request.urlopen(url, timeout=60) as source, target.open('wb') as out:
                shutil.copyfileobj(source, out)
        log_path = ROOT / 'logs/patch-series-renoir.log'
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open('w') as log:
            patches = sorted((ROOT / 'src/xnu/patches').glob('*.patch'))
            for patch in patches:
                log.write(patch.name + '\n')
                log.flush()
                for command in [['git', 'apply', '--check', str(patch)], ['git', 'apply', str(patch)]]:
                    subprocess.run(command, cwd=tree, stdout=log, stderr=log, check=True)
            log.write(f'PASS: {len(patches)} patches applied with no skips. Compilation not tested.\n')
        print(log_path.read_text().splitlines()[-1])

if __name__ == '__main__':
    main()
