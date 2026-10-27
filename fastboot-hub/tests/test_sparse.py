import os
import struct
import tempfile
import unittest
from pathlib import Path

from fbhub.sparse import (
    CHUNK_HEADER,
    CHUNK_TYPE_DONT_CARE,
    CHUNK_TYPE_FILL,
    CHUNK_TYPE_RAW,
    SPARSE_HEADER,
    SPARSE_MAGIC,
    SparseError,
    SparseSource,
    is_sparse_file,
    iter_sparse_parts,
    open_source,
)

BS = 4096


def parse_sparse(data: bytes):
    magic, major, minor, file_hdr, chunk_hdr, blk, total, chunks, crc = (
        SPARSE_HEADER.unpack_from(data, 0)
    )
    assert magic == SPARSE_MAGIC
    offset = file_hdr
    cursor = 0
    segments = []
    for _ in range(chunks):
        chunk_type, _reserved, chunk_sz, total_sz = CHUNK_HEADER.unpack_from(data, offset)
        payload = data[offset + chunk_hdr:offset + total_sz]
        if chunk_type == CHUNK_TYPE_RAW:
            count = (chunk_sz + blk - 1) // blk
            segments.append(("raw", cursor, count, payload.ljust(count * blk, b"\0")))
            cursor += count
        elif chunk_type == CHUNK_TYPE_FILL:
            count = chunk_sz // blk
            segments.append(("fill", cursor, count, int.from_bytes(payload[:4], "little")))
            cursor += count
        elif chunk_type == CHUNK_TYPE_DONT_CARE:
            count = chunk_sz // blk
            cursor += count
        else:
            raise AssertionError(f"unexpected chunk {chunk_type}")
        offset += total_sz
    assert cursor == total
    return total, segments


def apply_parts(parts, total_bytes: int) -> bytes:
    output = bytearray(total_bytes)
    for part in parts:
        _total, segments = parse_sparse(part)
        for kind, start, count, payload in segments:
            offset = start * BS
            length = count * BS
            if kind == "raw":
                output[offset:offset + length] = payload
            elif kind == "fill":
                output[offset:offset + length] = int(payload).to_bytes(4, "little") * (length // 4)
    return bytes(output)


class SparseTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)

    def write(self, name: str, data: bytes) -> Path:
        path = Path(self.tempdir.name) / name
        path.write_bytes(data)
        return path

    def test_raw_roundtrip_and_split(self):
        blocks = (
            [os.urandom(BS) for _ in range(2)]
            + [b"\0" * BS] * 4
            + [os.urandom(BS)]
            + [b"\0" * BS] * 3
        )
        raw = b"".join(blocks)
        path = self.write("raw.img", raw)

        for limit in (100_000, 4160, 8256, 12288):
            with self.subTest(limit=limit), open_source(path) as source:
                parts = list(iter_sparse_parts(source, limit))
                self.assertTrue(parts)
                for part in parts:
                    self.assertLessEqual(len(part), limit)
                self.assertEqual(apply_parts(parts, len(raw)), raw)

    def test_existing_sparse_roundtrip(self):
        blocks = [os.urandom(BS), b"\0" * BS * 3, os.urandom(BS)]
        raw = b"".join(blocks)
        raw_path = self.write("raw.img", raw)
        with open_source(raw_path) as source:
            sparse_data = next(iter(iter_sparse_parts(source, 10 ** 9)))
        sparse_path = self.write("image.sparse", sparse_data)
        self.assertTrue(is_sparse_file(sparse_path))
        with open_source(sparse_path) as source:
            self.assertIsInstance(source, SparseSource)

        for limit in (4160, 8256):
            with open_source(sparse_path) as source:
                parts = list(iter_sparse_parts(source, limit))
            for part in parts:
                self.assertLessEqual(len(part), limit)
            self.assertEqual(apply_parts(parts, len(raw)), raw)

    def test_last_partial_block_padded(self):
        raw = os.urandom(BS + 100)
        path = self.write("partial.img", raw)
        with open_source(path) as source:
            parts = list(iter_sparse_parts(source, 100_000))
        rebuilt = apply_parts(parts, BS * 2)
        self.assertEqual(rebuilt[:len(raw)], raw)
        self.assertEqual(rebuilt[len(raw):], b"\0" * (BS * 2 - len(raw)))

    def test_invalid_limit(self):
        path = self.write("small.img", os.urandom(BS))
        with open_source(path) as source, self.assertRaises(SparseError):
            list(iter_sparse_parts(source, 30))

    def test_empty_image_rejected(self):
        path = self.write("empty.img", b"")
        with self.assertRaises(SparseError):
            open_source(path)

    def test_huge_fill_chunk_is_split_into_valid_chunks(self):
        # A 2.4 GiB fill cannot fit in one sparse chunk (chunk_sz is uint32),
        # so it must be emitted as several chunks while the header keeps the
        # full image block count.
        blocks = 600_000
        data = SPARSE_HEADER.pack(
            SPARSE_MAGIC, 1, 0, 28, 12, BS, blocks, 1, 0
        ) + CHUNK_HEADER.pack(CHUNK_TYPE_FILL, 0, blocks * BS, 16) + struct.pack("<I", 0)
        path = self.write("huge-fill.sparse", data)
        with open_source(path) as source:
            parts = list(iter_sparse_parts(source, 1024 * 1024))
        self.assertEqual(len(parts), 1)
        total, segments = parse_sparse(parts[0])
        self.assertEqual(total, blocks)
        self.assertEqual(len(segments), 3)
        self.assertTrue(all(item[0] == "fill" for item in segments))


if __name__ == "__main__":
    unittest.main()
