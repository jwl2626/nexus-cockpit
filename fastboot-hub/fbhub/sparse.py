"""Android sparse image encoding and splitting.

Large images cannot be sent in one fastboot ``download`` because the
bootloader advertises a ``max-download-size``.  The reference implementation
converts the image to the Android sparse format and splits it into several
*complete-length* sparse files: every part describes the whole image and uses
DONTCARE chunks for the ranges it does not write.  Each part is downloaded and
flashed in order, so the device ends up with the full image.

This module reproduces that behaviour without libsparse and without loading the
whole image into memory.
"""

from __future__ import annotations

import mmap
import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from .models import FastbootError

SPARSE_MAGIC = 0xED26FF3A
CHUNK_TYPE_RAW = 0xCAC1
CHUNK_TYPE_FILL = 0xCAC2
CHUNK_TYPE_DONT_CARE = 0xCAC3
CHUNK_TYPE_CRC32 = 0xCAC4

SPARSE_HEADER = struct.Struct("<IHHHHIIII")
CHUNK_HEADER = struct.Struct("<HHII")
DEFAULT_BLOCK_SIZE = 4096
WINDOW = 1024 * 1024
# One sparse chunk's byte count is a uint32.  Keep chunks well below 4 GiB so
# 8 GiB+ super images still produce valid skip/fill chunks.
MAX_CHUNK_BYTES = 1024 * 1024 * 1024


class SparseError(FastbootError):
    pass


@dataclass(frozen=True)
class Segment:
    """A range of image blocks with a single storage type."""

    kind: str  # "raw" | "fill" | "skip"
    block: int
    blocks: int
    data_off: int = 0
    data_len: int = 0
    fill: int = 0

    @property
    def end_block(self) -> int:
        return self.block + self.blocks


