from pyzbar.pyzbar import decode, ZBarSymbol
import numpy as np
import cv2
import os
import sys
from contextlib import contextmanager
import time
import platform
import urllib.request
import json

# リリースバージョン
version = 1.05

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

OS = platform.system()
if OS == 'Windows':
    import win32com.client as wincl
    voice = wincl.Dispatch("SAPI.SpVoice")

import subprocess
import tempfile
@contextmanager
def stderr_redirected(to=os.devnull):
    fd = sys.stderr.fileno()

    ##### assert that Python and C stdio write using the same file descriptor
    ####assert libc.fileno(ctypes.c_void_p.in_dll(libc, "stdout")) == fd == 1

    def _redirect_stderr(to):
        sys.stderr.close() # + implicit flush()
        os.dup2(to.fileno(), fd) # fd writes to 'to' file
        sys.stderr = os.fdopen(fd, 'w') # Python writes to fd

    with os.fdopen(os.dup(fd), 'w') as old_stderr:
        with open(to, 'w') as file:
            _redirect_stderr(to=file)
        try:
            yield # allow code to be run with the redirected stdout
        finally:
            _redirect_stderr(to=old_stderr) # restore stdout.
                                            # buffering and flags such as
                                            # CLOEXEC may be different

def speak(speech_text):
    if OS == 'Windows':
        voice.Speak(speech_text)
    else:
        subprocess.run(f"echo '{speech_text}' | open_jtalk -x /var/lib/mecab/dic/open-jtalk/naist-jdic -m /usr/share/hts-voice/nitech-jp-atr503-m001/nitech_jp_atr503_m001.htsvoice -ow /dev/stdout | aplay --quiet", shell=True)

def show(cv, frame):
    cv.imshow('ScaleSpeedCamera',frame)
    if cv.waitKey(1) & 0xFF == ord('q') or cv.getWindowProperty('ScaleSpeedCamera', 0) == -1:
        print('終了します')
        sys.exit()
        
def changeContrast(num):
    cap.set(cv2.CAP_PROP_CONTRAST, num)

def changeRectSize(num):
    global rect_size
    rect_size = num

def changeWeight(num):
    global weight
    weight = max((num + 1) / 10 - 0.1, 0.1)

camera_id_max = -1
for camera_id in range(4, -1, -1):
    with stderr_redirected():
        cap = cv2.VideoCapture(camera_id)
        if cap.isOpened():
            camera_id_max = camera_id
            cap.release()
            break

if camera_id_max < 0:
    print('カメラが検出できませんでした。')
    sys.exit()
    
if camera_id_max > 0:
    print('複数のカメラが検出されました。どのカメラを使いますか?"')
    for i in range(camera_id_max + 1):
        print(f'カメラID: {i}')
    camera_id_selected = int(input('カメラID(数字)を入力してEnter> '))
else:
    camera_id_selected = camera_id_max

cap = cv2.VideoCapture(camera_id_selected)

camera_width = 1280
camera_height = 720
camera_fps = 30
cap.set(cv2.CAP_PROP_FRAME_WIDTH, camera_width)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_height)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
cap.set(cv2.CAP_PROP_FPS, camera_fps)
print('起動しました')
print()

cv2.namedWindow('ScaleSpeedCamera')
changeContrast(80)
cv2.createTrackbar('Contrast', 'ScaleSpeedCamera', 80 , 300, changeContrast)
changeRectSize(150)
cv2.createTrackbar('MinRect', 'ScaleSpeedCamera', 50 , 300, changeRectSize)
changeWeight(3)
cv2.createTrackbar('Weight', 'ScaleSpeedCamera', 3 , 5, changeWeight)

last_kph = None

