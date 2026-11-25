import cv2
import argparse
from pathlib import Path

"""解码二维码"""

def decodeQrCode(path):
    # flag of reading img process
    readFlag = True 

    # read the picture
    img = cv2.imread(str(path))
    if img is None:
        readFlag = False
        return readFlag,None,None
    
    # decode the picture
    decoder = cv2.QRCodeDetector()
    # return the result
    data,point,straight_qrcode = decoder.detectAndDecode(img)

    # identify the process of decoding
    decodeFlag = bool(data)

    return readFlag,decodeFlag,data

def main():
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        'input',
        type=Path,
        help="input Qrcode picture"
    )

    args = parser.parse_args()

    readFlag,decodeFlag,data = decodeQrCode(args.input)

    if readFlag and decodeFlag:
        print(f"Decoded data : {data}")
        return 0
    elif not readFlag:
        print("文件读取失败")
        return 1
    elif not decodeFlag:
        print("解码失败")
        return 1
    else:
        print("unknown error")
        return 1

if __name__ == '__main__':
    raise SystemExit(main())