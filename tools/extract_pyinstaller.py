#!/usr/bin/env python3
"""Extract the embedded files from a PyInstaller-built binary (ELF or .exe).

A PyInstaller "onefile" program is a bootloader with a *CArchive* appended to
it; that archive holds the frozen entry-point script, an inner *PYZ* archive of
all bundled Python modules, and any data/shared-object files. This tool parses
that structure and writes the pieces out as loadable ``.pyc`` plus raw data
files.

It is purely static -- it reads and decompresses bytes, it never executes the
target -- so it is safe to point at the malicious D2 executables. The recovered
``.pyc`` are the same Python 3.10 bytecode PyFEX analyzes.

Usage:
    extract_pyinstaller.py <binary|dir> <out_dir> [--limit N]

Notes:
    * For a directory, every regular file in it is treated as a candidate and
      extracted into ``<out_dir>/<binary_name>/``.
    * Best run with a Python matching the bundle (3.10). The written ``.pyc``
      carry the bundle's magic regardless; only the inner PYZ *index* is
      unmarshalled, which is portable across 3.x for its simple types.
"""
from __future__ import annotations

import argparse
import marshal
import struct
import sys
import zlib
from pathlib import Path

MEI_COOKIE = b"MEI\014\013\012\013\016"
COOKIE_V20 = 24            # magic + 4 uint32
COOKIE_V21 = 24 + 64       # ... + 64-byte python-lib name

# pyc header magic by the "pyver" integer stored in the cookie (e.g. 310 = 3.10)
PYC_MAGIC = {
    36: b"\x33\x0d\x0d\x0a", 37: b"\x42\x0d\x0d\x0a", 38: b"\x55\x0d\x0d\x0a",
    39: b"\x61\x0d\x0d\x0a", 310: b"\x6f\x0d\x0d\x0a", 311: b"\xa7\x0d\x0d\x0a",
    312: b"\xcb\x0d\x0d\x0a", 313: b"\xf3\x0d\x0d\x0a",
}


def pyc_header(pyver: int, magic: bytes | None = None) -> bytes:
    """A 16-byte PEP 552 header (3.7+) or the older 12/8-byte form."""
    magic = magic or PYC_MAGIC.get(pyver, PYC_MAGIC[310])
    if pyver >= 37:
        return magic + b"\0" * 12          # magic + bitfield + mtime + size
    if pyver >= 33:
        return magic + b"\0" * 8
    return magic + b"\0" * 4


class PyInstArchive:
    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        self.size = len(self.data)

    def parse(self) -> list[tuple]:
        cpos = self.data.rfind(MEI_COOKIE)
        if cpos == -1:
            raise ValueError("no PyInstaller MEI cookie (not a PyInstaller binary?)")
        tail = self.data[cpos + COOKIE_V20 : cpos + COOKIE_V21].lower()
        v21 = b"python" in tail or b".so" in tail or b".dll" in tail
        if v21:
            _m, lenpkg, toc, toclen, pyver, _lib = struct.unpack(
                "!8sIIII64s", self.data[cpos : cpos + COOKIE_V21])
            cookie_size = COOKIE_V21
        else:
            _m, lenpkg, toc, toclen, pyver = struct.unpack(
                "!8sIIII", self.data[cpos : cpos + COOKIE_V20])
            cookie_size = COOKIE_V20
        tail_bytes = self.size - cpos - cookie_size
        overlay = self.size - (lenpkg + tail_bytes)
        self.pyver = pyver
        return self._parse_toc(overlay, overlay + toc, toclen)

    def _parse_toc(self, overlay: int, toc_pos: int, toc_len: int) -> list[tuple]:
        entries, off, end = [], toc_pos, toc_pos + toc_len
        while off < end:
            (entry_size,) = struct.unpack("!i", self.data[off : off + 4])
            if entry_size < 18:
                break
            body = self.data[off + 4 : off + entry_size]
            epos, cds, uds, flag, typ = struct.unpack("!IIIBc", body[:14])
            name = body[14:].split(b"\0", 1)[0].decode("utf-8", "replace")
            entries.append((overlay + epos, cds, uds, flag, typ, name))
            off += entry_size
        return entries


def extract(bin_path: Path, out_dir: Path) -> dict:
    ar = PyInstArchive(bin_path)
    entries = ar.parse()
    out_dir.mkdir(parents=True, exist_ok=True)
    stats = {"data_files": 0, "pyc": 0, "pyz_modules": 0, "scripts": []}
    for pos, cds, _uds, flag, typ, name in entries:
        raw = ar.data[pos : pos + cds]
        if flag == 1:
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                pass
        safe = name.replace("\\", "/").lstrip("/") or "unnamed"
        if typ in (b"s", b"m", b"M"):                       # script / module / package
            dest = out_dir / (safe + ".pyc")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(pyc_header(ar.pyver) + raw)
            stats["pyc"] += 1
            if typ == b"s":
                stats["scripts"].append(safe)
        elif typ in (b"z", b"Z"):                           # inner PYZ archive
            (out_dir / (safe + ".pyz")).write_bytes(raw)
            stats["pyz_modules"] += _extract_pyz(raw, out_dir / (safe + "_extracted"), ar.pyver)
        else:                                               # binaries / data
            dest = out_dir / safe
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
            stats["data_files"] += 1
    return stats


def _extract_pyz(data: bytes, out: Path, pyver: int) -> int:
    if data[:4] != b"PYZ\0":
        return 0
    magic = data[4:8]
    (toc_pos,) = struct.unpack("!i", data[8:12])
    try:
        toc = marshal.loads(data[toc_pos:])
    except Exception:
        return 0
    if isinstance(toc, dict):
        toc = list(toc.items())
    out.mkdir(parents=True, exist_ok=True)
    hdr = pyc_header(pyver, magic)
    n = 0
    for name, entry in toc:
        try:
            ispkg, epos, length = entry
        except (TypeError, ValueError):
            continue
        try:
            code = zlib.decompress(data[epos : epos + length])
        except zlib.error:
            continue
        modname = name if isinstance(name, str) else name.decode("utf-8", "replace")
        rel = modname.replace(".", "/") + ("/__init__.pyc" if ispkg else ".pyc")
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(hdr + code)
        n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract embedded files from PyInstaller binaries.")
    ap.add_argument("target", help="A PyInstaller binary, or a directory of them.")
    ap.add_argument("out_dir", help="Output directory (one subfolder per binary).")
    ap.add_argument("--limit", type=int, default=0, help="Max binaries to process from a directory (0 = all).")
    args = ap.parse_args()

    target, out_root = Path(args.target), Path(args.out_dir)
    if target.is_dir():
        bins = sorted(p for p in target.iterdir() if p.is_file())
        if args.limit:
            bins = bins[: args.limit]
    else:
        bins = [target]

    ok = failed = 0
    for b in bins:
        try:
            stats = extract(b, out_root / b.name)
            entry = ",".join(s for s in stats["scripts"] if not s.startswith("py")) or "?"
            print(f"OK   {b.name}: pyz_modules={stats['pyz_modules']} pyc={stats['pyc']} "
                  f"data={stats['data_files']} entry~={entry}")
            ok += 1
        except Exception as exc:                            # noqa: BLE001
            print(f"FAIL {b.name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            failed += 1
    print(f"\nextracted {ok} binary(ies), {failed} failed -> {out_root}")
    return 1 if failed and not ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
