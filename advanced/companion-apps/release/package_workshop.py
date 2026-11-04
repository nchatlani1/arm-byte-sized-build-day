"""Deterministic unified repository release; explicit source only, never credentials."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import zipfile

HERE = Path(__file__).resolve().parent
RUNTIME = {'.git', '.pio', '.generated', '.local', '.venv', '.venv-companion', 'build', 'dist', '__pycache__'}
GENERATED_EDITOR = {'.vscode/c_cpp_properties.json', '.vscode/launch.json'}

def read_manifest(path):
    names = [line.strip() for line in Path(path).read_text().splitlines()
             if line.strip() and not line.startswith('#')]
    if not names or names != sorted(set(names)):
        raise ValueError('Manifest must be nonempty, sorted and unique')
    for name in names:
        p = PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or p.as_posix() != name or '\\' in name:
            raise ValueError('Unsafe manifest path')
        if any(part in RUNTIME for part in p.parts) or name.endswith(tuple(GENERATED_EDITOR)):
            raise ValueError('Generated/private manifest entry')
        if p.name in ('.env', 'secrets.h') or p.name.endswith(('-token.json', '-credentials.json')):
            raise ValueError('Private manifest entry')
    return names

def source_files(source):
    result = set()
    source = Path(source)
    if source.is_symlink():
        raise ValueError('Source root must not be a symlink')
    for root, dirs, files in os.walk(source):
        for name in dirs:
            if (Path(root)/name).is_symlink():
                raise ValueError('Source symlink is not allowed')
        dirs[:] = [name for name in dirs if name not in RUNTIME]
        for name in files:
            p = Path(root)/name
            rel = p.relative_to(source).as_posix()
            if p.is_symlink():
                raise ValueError('Source symlink is not allowed')
            if rel.endswith(tuple(GENERATED_EDITOR)) or name == '.DS_Store' or name.endswith('.pyc'):
                continue
            result.add(rel)
    return result

def package(source, output, release, manifest=HERE/'repository-files.txt'):
    source, output = Path(source), Path(output)
    if not source.is_dir():
        raise ValueError('Source directory is missing')
    if output.resolve() == source.resolve() or source.resolve() in output.resolve().parents:
        raise ValueError('Release output must be outside repository source')
    names = read_manifest(manifest)
    actual = source_files(source)
    if actual != set(names):
        raise ValueError('Source/manifest mismatch: missing='+repr(sorted(set(names)-actual))+
                         '; unexpected='+repr(sorted(actual-set(names))))
    output.mkdir(parents=True, exist_ok=True)
    archive = output/'CrowPanel-Workshop-Source.zip'
    records = []
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in names:
            data = (source/name).read_bytes()
            info = zipfile.ZipInfo('CrowPanel-Workshop/'+name, (2026, 11, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            z.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED)
            records.append(dict(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    with zipfile.ZipFile(archive) as z:
        if z.testzip() or z.namelist() != ['CrowPanel-Workshop/'+n for n in names]:
            raise RuntimeError('Archive integrity/membership failure')
        for item in records:
            if hashlib.sha256(z.read('CrowPanel-Workshop/'+item['path'])).hexdigest() != item['sha256']:
                raise RuntimeError('Archive/source byte mismatch')
    result = dict(release=release, archive=archive.name,
                  sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                  source_bytes=sum(r['bytes'] for r in records), file_count=len(records), files=records)
    (output/'participant-release.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='files'}))
    return archive

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--release', required=True)
    args = parser.parse_args()
    package(args.source, args.output, args.release)

if __name__ == '__main__':
    main()
