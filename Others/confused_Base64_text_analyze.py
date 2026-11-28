"""
Base64 混淆字符候选分析工具

针对抄写时将数字误写为字母、或大小写混淆的 Base64 字符串，按字符映射生成候选。
程序每 4 个字符分组，显示各候选解码结果；用户可逐组选取一个或多个候选，
最后组合所选候选，并输出组合后的 Base64、字节和 UTF-8 内容。

使用方法：
运行程序后输入待检查的 Base64 字符串。每组输入一个候选序号（如 1），
或多个候选序号组成的列表（如 [1, 3]）。

注意：
候选映射由 mapDir 预先定义，并非自动识别所有相似字符。各组选项越多，
最终组合数量越大；非有效 UTF-8 的结果会显示为无效。
"""

import base64
from itertools import product
import ast

cyptoStr = "QWIHBLGZZXJSXZNVBZW"
cyptoStr = str(input("input the encodeed string for check:"))
subList = [cyptoStr[i:i+4] for i in range(0,len(cyptoStr),4)]

if len(subList[-1]) == 1:
    print("最后一组的字符数量不是base64，数量不对")
else:
    subList[-1] += "=" * (4 - len(subList[-1]))

mapDir = {
    "A":[4,"a"],
    "B":[8,"b"],
    "C":["c"],
    "D":["d"],
    "E":[3,"e"],
    "F":["f"],
    "G":[6,9,"g"],
    "H":["h"],
    "I":["i",1],
    "J":["j"],
    "K":["k"],
    "L":["l",1],
    "M":["m"],
    "N":["n"],
    "O":[0,"o"],
    "P":["p"],
    "Q":[9,"q"],
    "R":["r"],
    "S":[5,"s"],
    "T":[7,"t"],
    "U":["u"],
    "V":["v"],
    "W":["w"],
    "X":["x"],
    "Y":["y"],
    "Z":[2,"z"]
}

# 先处理编码混淆，生成不同候选
possibleList=[]
for i, group in enumerate(subList, start=1):
    letters = group.rstrip("=")
    padding = group[len(letters):]
    choices = [[char] + mapDir.get(char, []) for char in letters]
    groupCandidates = [
        "".join(str(char) for char in combination) + padding
        for combination in product(*choices)
    ]
    possibleList.append(groupCandidates)
    # print(f"第{i}组候选：")
    # for candidate in groupCandidates:
    #     print(candidate)

# 获取每一个小组别下的可能解码然后进行组合
selectedCandidatesByGroup = []
for i, group in enumerate(possibleList, start=1):
    # 获取第i组的可能解码候选
    print(f"第{i}组Base64解码候选：")

    decodedCandidates = []
    for encodedStr in group:
        decodedBytes = base64.b64decode(encodedStr, validate=True)
        try:
            decodedText = decodedBytes.decode("utf-8")
        except UnicodeDecodeError:
            decodedText = f"<暂不能单独解码，字节：{decodedBytes.hex()}>"
        decodedCandidates.append((encodedStr, decodedBytes, decodedText))

    for option, (encodedStr, _, decodedText) in enumerate(decodedCandidates, start=1):
        print(f"{option}. {decodedText!r} (Base64: {encodedStr})")
    
    # 选择解码候选
    while True:
        raw = input(f"请输入第{i}组要保留的候选序号，例如 [1, 3]：")
        try:
            selectedOptions = ast.literal_eval(raw)
        except (SyntaxError, ValueError):
            print("请输入序号，例如 1 或 [1, 3]。")
            continue

        if type(selectedOptions) is int:
            selectedOptions = [selectedOptions]

        if (
            isinstance(selectedOptions, list)
            and selectedOptions
            and all(
                type(option) is int and 1 <= option <= len(decodedCandidates)
                for option in selectedOptions
            )
            and len(set(selectedOptions)) == len(selectedOptions)
        ):
            selectedCandidatesByGroup.append(
                [decodedCandidates[option - 1] for option in selectedOptions]
            )
            break
        print(
            f"请输入 1 到 {len(decodedCandidates)} 之间不重复的一个或多个序号。"
        )

# 组合候选
print("各组选择完成，逐个输出组合：")
for i, combination in enumerate(product(*selectedCandidatesByGroup), start=1):
    encodedCombination = "".join(candidate[0] for candidate in combination)
    resultBytes = b"".join(candidate[1] for candidate in combination)
    print(f"组合 {i}:")
    print(f"  Base64: {encodedCombination}")
    print(f"  字节(hex): {resultBytes.hex()}")
    try:
        result = resultBytes.decode("utf-8")
        print(f"  UTF-8: {result!r}")
    except UnicodeDecodeError:
        print("  UTF-8: 无效")