def MeasureSpeed(cap):
    a_center = None
    b_center = None
    avg = None
    train_from = None
    passed_a_time = None
    passed_b_time = None
    cnt_qr = 0
    last_time = 0
    global last_kph
    global rect_size
    global weight
    
    # 列車が去るまで(rectがなくなるまで)なにもしない。20フレーム数える
    is_still = 20
    
    qr_save_cnt = 0
    
    while True:     
        if OS == 'Windows':
            ret, frame = cap.read()
        else:
            with stderr_redirected():
                ret, frame = cap.read()
        
        if ret == False:
            continue
            
        if cnt_qr % 5 == 0 or not (a_center and b_center):
            qrdata = decode(frame, symbols=[ZBarSymbol.QRCODE])
            if len(qrdata) < 2:
                qr_save_cnt -= 1
                if qr_save_cnt <= 0:
                    a_center = None
                    b_center = None
                    qr_save_cnt = 40
            else:
                qr_save_cnt = 40

            scale = 'N'
            for d in qrdata:
                if d.data == b'A':
                    a_center = int((d.polygon[0].x + d.polygon[1].x + d.polygon[2].x + d.polygon[3].x) / 4)
                    a_center_y = int((d.polygon[0].y + d.polygon[1].y + d.polygon[2].y + d.polygon[3].y) / 4)
                    a_top = d.rect.top
                    a_bottom_center = int((d.polygon[0].x + d.polygon[1].x) / 2)
                    a_bottom_center_y = int((d.polygon[0].y + d.polygon[1].y) / 2)

                if d.data == b'B' or d.data == b'C' or d.data == b'D':
                    if d.data == b'C':
                        scale = 'HO'
                    elif d.data == b'D':
                        scale = 'Z'
                    b_center = int((d.polygon[0].x + d.polygon[1].x + d.polygon[2].x + d.polygon[3].x) / 4)
                    b_center_y = int((d.polygon[0].y + d.polygon[1].y + d.polygon[2].y + d.polygon[3].y) / 4)
                    b_top = d.rect.top
                    b_bottom_center = int((d.polygon[1].x + d.polygon[2].x) / 2)
                    b_bottom_center_y = int((d.polygon[1].y + d.polygon[2].y) / 2)
            
            cnt_qr = 1
        else:
            cnt_qr += 1

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # QRコードが認識できなかった場合
        if not (a_center and b_center):
            show(cv2, frame)
            continue

        if avg is None:
            avg = frame.copy().astype("float")
            continue

        cv2.accumulateWeighted(frame, avg, weight)
        frameDelta = cv2.absdiff(frame, cv2.convertScaleAbs(avg))
        thresh = cv2.threshold(frameDelta, 40, 255, cv2.THRESH_TOZERO)[1]
        
        contours, hierarchy = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        max_x = 0
        min_x = 99999
        for i in range(0, len(contours)):
            if len(contours[i]) > 0:
                # 小さいオブジェクトを除去する
                if cv2.contourArea(contours[i]) < rect_size:
                    continue

                rect = contours[i]
                x, y, w, h = cv2.boundingRect(rect)
                
                # 範囲外を無視する
                if y > int((a_top + b_top) / 2):
                    continue
                if y + h < a_top - 300:
                    continue
                
                #線路の微妙な部分を排除する
                if h < 10:
                    continue
                if w > 100:
                    continue
                
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 5)
                
                max_x = int(max(max_x, x + w))
                if max_x == x + w:
                    max_x = x
                min_x = int(min(min_x, x))
                if min_x == x:
                    min_x = x
                    min_x_bottom = y + h
        
        if max_x != 0:
            if train_from is None and is_still <= 0:                        
                if a_center < max_x < (a_center + b_center) / 2:
                    train_from = 'left'
                    passed_a_time = time.time()
                    print('列車が左から来ました')
                elif (a_center + b_center) / 2 < min_x < b_center:
                    train_from = 'right'
                    passed_b_time = time.time()
                    print('列車が右から来ました')
            
            if train_from == 'left' and passed_a_time + 0.5 < time.time():
                if passed_b_time is None:
                    if max_x > b_center:
                        print('右を通過しました')
                        passed_b_time = time.time()
            elif train_from == 'right' and passed_b_time + 0.5 < time.time():
                if passed_a_time is None:
                    if a_center > min_x:
                        print('左を通過しました')
                        passed_a_time = time.time()
                            
            if passed_a_time and (time.time() > passed_a_time + (15 - (weight-0.1) * 20)):
                break
            if passed_b_time and (time.time() > passed_b_time + (15 - (weight-0.1) * 20)):
                break
        else:
            is_still -= 1

        if passed_a_time is not None and passed_b_time is not None:
            passing_time = abs(passed_a_time - passed_b_time)
            qr_length = 0.15
            if scale == 'N':
                kph = int((qr_length / passing_time) * 3.6 * 150)
            elif scale == 'HO':
                kph = int((qr_length / passing_time) * 3.6 * 80)
            else: # Z
                kph = int((qr_length / passing_time) * 3.6 * 220)
            print(f'時速{kph}キロメートルです')
            speak(f'時速{kph}キロメートルです')
            last_kph = kph
            break

        if last_kph:
            text_area =  cv2.getTextSize(f'{last_kph}km/h', cv2.FONT_HERSHEY_DUPLEX, 3, 3)[0]
            cv2.rectangle(frame, (0, 0), (text_area[0] + 70, text_area[1] + 40), (150, 150 , 150), -1)
            cv2.putText(frame, f'{last_kph}km/h', (35, text_area[1] + 20), cv2.FONT_HERSHEY_DUPLEX, 3, (0, 255, 0), 3)
        cv2.line(frame, (a_bottom_center, a_bottom_center_y), (a_bottom_center, 0), (255, 0, 0), 3)
        cv2.line(frame, (b_bottom_center, b_bottom_center_y), (b_bottom_center, 0), (255, 0, 0), 3)
        cv2.line(frame, (0, a_top), (2000, b_top), (255, 0, 0), 3)
        cv2.line(frame, (0, a_top - 300), (2000, b_top - 300), (255, 0, 0), 3)
        show(cv2, frame)

while (cap.isOpened()):
    MeasureSpeed(cap)
