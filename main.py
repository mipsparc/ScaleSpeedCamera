#coding:utf-8

import cv2
import os
import numpy as np
import sys
from contextlib import contextmanager
import time
import urllib.request
import json
from multiprocessing import Process, Array, Value, Queue, freeze_support, sharedctypes
import queue
import tkinter
from tkinter import ttk
from ReaderWorker import ReaderWorker
from MeasureSpeedWorker import MeasureSpeedWorker
from Greeting import Greeting
from Display import DisplayWorker
import platform
OS = platform.system()
if OS == 'Windows':
    import ctypes

# リリースバージョン
version = 1.1
        
def display(frame, last_kph, boxes, fps, a_arr, b_arr, area_height, disp, speed_system):
    for box in boxes:
        cv2.rectangle(frame, (box[0], box[1]), (box[0] + box[2], box[1] + box[3]), (0, 255, 0), 5)

    if last_kph > 0:
        if speed_system == 'kph':
            speed_suffix = 'km/h'
        else:
            speed_suffix = 'MPH'
        kph_area = cv2.getTextSize(f'{last_kph}{speed_suffix}', cv2.FONT_HERSHEY_DUPLEX, 2, 2)[0]
        cv2.rectangle(frame, (0, 0), (kph_area[0] + 70, kph_area[1] + 40), (150, 150 , 150), -1)
        cv2.putText(frame, f'{last_kph}{speed_suffix}', (35, kph_area[1] + 20), cv2.FONT_HERSHEY_DUPLEX, 2, (255, 255, 255), 2)

    if fps > 0:
        fps_area =  cv2.getTextSize(f'{fps}fps', cv2.FONT_HERSHEY_DUPLEX, 1, 1)[0]
        cv2.putText(frame, f'{fps}fps', (35, fps_area[1] + 100), cv2.FONT_HERSHEY_DUPLEX, 1, (255, 255, 255), 1)

    cv2.line(frame, (a_arr[0], a_arr[1]), (a_arr[0], 0), (255, 0, 0), 3)
    cv2.line(frame, (b_arr[0], b_arr[1]), (b_arr[0], 0), (255, 0, 0), 3)
    cv2.line(frame, (0, a_arr[2]), (2000, b_arr[2]), (255, 0, 0), 3)
    cv2.line(frame, (0, a_arr[2] - area_height), (2000, b_arr[2] - area_height), (255, 0, 0), 3)
    
    np.asarray(frame_shared)[:] = frame.flatten()

def createMeasure(frame_shared, speed_shared, a_arr, b_arr, box_q, params, scale, speed_system, camera_width, camera_height):
    measure = Process(target=MeasureSpeedWorker, args=(frame_shared, speed_shared, a_arr, b_arr, box_q, params, scale, speed_system, camera_width, camera_height), daemon=True)
    measure.start()
    return measure

if __name__ == '__main__':
    freeze_support()

    # 旧バージョン判定
    old_ver = False
    try:
        with urllib.request.urlopen('https://api.github.com/repos/mipsparc/ScaleSpeedCamera/releases/latest', timeout=3) as response:
            j = response.read().decode('utf-8')
            latest_version = json.loads(j)['tag_name'][1:]
            if float(latest_version) > version:
                old_ver = True
    except:
        pass
    
    print('ScaleSpeedCamera (鉄道模型車速計測ソフト) by mipsparc')
    print(f'バージョン{version}')
    print('起動中です。しばらくお待ちください……''')

    camera_ids = []
    camera_id_max = -1
    for camera_id in range(4, -1, -1):
        cap = cv2.VideoCapture(camera_id)
        if cap.isOpened():
            camera_ids.append(camera_id)
            cap.release()

    if len(camera_ids) == 0:
        messagebox.showinfo(message='利用できるカメラがありません。\n他のソフトで使用していませんか?')
        sys.exit()
        
    if OS == 'Windows':
        ctypes.windll.shcore.SetProcessDpiAwareness(True)
    
    root = tkinter.Tk()
    greeting = Greeting(root, camera_ids, version, old_ver)
    try:
        camera_id_selected = int(greeting.init_value['camera_id'])
        save_photo = greeting.init_value['save_photo']
        speed_system = greeting.init_value['speed_system']
        scale = greeting.init_value['scale']
    # ウィンドウ閉じた場合
    except AttributeError:
        sys.exit()

    cap = cv2.VideoCapture(camera_id_selected)
    
    camera_width = 1280
    camera_height = 720
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, camera_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_height)
    real_cam_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    real_cam_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    shrink = False
    if real_cam_w != camera_width or real_cam_h != camera_height:
        shrink = True
    
    ret, frame = cap.read()
    if shrink:
        frame = cv2.resize(frame, (camera_height, camera_width))
    frame_shared = sharedctypes.RawArray('B', camera_width * camera_height * 3)
    np.asarray(frame_shared)[:] = frame.flatten()
    
    measure_params = Array('i', [15, 20, 200, int(save_photo), 15])
    disp = Process(target=DisplayWorker, args=(frame_shared, camera_width, camera_height, measure_params))
    disp.start()

    camera_fps = 60
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FPS, camera_fps)
    real_cam_fps = int(cap.get(cv2.CAP_PROP_FPS))
    print(f'{real_cam_fps}fps')
        
    a_arr = Array('i', [-1, -1, -1])
    b_arr = Array('i', [-1, -1, -1])
    
    frame_gray_shared = sharedctypes.RawArray('B', camera_width * camera_height)
    gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    np.asarray(frame_gray_shared)[:] = gray_frame.flatten()
    reader = Process(target=ReaderWorker, args=(frame_gray_shared, a_arr, b_arr, camera_width, camera_height), daemon=True)
    reader.start()
    
    box_q  = Queue()
    boxes = []
    speed_shared = Value('i', -1)

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
        if shrink:
            frame = cv2.resize(frame, (camera_height, camera_width))
        
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        np.asarray(frame_gray_shared)[:] = gray_frame.flatten()
        
        speed = speed_shared.value
        
        try:
            boxes = box_q.get(False)
        except queue.Empty:
            pass
        
        if measure is None or not measure.is_alive():
            measure = createMeasure(frame_gray_shared, speed_shared, a_arr, b_arr, box_q, measure_params, scale, speed_system, camera_width, camera_height)
        
        area_height = measure_params[2]
        
        if display_cnt % 5 == 0:
            display(frame, speed, boxes, fps, a_arr, b_arr, area_height, disp, speed_system)
            display_cnt = 0
        else:
            display_cnt += 1
            
        # ウィンドウを閉じたとき
        if not disp.is_alive():
            cap.release()
            sys.exit()
        
        if cnt_fps <= 0:
            tm.stop()
            fps = int(1.0 / (tm.getTimeSec() / 10.0))
            tm.reset()
            tm.start()
            cnt_fps = 10
        else:
            cnt_fps -= 1
