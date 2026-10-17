from pathlib import Path
import hashlib, json, re, zipfile

root = Path.cwd().resolve()
archives = sorted((root / '.skill-import').glob('skills-part-*.zip'))
if len(archives) != 14:
    raise SystemExit(f'Expected 14 archives, found {len(archives)}')
for archive in archives:
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            target = (root / info.filename).resolve()
            target.relative_to(root)
            if not (info.filename.startswith('.agents/skills/') or info.filename in {'README.md', 'AGENTS.md', 'SKILLS-CATALOG.json', 'SKILLS-FILES.json'}):
                raise SystemExit(f'Unexpected archive member: {info.filename}')
        bundle.extractall(root)
manifest = json.loads((root / 'SKILLS-FILES.json').read_text('utf-8'))
for item in manifest:
    p = root / item['path']
    if hashlib.sha256(p.read_bytes()).hexdigest() != item['sha256']:
        raise SystemExit(f'Checksum mismatch: {item["path"]}')
catalog = json.loads((root / 'SKILLS-CATALOG.json').read_text('utf-8'))
assert len(catalog['skills']) == 42
for skill in catalog['skills']:
    p = root / skill['folder'] / 'SKILL.md'
    text = p.read_text('utf-8-sig')
    match = re.search(r'^name:\s*[\"\']?([^\r\n\"\']+)', text, re.M)
    assert match and match.group(1).strip() == p.parent.name, p
entries = list((root / '.agents/skills').rglob('SKILL.md'))
assert len(entries) == 42, len(entries)
print(f'Validated {len(entries)} skills and {len(manifest)} file checksums.')

