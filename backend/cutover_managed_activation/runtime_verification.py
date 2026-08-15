"""Self-verification performed by the newly published Runtime."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .canonical import fail
from .runtime_execution import run_offline
from .runtime_policy import PYTHON_VERSION

_MAX_OUTPUT = 256_000
_SQLITE_BINARIES = ("DLLs/_sqlite3.pyd", "DLLs/sqlite3.dll")

_SCRIPT_HELPERS = r"""import sys,nt,_sha2,_imp
if sys._xoptions != {'frozen_modules':'on'} or not _imp.is_frozen('codecs'):
 raise RuntimeError('startup')
def _audit(event,args):
 if event == 'import' or event.startswith(('socket.','subprocess.')) or event == 'os.system':
  raise RuntimeError('blocked')
sys.addaudithook(_audit)
def _read(path,limit):
 result=bytearray()
 with open(path,'rb') as source:
  while len(result) <= limit:
   block=source.read(min(65536,limit+1-len(result)))
   if not block: break
   result.extend(block)
 if len(result) > limit: raise RuntimeError('bounded')
 return bytes(result)
def _hash(path):
 digest=_sha2.sha256()
 with open(path,'rb') as source:
  while True:
   block=source.read(65536)
   if not block: break
   digest.update(block)
 return digest.hexdigest()
def _metadata(path):
 lines=_read(path,1048576).splitlines()
 header=[]
 for line in lines:
  if not line: break
  header.append(line)
 names=[line[6:] for line in header if line.startswith(b'Name: ')]
 versions=[line[9:] for line in header if line.startswith(b'Version: ')]
 if len(names) != 1 or len(versions) != 1: raise RuntimeError('metadata')
 name=names[0].decode()
 version=versions[0].decode()
 if not _safe(name) or not _safe(version): raise RuntimeError('metadata')
 return name,version
def _safe(value):
 allowed='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-!+'
 return 1 <= len(value) <= 128 and value.isascii() and all(ch in allowed for ch in value)
def _one_import_hash(site,module_path,package_path):
 hashes=[]
 for relative in (module_path,package_path):
  try: hashes.append(_hash(site+'\\'+relative))
  except FileNotFoundError: pass
 if len(hashes) != 1: raise RuntimeError('import')
 return hashes[0]
def _pairs(items):
 return ','.join('["'+first+'","'+second+'"]' for first,second in items)
"""

_SCRIPT_MAIN = r"""
root=sys.executable.rpartition('\\')[0]
site=root+'\\Lib\\site-packages'
expected_metadata=sorted([item[2] for item in package_specs],key=str.casefold)
observed_metadata=sorted([
 name for name in nt.listdir(site)
 if name.casefold().endswith(('.dist-info','.egg-info'))
],key=str.casefold)
if observed_metadata != expected_metadata: raise RuntimeError('installed')
installed=[]
imports=[]
for distribution,version,dist_info,import_name,module_path,package_path in package_specs:
 actual_name,actual_version=_metadata(site+'\\'+dist_info+'\\METADATA')
 installed.append([actual_name,actual_version])
 imports.append([import_name,_one_import_hash(site,module_path,package_path)])
installed.sort(key=lambda item:item[0].casefold())
sqlite_binaries=[
 [name,_hash(root+'\\'+name.replace('/','\\'))]
 for name in sqlite_binary_names
]
output=(
 '{"codecs_frozen":1,'
 '"dependency_lock_sha256":"'+_hash(root+'\\dependency-lock.json')+'",'
 '"dont_write_bytecode":'+str(sys.flags.dont_write_bytecode)+','
 '"executable_name":"python.exe",'
 '"frozen_modules_on":1,'
 '"imports":['+_pairs(imports)+'],'
 '"installed":['+_pairs(installed)+'],'
 '"isolated":'+str(sys.flags.isolated)+','
 '"no_site":'+str(sys.flags.no_site)+','
 '"no_user_site":'+str(sys.flags.no_user_site)+','
 '"python_executable_sha256":"'+_hash(sys.executable)+'",'
 '"python_version":"'+sys.version.split()[0]+'",'
 '"startup_archive_sha256":"'+_hash(root+'\\managed-startup.zip')+'",'
 '"sqlite_binaries":['+_pairs(sqlite_binaries)+']}'
)
print(output)
"""


def verify_with_new_runtime(target: Path, review) -> dict[str, object]:
    executable = target / "python.exe"
    completed = run_offline(
        [
            str(executable),
            "-X",
            "frozen_modules=on",
            "-I",
            "-B",
            "-S",
            "-c",
            _verification_script(review),
        ],
        root=target,
        timeout=20,
        output_limit=_MAX_OUTPUT,
    )
    if (
        completed.returncode != 0
        or not completed.stdout
        or len(completed.stdout) > _MAX_OUTPUT
    ):
        fail("runtime_self_verification_failed")
    try:
        value = json.loads(completed.stdout.decode("ascii"))
    except (UnicodeError, json.JSONDecodeError):
        fail("runtime_self_verification_failed")
    if type(value) is not dict:
        fail("runtime_self_verification_failed")
    return value


def validate_runtime_evidence(
    value, review, target, sqlite_binary_hashes, startup_archive_hash
) -> None:
    expected_packages = sorted(
        [[wheel.distribution, wheel.version] for wheel in review.wheels],
        key=lambda item: item[0].casefold(),
    )
    expected_imports = [
        [wheel.import_name, wheel.import_sha256] for wheel in review.wheels
    ]
    expected = {
        "codecs_frozen": 1,
        "frozen_modules_on": 1,
        "python_version": PYTHON_VERSION,
        "python_executable_sha256": review.source_executable_sha256,
        "startup_archive_sha256": startup_archive_hash,
        "sqlite_binaries": [list(item) for item in sqlite_binary_hashes],
        "dependency_lock_sha256": review.dependency_lock_fingerprint,
        "installed": expected_packages,
        "imports": expected_imports,
        "isolated": 1,
        "no_site": 1,
        "no_user_site": 1,
        "dont_write_bytecode": 1,
        "executable_name": "python.exe",
    }
    if value != expected:
        fail("runtime_self_verification_failed")
    executable = target / "python.exe"
    if not executable.is_file() or executable.is_symlink():
        fail("runtime_self_verification_failed")


def _verification_script(review) -> str:
    return (
        _SCRIPT_HELPERS
        + "\npackage_specs="
        + repr(_package_specs(review))
        + "\nsqlite_binary_names="
        + repr(_SQLITE_BINARIES)
        + _SCRIPT_MAIN
    )


def _package_specs(review) -> tuple[tuple[str, ...], ...]:
    result = []
    for wheel in review.wheels:
        dist_info = (
            re.sub(r"[-_.]+", "_", wheel.distribution)
            + "-"
            + wheel.version
            + ".dist-info"
        )
        import_parts = wheel.import_name.split(".")
        base = "\\".join(import_parts)
        result.append(
            (
                wheel.distribution,
                wheel.version,
                dist_info,
                wheel.import_name,
                base + ".py",
                base + "\\__init__.py",
            )
        )
    return tuple(result)
