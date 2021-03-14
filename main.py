#coding:utf-8

import cv2
import os
import numpy as np
import sys
from contextlib import contextmanager
import time
import urllib.request
import json
from multiprocessing import Process, Array, Value, Queue, freeze_support
import queue
import tkinter
from tkinter import ttk, messagebox
from ReaderWorker import ReaderWorker
from MeasureSpeedWorker import MeasureSpeedWorker
from Greeting import Greeting

# リリースバージョン
version = 1.1

# 対応スケール
'''
N: 1/160
HO(略号H): 1/80
Z: 1/220
'''

class WindowChange:
    @classmethod
    def changeRectSize(self, num):
        self.rect_size = num

    # weightの10倍
    @classmethod
    def changeWeight(self, num):
        self.weight = num
        
    @classmethod
    def changeHeight(self, num):
        self.area_height = num
        
    @classmethod
    def changeQrLength(self, num):
        self.qr_length = num
        
def display(frame, last_kph, boxes, fps, a_arr, b_arr, area_height):
    for box in boxes:
        cv2.rectangle(frame, (box[0], box[1]), (box[0] + box[2], box[1] + box[3]), (0, 255, 0), 5)

    if last_kph > 0:
        kph_area = cv2.getTextSize(f'{last_kph}km/h', cv2.FONT_HERSHEY_DUPLEX, 2, 2)[0]
        cv2.rectangle(frame, (0, 0), (kph_area[0] + 70, kph_area[1] + 40), (150, 150 , 150), -1)
        cv2.putText(frame, f'{last_kph}km/h', (35, kph_area[1] + 20), cv2.FONT_HERSHEY_DUPLEX, 2, (255, 255, 255), 2)

    if fps > 0:
        fps_area =  cv2.getTextSize(f'{fps}fps', cv2.FONT_HERSHEY_DUPLEX, 1, 1)[0]
        cv2.putText(frame, f'{fps}fps', (35, fps_area[1] + 100), cv2.FONT_HERSHEY_DUPLEX, 1, (255, 255, 255), 1)

    cv2.line(frame, (a_arr[0], a_arr[1]), (a_arr[0], 0), (255, 0, 0), 3)
    cv2.line(frame, (b_arr[0], b_arr[1]), (b_arr[0], 0), (255, 0, 0), 3)
    cv2.line(frame, (0, a_arr[2]), (2000, b_arr[2]), (255, 0, 0), 3)
    cv2.line(frame, (0, a_arr[2] - area_height), (2000, b_arr[2] - area_height), (255, 0, 0), 3)
    
    cv2.imshow('ScaleSpeedCamera',frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q') or cv2.getWindowProperty('ScaleSpeedCamera', 0) == -1:
        print('終了しています。しばらくお待ちください…')
        cap.release()
        cv2.destroyAllWindows()
        sys.exit()

def createMeasure(frame_q, kph_shared, a_arr, b_arr, box_q, scale_shared, params):
    measure = Process(target=MeasureSpeedWorker, args=(frame_q, kph_shared, a_arr, b_arr, box_q, scale_shared, params))
    measure.start()
    return measure

if __name__ == '__main__':
    freeze_support()
        
    # 最新バージョン確認
    try:
        with urllib.request.urlopen('https://api.github.com/repos/mipsparc/ScaleSpeedCamera/releases/latest', timeout=3) as response:
            j = response.read().decode('utf-8')
            latest_version = json.loads(j)['tag_name'][1:]
            if float(latest_version) > version:
                print('新しいバージョンが出ています。以下よりダウンロードをお願いします。')
                print('https://github.com/mipsparc/ScaleSpeedCamera/releases')
                print()
                input('このまま起動するには、Enterキーを押してください')
                print()
            else:
                print('最新のバージョンです')
    except KeyboardInterrupt:
        sys.exit()
    except:
        pass
    
    print('ScaleSpeedCamera (鉄道模型車速計測ソフト) by mipsparc')
    print(f'バージョン{version}')
    print('起動中です。しばらくお待ちください……''')

    camera_id_max = -1
    for camera_id in range(4, -1, -1):
        cap = cv2.VideoCapture(camera_id)
        if cap.isOpened():
            camera_id_max = camera_id
            cap.release()
            break

    if camera_id_max == -1:
        messagebox.showinfo(message='利用できるカメラがありません。\n他のソフトで使用していませんか?')
        sys.exit()
    
    root = tkinter.Tk()
    greeting = Greeting(root, camera_id_max)
    print(greeting.init_value)
    camera_id_selected = int(greeting.init_value['camera_id'])
    save_photo = greeting.init_value['save_photo']

    cap = cv2.VideoCapture(camera_id_selected)

    camera_width = 1280
    camera_height = 720
    camera_fps = 60
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, camera_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_height)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FPS, camera_fps)
    real_cam_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    real_cam_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    real_cam_fps = int(cap.get(cv2.CAP_PROP_FPS))
    print(f'{real_cam_w}x{real_cam_h} {real_cam_fps}fps')

    print('カメラの初期化が完了しました')
    print()
    
    cv2.namedWindow('ScaleSpeedCamera')

    frame_q_measure = Queue()
    frame_q_reader = Queue()
    box_q  = Queue()
    boxes = []
    kph_shared = Value('i', -1)
    scale_shared = Value('u', 'N')
    a_arr = Array('i', [-1, -1, -1])
    b_arr = Array('i', [-1, -1, -1])
    measure_params = Array('i', [15, 20, 200, int(save_photo), 15])

    cv2.createTrackbar('MinRect', 'ScaleSpeedCamera', 15, 300, WindowChange.changeRectSize)
    cv2.createTrackbar('Weight', 'ScaleSpeedCamera', 20, 100, WindowChange.changeWeight)
    cv2.createTrackbar('Height', 'ScaleSpeedCamera', 200, 400, WindowChange.changeHeight)
    cv2.createTrackbar('Barcode', 'ScaleSpeedCamera', 15, 100, WindowChange.changeQrLength)
    WindowChange.changeRectSize(15)
    WindowChange.changeWeight(20)
    WindowChange.changeHeight(200)
    WindowChange.changeQrLength(15)

    # fps計測
    tm = cv2.TickMeter()
    tm.start()
    cnt_fps = 10
    fps = -1

    measure = None
    reader = None
    
    display_cnt = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if ret == False:
            continue
                
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_q_measure.put(gray_frame)
        frame_q_reader.put(gray_frame)
        kph = kph_shared.value
        
        measure_params[0] = WindowChange.rect_size
        measure_params[1] = WindowChange.weight + 1
        measure_params[2] = WindowChange.area_height
        measure_params[4] = WindowChange.qr_length
        
        try:
            boxes = box_q.get(False)
        except queue.Empty:
            pass
        
        area_height = WindowChange.area_height
        
        if display_cnt % 5 == 0:
            display(frame, kph, boxes, fps, a_arr, b_arr, area_height)
            display_cnt = 0
        else:
            display_cnt += 1
        
        if reader is None:
            reader = Process(target=ReaderWorker, args=(frame_q_reader, a_arr, b_arr, scale_shared))
            reader.start()
        
        if measure is None or not measure.is_alive():
            measure = createMeasure(frame_q_measure, kph_shared, a_arr, b_arr, box_q, scale_shared, measure_params)
        
        if cnt_fps <= 0:
            tm.stop()
            fps = int(1.0 / (tm.getTimeSec() / 10.0))
            tm.reset()
            tm.start()
            cnt_fps = 10
        else:
            cnt_fps -= 1