class ImageSource:
    block_size = DEFAULT_BLOCK_SIZE
    total_blocks = 0

    def segments(self) -> Iterator[Segment]:
        raise NotImplementedError

    def read(self, offset: int, length: int) -> bytes:
        raise NotImplementedError

    def close(self) -> None:
        pass

    def __enter__(self) -> "ImageSource":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class RawSource(ImageSource):
    """A raw disk image, scanned lazily for zero blocks."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._file = open(self.path, "rb")
        self._size = os.fstat(self._file.fileno()).st_size
        if self._size <= 0:
            self._file.close()
            raise SparseError(f"镜像为空: {self.path}")
        self._mm = mmap.mmap(self._file.fileno(), 0, access=mmap.ACCESS_READ)
        self.total_blocks = (self._size + self.block_size - 1) // self.block_size

    def close(self) -> None:
        try:
            self._mm.close()
        except Exception:
            pass
        try:
            self._file.close()
        except Exception:
            pass

    def read(self, offset: int, length: int) -> bytes:
        end = min(offset + length, self._size)
        data = self._mm[offset:end] if offset < self._size else b""
        if len(data) < length:
            data += b"\x00" * (length - len(data))
        return data

    def _is_zero(self, offset: int, length: int) -> bool:
        if length <= 0:
            return True
        return self._mm[offset:offset + length].count(0) == length

    def segments(self) -> Iterator[Segment]:
        block = 0
        block_size = self.block_size
        while block < self.total_blocks:
            offset = block * block_size
            remaining = self._size - offset
            if remaining <= 0:
                break

            # Fast path: a whole 1 MiB window of zeroes becomes one FILL chunk.
            window_len = min(WINDOW, remaining)
            if self._is_zero(offset, window_len):
                blocks = window_len // block_size
                if blocks:
                    yield Segment("fill", block, blocks, fill=0)
                    block += blocks
                    continue

            # Slow path: classify one block, then extend the run.
            length = min(block_size, remaining)
            zero = self._is_zero(offset, length)
            run_end = block + 1
            while run_end < self.total_blocks:
                next_off = run_end * block_size
                next_len = min(block_size, self._size - next_off)
                if self._is_zero(next_off, next_len) != zero:
                    break
                run_end += 1

            blocks = run_end - block
            if zero:
                yield Segment("fill", block, blocks, fill=0)
            else:
                yield Segment(
                    "raw",
                    block,
                    blocks,
                    data_off=offset,
                    data_len=min(blocks * block_size, self._size - offset),
                )
            block = run_end


class SparseSource(ImageSource):
    """An existing Android sparse image."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._file = open(self.path, "rb")
        self._size = os.fstat(self._file.fileno()).st_size
        header = self._file.read(SPARSE_HEADER.size)
        if len(header) != SPARSE_HEADER.size:
            self._file.close()
            raise SparseError(f"sparse 文件头不完整: {self.path}")
        (
            magic,
            major,
            minor,
            file_hdr_sz,
            chunk_hdr_sz,
            blk_sz,
            total_blks,
            total_chunks,
            checksum,
        ) = SPARSE_HEADER.unpack(header)
        if magic != SPARSE_MAGIC:
            self._file.close()
            raise SparseError(f"不是 Android sparse 镜像: {self.path}")
        if major != 1 or minor != 0:
            self._file.close()
            raise SparseError(f"不支持的 sparse 版本 {major}.{minor}: {self.path}")
        if file_hdr_sz < SPARSE_HEADER.size or chunk_hdr_sz < CHUNK_HEADER.size:
            self._file.close()
            raise SparseError("sparse 文件头长度无效")
        if blk_sz <= 0 or blk_sz > 16 * 1024 * 1024:
            self._file.close()
            raise SparseError(f"sparse 块大小无效: {blk_sz}")
        self.block_size = blk_sz
        self.total_blocks = total_blks
        self.image_checksum = checksum
        self._chunk_hdr_sz = chunk_hdr_sz
        self._segments = self._parse(total_chunks, file_hdr_sz)

    def _parse(self, total_chunks: int, file_hdr_sz: int) -> list[Segment]:
        segments: list[Segment] = []
        block = 0
        self._file.seek(file_hdr_sz)
        for _ in range(total_chunks):
            raw = self._file.read(self._chunk_hdr_sz)
            if len(raw) < self._chunk_hdr_sz:
                raise SparseError("sparse 块头不完整")
            chunk_type, _reserved, chunk_sz, total_sz = CHUNK_HEADER.unpack_from(raw, 0)
            if total_sz < self._chunk_hdr_sz:
                raise SparseError("sparse 块长度无效")
            data_offset = self._file.tell()

            if chunk_type == CHUNK_TYPE_RAW:
                blocks = (chunk_sz + self.block_size - 1) // self.block_size
                if blocks <= 0:
                    raise SparseError("sparse RAW 块长度为 0")
                segments.append(
                    Segment(
                        "raw",
                        block,
                        blocks,
                        data_off=data_offset,
                        data_len=chunk_sz,
                    )
                )
                block += blocks
            elif chunk_type == CHUNK_TYPE_FILL:
                if chunk_sz % self.block_size:
                    raise SparseError("sparse FILL 块未按块对齐")
                fill_raw = self._file.read(4)
                if len(fill_raw) != 4:
                    raise SparseError("sparse FILL 数据不完整")
                blocks = chunk_sz // self.block_size
                segments.append(
                    Segment("fill", block, blocks, fill=int.from_bytes(fill_raw, "little"))
                )
                block += blocks
            elif chunk_type == CHUNK_TYPE_DONT_CARE:
                if chunk_sz % self.block_size:
                    raise SparseError("sparse DONTCARE 块未按块对齐")
                blocks = chunk_sz // self.block_size
                if blocks:
                    segments.append(Segment("skip", block, blocks))
                block += blocks
            elif chunk_type == CHUNK_TYPE_CRC32:
                # Optional checksum chunk; it does not cover image blocks.
                pass
            else:
                raise SparseError(f"未知 sparse 块类型 0x{chunk_type:04x}")

            self._file.seek(data_offset + total_sz - self._chunk_hdr_sz)

        if block > self.total_blocks:
            raise SparseError("sparse 数据超过头部声明的块数")
        if block < self.total_blocks:
            segments.append(Segment("skip", block, self.total_blocks - block))
        return segments

    def segments(self) -> Iterator[Segment]:
        yield from self._segments

    def read(self, offset: int, length: int) -> bytes:
        self._file.seek(offset)
        data = self._file.read(length)
        if len(data) < length:
            data += b"\x00" * (length - len(data))
        return data

    def close(self) -> None:
        try:
            self._file.close()
        except Exception:
            pass


def is_sparse_file(path: str | Path) -> bool:
    try:
        with open(path, "rb") as handle:
            head = handle.read(4)
        return len(head) == 4 and int.from_bytes(head, "little") == SPARSE_MAGIC
    except OSError:
        return False


