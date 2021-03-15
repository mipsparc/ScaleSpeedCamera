#coding:utf-8

import time
from pylibdmtx.pylibdmtx import decode, DmtxSymbolSize
import queue
import cv2
import sys
import numpy as np

def ReaderWorker(frame_shared, a_arr, b_arr, real_cam_w, real_cam_h):
    last_a_update = 0
    last_b_update = 0
    a_center_y = -1
    b_center_y = -1
    a_top = -1
    b_top = -1
    
    while True:
        frame = np.array(frame_shared, dtype=np.uint8).reshape(real_cam_h, real_cam_w)
        
        # 5秒間バーコードを検出できなかったら初期化する
        if last_a_update + 5 < time.time() or last_b_update + 5 < time.time():
            a_center = -1
            b_center = -1

        ret, preprocessed = cv2.threshold(frame, 170, 255, cv2.THRESH_BINARY)
        
        codedata = decode(preprocessed, timeout=300, max_count=2, shape=DmtxSymbolSize.DmtxSymbolSquareAuto)

        for d in codedata:
            if d.data == b'A':
                a_center = int(d.rect.left + d.rect.width/2)
                a_center_y = real_cam_h - int(d.rect.top + d.rect.height/2)
                a_top = real_cam_h - d.rect.top - d.rect.height
                last_a_update = time.time()

            if d.data == b'B' or d.data == b'C' or d.data == b'D':
                b_center = int(d.rect.left + d.rect.width/2)
                b_center_y = real_cam_h - int(d.rect.top + d.rect.height/2)
                b_top = real_cam_h - d.rect.top - d.rect.height
                last_b_update = time.time()
                
        a_arr[0] = a_center
        a_arr[1] = a_center_y
        a_arr[2] = a_top
        b_arr[0] = b_center
        b_arr[1] = b_center_y
        b_arr[2] = b_top
