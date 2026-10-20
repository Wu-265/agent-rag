"""
生成 B类(文件边界)测试所需的异常测试文件。
每个文件对应一种边界场景，供 run_edge_file_test.py 调用 analyze_file 测试。
"""
import os
import random

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_files")
os.makedirs(OUT_DIR, exist_ok=True)


def write_bytes(name: str, data: bytes):
    path = os.path.join(OUT_DIR, name)
    with open(path, "wb") as f:
        f.write(data)
    print(f"  生成 {name} ({len(data)} 字节)")


# 1. 空文件（0字节）
write_bytes("empty.txt", b"")

# 2. 乱码/二进制伪装成 csv（用随机字节，保证非文本）
random.seed(42)
write_bytes("binary_garbage.csv", bytes(random.randint(0, 255) for _ in range(5000)))

# 3. 正常CSV（对照组）
normal_csv = "name,age,score\nAlice,25,88.5\nBob,30,92.0\nCarol,22,85.5\n".encode("utf-8")
write_bytes("normal.csv", normal_csv)

# 4. 只有表头无数据的CSV
write_bytes("empty_header.csv", "name,age,score\n".encode("utf-8"))

# 5. 半截/损坏CSV（正常开头 + 乱码尾巴）
good_part = "name,age,score\nAlice,25,88.5\nBob,30,".encode("utf-8")
bad_part = bytes(random.randint(128, 255) for _ in range(2000))
write_bytes("broken.csv", good_part + bad_part)

# 6. 超大文件（>20MB，测大小上限——注意 analyze_file 本身不检查大小，
#    但为了模拟 app.py 的 MAX_FILE_SIZE 拦截，先造一个，脚本里可单独测）
big = (b"x" * 1024 * 1024 * 21)  # 21MB
write_bytes("huge.txt", big)

# 7. 编码错误：把utf-8中文用错误方式写，模拟乱码
#    这里故意用 latin-1 无法解码的字节组合
garbled_bytes = "这是一个正常的中文文本，用来测试编码问题。".encode("utf-8")
# 每隔几个字节插入一个非法字节，制造大量乱码
garbled = bytearray()
for i, b in enumerate(garbled_bytes):
    garbled.append(b)
    if i % 3 == 0:
        garbled.append(0x80)  # 插入非法UTF-8字节
write_bytes("encoding_garbled.txt", bytes(garbled))

print("\n全部测试文件生成完成。")
print(f"目录: {OUT_DIR}")