def open_source(path: str | Path) -> ImageSource:
    if is_sparse_file(path):
        return SparseSource(path)
    return RawSource(path)


class _PartBuilder:
    def __init__(self, source: ImageSource, limit: int):
        self.source = source
        self.limit = limit
        self.block_size = source.block_size
        self.total = source.total_blocks
        self.chunks: list[Segment] = []
        self.size = SPARSE_HEADER.size
        self.end = 0
        self.has_data = False

    def _skip_cost(self, blocks: int) -> int:
        if blocks <= 0:
            return 0
        return _chunk_count(blocks * self.block_size) * CHUNK_HEADER.size

    def add(self, segment: Segment) -> int:
        """Add up to ``segment.blocks`` blocks.  Return blocks consumed."""
        if segment.block < self.end:
            overlap = self.end - segment.block
            if overlap >= segment.blocks:
                return segment.blocks
            segment = _slice_segment(segment, overlap, segment.blocks - overlap, self.block_size)

        if segment.kind == "skip":
            # Gaps are materialised only when a data chunk follows.
            return segment.blocks

        gap = self._skip_cost(segment.block - self.end)
        trailing = self._skip_cost(self.total - (segment.block + segment.blocks))

        if segment.kind == "raw":
            take = segment.blocks
            trailing = self._skip_cost(self.total - (segment.block + take))
            available = self.limit - self.size - gap - CHUNK_HEADER.size - trailing
            if available <= 0:
                return 0
            take = min(take, available // self.block_size)
            if take <= 0:
                return 0
            trailing = self._skip_cost(self.total - (segment.block + take))
            if self.size + gap + CHUNK_HEADER.size + take * self.block_size + trailing > self.limit:
                take -= 1
                if take <= 0:
                    return 0
                trailing = self._skip_cost(self.total - (segment.block + take))
            payload = take * self.block_size
            consumed = take
            chunk = Segment(
                "raw",
                segment.block,
                take,
                data_off=segment.data_off,
                data_len=payload,
            )
            chunk_cost = CHUNK_HEADER.size + payload
        elif segment.kind == "fill":
            fill_bytes = segment.blocks * self.block_size
            fill_chunks = _chunk_count(fill_bytes)
            chunk_cost = fill_chunks * (CHUNK_HEADER.size + 4)
            if self.size + gap + chunk_cost + trailing > self.limit:
                return 0
            consumed = segment.blocks
            chunk = Segment(
                "fill", segment.block, segment.blocks, fill=segment.fill
            )
        else:
            return segment.blocks

        self.size += gap + chunk_cost + trailing
        self.end = segment.block + consumed
        self.chunks.append(chunk)
        self.has_data = True
        return consumed

    def build(self) -> bytes:
        if not self.has_data:
            raise SparseError("内部错误：空的 sparse 分片")

        out_chunks: list[bytes] = []
        cursor = 0
        for chunk in self.chunks:
            if chunk.block < cursor:
                trim = cursor - chunk.block
                if trim >= chunk.blocks:
                    continue
                chunk = _slice_segment(chunk, trim, chunk.blocks - trim, self.block_size)
            if chunk.block > cursor:
                for size in _split_sizes((chunk.block - cursor) * self.block_size):
                    out_chunks.append(_skip_chunk(size))
            if chunk.kind == "fill":
                payload = struct.pack("<I", chunk.fill & 0xFFFFFFFF)
                for size in _split_sizes(chunk.blocks * self.block_size):
                    out_chunks.append(
                        CHUNK_HEADER.pack(
                            CHUNK_TYPE_FILL, 0, size, CHUNK_HEADER.size + 4
                        ) + payload
                    )
            else:
                out_chunks.append(self._encode_chunk(chunk))
            cursor = chunk.block + chunk.blocks

        if cursor < self.total:
            for size in _split_sizes((self.total - cursor) * self.block_size):
                out_chunks.append(_skip_chunk(size))

        header = SPARSE_HEADER.pack(
            SPARSE_MAGIC,
            1,
            0,
            SPARSE_HEADER.size,
            CHUNK_HEADER.size,
            self.block_size,
            self.total,
            len(out_chunks),
            0,
        )
        body = header + b"".join(out_chunks)
        if len(body) > self.limit:
            raise SparseError(
                f"内部错误：sparse 分片 {len(body)} 字节超过限制 {self.limit} 字节"
            )
        return body

    def _encode_chunk(self, chunk: Segment) -> bytes:
        if chunk.kind == "skip":
            size = chunk.blocks * self.block_size
            return CHUNK_HEADER.pack(
                CHUNK_TYPE_DONT_CARE, 0, size, CHUNK_HEADER.size
            )

        size = chunk.blocks * self.block_size
        data = self.source.read(chunk.data_off, size)
        if len(data) != size:
            data += b"\x00" * (size - len(data))
        return CHUNK_HEADER.pack(
            CHUNK_TYPE_RAW, 0, size, CHUNK_HEADER.size + size
        ) + data


def _slice_segment(segment: Segment, offset: int, blocks: int, block_size: int) -> Segment:
    if offset < 0 or blocks < 0 or offset + blocks > segment.blocks:
        raise ValueError("segment slice out of range")
    data_off = segment.data_off
    data_len = segment.data_len
    if segment.kind == "raw":
        data_off += offset * block_size
        data_len = max(0, data_len - offset * block_size)
    return Segment(
        kind=segment.kind,
        block=segment.block + offset,
        blocks=blocks,
        data_off=data_off,
        data_len=data_len,
        fill=segment.fill,
    )


def _chunk_count(size: int) -> int:
    if size <= 0:
        return 0
    return (size + MAX_CHUNK_BYTES - 1) // MAX_CHUNK_BYTES


def _split_sizes(size: int) -> list[int]:
    """Split a byte range into sparse-chunk-sized pieces."""
    result: list[int] = []
    remaining = size
    while remaining > MAX_CHUNK_BYTES:
        result.append(MAX_CHUNK_BYTES)
        remaining -= MAX_CHUNK_BYTES
    if remaining > 0:
        result.append(remaining)
    return result


def _skip_chunk(size: int) -> bytes:
    if size <= 0 or size > 0xFFFFFFFF:
        raise SparseError(f"无效的 sparse 跳过长度: {size}")
    return CHUNK_HEADER.pack(CHUNK_TYPE_DONT_CARE, 0, size, CHUNK_HEADER.size)


def iter_sparse_parts(source: ImageSource, limit: int) -> Iterator[bytes]:
    """Yield full-length sparse parts, each at most ``limit`` bytes."""
    if limit < SPARSE_HEADER.size + 2 * CHUNK_HEADER.size + 4:
        raise SparseError(f"max-download-size 太小（{limit} 字节）")
    if source.total_blocks <= 0:
        raise SparseError("镜像没有数据")

    builder = _PartBuilder(source, limit)
    for segment in source.segments():
        if segment.kind == "skip":
            continue
        pending = segment
        while pending.blocks > 0:
            consumed = builder.add(pending)
            if consumed == 0:
                if builder.has_data:
                    yield builder.build()
                    builder = _PartBuilder(source, limit)
                    continue
                # The segment cannot fit even in an empty part.  Try a
                # smaller slice; for FILL chunks this can only happen when the
                # limit is absurdly small.
                max_blocks = _max_blocks_for_empty(pending, source.block_size, limit, source.total_blocks)
                if max_blocks <= 0:
                    raise SparseError(
                        f"无法把镜像放入 max-download-size={limit} 字节的分片"
                    )
                consumed = builder.add(
                    _slice_segment(pending, 0, max_blocks, source.block_size)
                )
                if consumed <= 0:
                    raise SparseError("sparse 分片规划失败")

            if consumed < pending.blocks:
                yield builder.build()
                builder = _PartBuilder(source, limit)
                pending = _slice_segment(pending, consumed, pending.blocks - consumed, source.block_size)
            else:
                break

    if builder.has_data:
        yield builder.build()


def _max_blocks_for_empty(segment: Segment, block_size: int, limit: int, total: int) -> int:
    overhead = SPARSE_HEADER.size + CHUNK_HEADER.size
    if segment.block > 0:
        overhead += CHUNK_HEADER.size
    if segment.kind == "raw":
        overhead += CHUNK_HEADER.size if segment.block + segment.blocks < total else 0
        return max(0, (limit - overhead) // block_size)
    if segment.kind == "fill":
        return segment.blocks if overhead + 4 <= limit else 0
    return segment.blocks


def split_raw_image(path: str | Path, limit: int, max_part_size: Optional[int] = None) -> Iterator[bytes]:
    """Convenience helper used by tests and diagnostics."""
    cap = limit if max_part_size is None else min(limit, max_part_size)
    with open_source(path) as source:
        yield from iter_sparse_parts(source, cap)
