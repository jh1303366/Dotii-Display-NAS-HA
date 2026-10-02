"""Install the pinned official Linux CLI, verifying its published integrity."""
import base64
import hashlib
import os
from pathlib import Path
import platform
import tarfile
import tempfile
import urllib.request

# This deployment targets the Intel Z4. Fail clearly on a different build CPU.
if platform.machine() not in {'x86_64', 'AMD64'}:
    raise SystemExit('This NAS image requires linux/amd64')
url = 'https://registry.npmjs.org/@openai/codex/-/codex-0.151.0-linux-x64.tgz'
integrity = 'xcVyY1FtwvVYhh2JBmz8fX8CQqFAxO/lxJ2IXsh8x5uwxZVHVl5fZHFHf8JdRaOGG0vpkYmu/DKKVoLd56/DDQ=='
with tempfile.TemporaryDirectory() as temporary:
    archive = Path(temporary) / 'codex.tgz'
    with urllib.request.urlopen(url, timeout=120) as response, archive.open('wb') as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    digest = hashlib.sha512()
    with archive.open('rb') as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    if base64.b64encode(digest.digest()).decode() != integrity:
        raise SystemExit('Codex package integrity mismatch')
    entries = {
        'package/vendor/x86_64-unknown-linux-musl/bin/codex': '/usr/local/bin/codex',
        'package/vendor/x86_64-unknown-linux-musl/codex-resources/bwrap': '/usr/local/bin/bwrap',
    }
    with tarfile.open(archive) as package:
        for member, target in entries.items():
            entry = package.getmember(member)
            if not entry.isfile():
                raise SystemExit('Unexpected Codex package member type')
            with package.extractfile(entry) as source, Path(target).open('wb') as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
            os.chmod(target, 0o755)
print('Installed verified Codex CLI 0.151.0 and its sandbox helper')
