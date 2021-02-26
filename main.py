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
version = 1.04

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
    raise
except:
    pass
   
print('ScaleSpeedCamera (鉄道模型車速計測ソフト) by mipsparc')
print(f'バージョン{version}')
print('起動中です。しばらくお待ちください……''')

OS = platform.system()
if OS == 'Windows':
    import win32com.client as wincl
    voice = wincl.Dispatch("SAPI.SpVoice")
else:
    import subprocess
    # JPEG破損エラーを抑止する
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

camera_id = 0
camera_width = 1280
camera_height = 720
camera_fps = 30

# Integrated Camera Lenovo ThinkPadでテスト済みの設定
cap = cv2.VideoCapture(camera_id)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, camera_width)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_height)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
cap.set(cv2.CAP_PROP_FPS, camera_fps)
cap.set(cv2.CAP_PROP_CONTRAST, 150)

print('起動しました')

def MeasureSpeed(cap):
    a_center = None
    b_center = None
    avg = None
    train_from = None
    passed_a_time = None
    passed_b_time = None
    cnt_qr = 0
    last_time = 0
    
    # 列車が去るまで(rectがなくなるまで)なにもしない。30フレーム数える
    is_still = 30
    
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
                    qr_save_cnt = 30
            else:
                qr_save_cnt = 30

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
                    elif d.data == b'd':
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
            cv2.imshow('ScaleSpeedCamera',frame)
            if cv2.waitKey(1) & 0xFF == ord('q') or cv2.getWindowProperty('ScaleSpeedCamera', 0) == -1:
                raise KeyboardInterrupt
            continue

        if avg is None:
            avg = frame.copy().astype("float")
            continue

        cv2.accumulateWeighted(frame, avg, 0.4)
        frameDelta = cv2.absdiff(frame, cv2.convertScaleAbs(avg))
        thresh = cv2.threshold(frameDelta, 20, 255, cv2.THRESH_BINARY)[1]
        
        contours, hierarchy = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        max_x = 0
        min_x = 99999
        for i in range(0, len(contours)):
            if len(contours[i]) > 0:
                # 小さいオブジェクトを除去する
                if cv2.contourArea(contours[i]) < 150:
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
                    print('from left')
                elif (a_center + b_center) / 2 < min_x < b_center:
                    train_from = 'right'
                    passed_b_time = time.time()
                    print('from right')
            
            if train_from == 'left' and passed_a_time + 0.5 < time.time():
                if passed_b_time is None:
                    if max_x > b_center:
                        print('passed right')
                        passed_b_time = time.time()
            elif train_from == 'right' and passed_b_time + 0.5 < time.time():
                if passed_a_time is None:
                    if a_center > min_x:
                        print('passed left')
                        passed_a_time = time.time()
                            
            if passed_a_time and (time.time() > passed_a_time + 6):
                break
            if passed_b_time and (time.time() > passed_b_time + 6):
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
            break
        
        cv2.line(frame, (a_bottom_center, a_bottom_center_y), (a_bottom_center, 0), (255, 0, 0), 3)
        cv2.line(frame, (b_bottom_center, b_bottom_center_y), (b_bottom_center, 0), (255, 0, 0), 3)
        cv2.line(frame, (0, a_top), (2000, b_top), (255, 0, 0), 3)
        cv2.line(frame, (0, a_top - 300), (2000, b_top - 300), (255, 0, 0), 3)
        
        cv2.imshow('ScaleSpeedCamera',frame)

        if cv2.waitKey(1) & 0xFF == ord('q') or cv2.getWindowProperty('ScaleSpeedCamera', 0) == -1:
            raise KeyboardInterrupt
        
try:
    while (cap.isOpened()):
        MeasureSpeed(cap)
finally:
    cap.release()
    cv2.destroyAllWindows()
