"""Verify the archived snapshot and exported candidates without modifying them."""
import hashlib
import json
import re
import tarfile
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / 'snapshot_manifest.json').read_text(encoding='utf-8'))
    archive = root / 'rebuild_snapshot.tar.gz'
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == manifest['archive_sha256']
    expected = {entry['path']: entry for entry in manifest['archive_files']}
    seen = set()
    secret_pattern = re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|sk-[A-Za-z0-9_-]{32,}|AKIA[A-Z0-9]{16})')
    with tarfile.open(archive, 'r:gz') as tar:
        for member in tar:
            assert member.isfile() and not member.name.startswith('/') and '..' not in Path(member.name).parts
            assert member.name not in seen
            seen.add(member.name)
            raw = tar.extractfile(member).read()
            entry = expected[member.name]
            assert len(raw) == entry['size']
            assert hashlib.sha256(raw).hexdigest() == entry['sha256']
            assert not secret_pattern.search(raw), f'Credential-like content: {member.name}'
    assert seen == set(expected)
    print(f'Archive verified: {len(seen)} files')
    all_ids = set()
    for label, count in manifest['latest_export_counts'].items():
        rows = []
        for path in sorted((root / 'candidates' / label).glob('*.jsonl')):
            assert path.stat().st_size < 95 * 1024 * 1024
            rows.extend(json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip())
        assert len(rows) == count
        for row in rows:
            assert row['file_id'] not in all_ids
            all_ids.add(row['file_id'])
            assert row['status'] == 'candidate' and row['human_acceptance'] == 'pending'
            entry = expected[row['source_draft']]
            assert row['source_draft_sha256'] == entry['sha256']
            assert isinstance(row['draft']['cases'], list) and isinstance(row['draft']['behaviors'], list)
        print(f'{label}: {len(rows)} unique candidate documents verified')
    audit = json.loads((root / 'quality_audit/mechanical_checks.json').read_text(encoding='utf-8'))
    assert len(audit) == 42 and all(row['sha_matches'] for row in audit)
    print('Quality audit: 42 samples; snapshot/export verification passed')


if __name__ == '__main__':
    main()
