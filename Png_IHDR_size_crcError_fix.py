# 默认IHDR CRC校验存在错误，
# 并且假设width和height其中一个存在问题，然后尝试解除对应的长和宽

"""通过 PNG 解压数据长度和原 IHDR CRC 尝试恢复宽度或高度。"""
import argparse
import struct
import zlib
from pathlib import Path

# PNG 文件开头固定的 8 字节签名，用于初步识别 PNG。
SIGNATURE = b'\x89PNG\r\n\x1a\n'
# PNG 规范规定的颜色类型：二进制位 1、2、4 分别表示
# 使用调色板、彩色、包含 Alpha 通道；并非所有组合都有效。
# 0：灰度；2：RGB；3：调色板索引；4：灰度 + Alpha；6：RGBA。
# 字典的值是每个像素存储的样本数量；索引颜色使用一个索引样本。
CHANNELS = {0: 1, 
            2: 3, 
            3: 1, 
            4: 2, 
            6: 4}
# PNG 颜色类型对应允许的位深，用于检查 IHDR 字段。
DEPTHS = {0: {1, 2, 4, 8, 16}, 
          2: {8, 16}, 
          3: {1, 2, 4, 8}, 
          4: {8, 16},
          6: {8, 16}}
# PNG 宽度或高度允许的最大值（2 的 31 次方减 1）。
MAX_DIM = 2**31 - 1
# 本脚本设置的解压数据上限：256 MiB，并非 PNG 格式限制。
MAX_RAW = 256 * 1024 * 1024


def inspect_png(data):
    if not data.startswith(SIGNATURE):
        raise ValueError('不是有效的 PNG 文件签名')
    
    pos, ihdr, target_crc, compressed = 8, None, None, bytearray()
    found_end = False

    while pos + 12 <= len(data):
        length = int.from_bytes(data[pos:pos + 4], 'big')
        end = pos + 12 + length

        if end > len(data):
            raise ValueError('数据块长度超过文件范围')
        
        kind, payload = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + length]
        stored = int.from_bytes(data[pos + 8 + length:end], 'big')

        if ihdr is None:
            if kind != b'IHDR' or length != 13:
                raise ValueError('第一个数据块不是长度为 13 的 IHDR')
            
            ihdr, target_crc = bytearray(kind + payload), stored

        elif kind == b'IHDR':
            raise ValueError('发现重复的 IHDR')
        
        elif kind == b'IDAT':
            if zlib.crc32(kind + payload) != stored:
                raise ValueError('IDAT CRC 不匹配，无法可靠推断尺寸')
            
            compressed.extend(payload)

        elif kind == b'IEND':
            found_end = True
            break

        pos = end

    if not found_end or not compressed:
        raise ValueError('缺少 IDAT 或 IEND')
    
    width, height, depth, color, compression, filtering, interlace = struct.unpack('>IIBBBBB', ihdr[4:])

    if color not in DEPTHS or depth not in DEPTHS[color] or compression != 0 or filtering != 0:
        raise ValueError('位深、颜色类型、压缩或过滤方法不受支持')
    
    if interlace != 0:
        raise ValueError('暂不支持隔行 PNG')
    
    dec = zlib.decompressobj()
    raw = dec.decompress(compressed, MAX_RAW + 1)

    if len(raw) > MAX_RAW or dec.unconsumed_tail:
        raise ValueError('解压数据超过 256 MiB 限制')
    
    if not dec.eof or dec.unused_data:
        raise ValueError('IDAT 压缩数据不完整或含有多余数据')
    
    return ihdr, target_crc, width, height, depth * CHANNELS[color], raw


def candidates(width, height, bits, raw):
    """分别假设当前宽度或高度正确，推导另一个尺寸。"""
    size = len(raw)
    found = set()

    if 0 < width <= MAX_DIM:
        row_size = (width * bits + 7) // 8 + 1
        if size % row_size == 0 and 0 < size // row_size <= MAX_DIM:
            found.add((width, size // row_size))

    if 0 < height <= MAX_DIM and size % height == 0:
        row_bytes = size // height - 1

        if row_bytes > 0:
            # ceil(width * bits / 8) == row_bytes；低位深时可能有多个宽度。
            lower = ((row_bytes - 1) * 8) // bits + 1 # 假设像素只在字节的前面存在一个像素
            upper = (row_bytes * 8) // bits # 假设像素都占满字节了
            for candidate_width in range(max(1, lower), min(MAX_DIM, upper) + 1):
                found.add((candidate_width, height))

    return sorted(found)


def main():
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument('input', 
                        type=Path, 
                        help='原 PNG 文件')
    
    parser.add_argument('-o', 
                        '--output', 
                        type=Path, 
                        help='把匹配的结果保存为新文件（可选）')
    args = parser.parse_args()

    try:
        data = args.input.read_bytes()
        ihdr, target, width, height, bits, raw = inspect_png(data)

        print(f'当前尺寸：{width} × {height}；解压后数据：{len(raw)} 字节')
        print(f'保存的 IHDR CRC：{target:08X}；当前计算值：{zlib.crc32(ihdr):08X}')

        if zlib.crc32(ihdr) == target:
            print('IHDR CRC 已匹配；这不保证尺寸一定正确。可能同时更改了CRC')

        matches = []

        for w, h in candidates(width, height, bits, raw):
            candidate = bytearray(ihdr)
            candidate[4:12] = struct.pack('>II', w, h)
            crc = zlib.crc32(candidate)
            row_size = (w * bits + 7) // 8 + 1
            filters_ok = all(raw[pos] <= 4 for pos in range(0, len(raw), row_size))

            print(f'候选尺寸：{w} × {h}；CRC：{crc:08X}；行过滤类型：{"正常" if filters_ok else "异常"}')
            
            if crc == target and filters_ok:
                matches.append((w, h))
        if not matches:
            print('没有找到符合条件的候选；可能宽高都被修改，或其他假设不成立。')
            return 1
        
        if args.output:
            if len(matches) != 1:
                raise ValueError('存在多个匹配候选，请人工确认')
            
            if args.output.resolve() == args.input.resolve():
                raise ValueError('输出路径不能与原文件相同')
            
            result = bytearray(data)
            result[16:24] = struct.pack('>II', *matches[0])

            with args.output.open('xb') as out:
                out.write(result)
            print(f'已保存新文件：{args.output}')
        else:
            print('只做检查；指定 -o 新文件路径可保存结果。')
        return 0
    except (OSError, ValueError, zlib.error, struct.error) as exc:
        print(f'无法处理：{exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
