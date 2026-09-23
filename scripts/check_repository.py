"""Offline maintenance/leakage checks and generated source status for the desktop tree.

Scans Git-visible files, including new non-ignored files. Does not inspect ignored
runtime data, archives, history, or secrets. Reports filenames/rule names only.
"""
from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self, text: str):
        super().__init__()
        self.tags: list[tuple[str, dict]] = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def main() -> int:
    files = sorted(set(subprocess.check_output(
        ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT,
    ).decode('utf-8').strip('\0').split('\0')))
    maintenance: list[str] = []
    leakage: list[str] = []
    forbidden = re.compile(r'^(?:Runtime|RuntimeTemp|Cache|Build|Program|Data|Logs|LegacyArchive)/|(?:^|/)\.env(?:\.|$)|\.(?:pem|key|db|sqlite3?|dpapi|bundle)$', re.I)
    credentials = re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bsk-[A-Za-z0-9_-]{20,}\b|\bAKIA[A-Z0-9]{16}\b')
    for name in files:
        path = ROOT / name
        if forbidden.search(name):
            leakage.append(f'{name}: forbidden repository artifact')
        if not path.is_file():
            maintenance.append(f'{name}: missing Git-visible file')
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        if credentials.search(text):
            leakage.append(f'{name}: credential-shaped content')
        if re.search(r'^(?:<{7} |={7}$|>{7} )', text, re.M):
            maintenance.append(f'{name}: conflict marker')
        if name.startswith('frontend/') and path.suffix == '.js':
            if re.search(r'\.innerHTML\s*=|\.insertAdjacentHTML\s*\(', text):
                maintenance.append(f'{name}: unsafe HTML write')
            if not shutil.which('node'):
                maintenance.append('Node.js is required; syntax checks were not run')
            elif subprocess.run(['node', '--check', str(path)], capture_output=True).returncode:
                maintenance.append(f'{name}: JavaScript syntax failed')
    notices = []
    for relative in ['frontend/browser_extension/popup.html', 'frontend/local_debug_page/index.html']:
        path = ROOT / relative
        text = path.read_text(encoding='utf-8')
        tags = Page(text).tags
        ids = [attrs['id'] for _, attrs in tags if 'id' in attrs]
        if len(ids) != len(set(ids)):
            maintenance.append(f'{relative}: duplicate IDs')
        by_id = {attrs['id']: attrs for _, attrs in tags if 'id' in attrs}
        if by_id.get('status', {}).get('aria-live') != 'polite':
            maintenance.append(f'{relative}: status must be polite')
        if 'readonly' not in by_id.get('draft', {}):
            maintenance.append(f'{relative}: browser draft must be readonly')
        if any('open' in attrs for tag, attrs in tags if tag == 'details'):
            maintenance.append(f'{relative}: details must start closed')
        for tag, attrs in tags:
            ref = attrs.get('src') if tag == 'script' else attrs.get('href') if tag == 'link' else None
            if not ref:
                continue
            asset = ROOT / 'frontend/browser_extension' / ref.lstrip('/') if ref.startswith('/shared/') else path.parent / ref.lstrip('/')
            if not asset.is_file():
                maintenance.append(f'{relative}: missing local asset')
        match = re.search(r'<p id="remote-processing-notice"[^>]*>(.*?)</p>', text, re.S)
        notices.append(match.group(1) if match else None)
    if not notices[0] or notices[0] != notices[1]:
        maintenance.append('Remote-processing disclosures differ or are absent')
    manifest = json.loads((ROOT / 'frontend/browser_extension/manifest.json').read_text(encoding='utf-8'))
    version = manifest['version']
    for name in ['README.md', 'docs/browser_verification.md']:
        if version not in (ROOT / name).read_text(encoding='utf-8'):
            maintenance.append(f'{name}: extension version is not synchronized')
    result = {
        'status': 'FAIL' if maintenance or leakage else 'PASS',
        'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'working_tree_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)),
        'extension_version': version, 'git_visible_files': len(files),
        'maintenance_findings': maintenance, 'leakage_findings': leakage,
        'limits': 'Pattern scan only; not a proof of absence of secrets. No ignored data or Git history inspected. No runtime, live mailbox or provider acceptance implied.',
    }
    output = ROOT / 'Build/project-status.json'
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    return int(result['status'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
