from pylibdmtx.pylibdmtx import decode
import numpy as np
import cv2
import os
import sys
from contextlib import contextmanager
import time
import platform
import urllib.request
import json
import subprocess
import tempfile
from multiprocessing import Process, Queue, Array, Value

# リリースバージョン
version = 1.07

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
        subprocess.Popen(f"echo '{speech_text}' | open_jtalk -x /var/lib/mecab/dic/open-jtalk/naist-jdic -m /usr/share/hts-voice/nitech-jp-atr503-m001/nitech_jp_atr503_m001.htsvoice -ow /dev/stdout | aplay --quiet", shell=True)

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
    
def changeHeight(num):
    global next_area_height
    next_area_height = num

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

cv2.namedWindow('ScaleSpeedCamera')

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

changeRectSize(150)
cv2.createTrackbar('MinRect', 'ScaleSpeedCamera', 150 , 300, changeRectSize)
changeWeight(3)
cv2.createTrackbar('Weight', 'ScaleSpeedCamera', 3 , 5, changeWeight)
changeHeight(300)
cv2.createTrackbar('Height', 'ScaleSpeedCamera', 300, 400, changeHeight)

def MeasureSpeedWorker(frame_q, kph_shared, a_arr, b_arr):
    avg = None
    train_from = None
    passed_a_time = None
    passed_b_time = None
    last_time = 0

    #TODO
    next_area_height = 300
    last_detect_area_height = next_area_height

    #global rect_size
    #global weight
    rect_size = 150
    weight = 0.4

    # 列車が去るまで(rectがなくなるまで)なにもしない。20フレーム数える
    is_still = 20

    detect_wait_cnt = 10

    while True:
        frame = frame_q.get(True, 1)
        
        a_center = a_arr[0]
        a_center_y = a_arr[1]
        a_top = a_arr[2]
        
        b_center = b_arr[0]
        b_center_y = b_arr[1]
        b_top = b_arr[2]
        
        print(a_arr[0], b_arr[0])
        
        # 明るさを平準化する
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        h,s,v = cv2.split(hsv)
        # https://qiita.com/s-kajioka/items/9c9fc6c0e9e8a9d05800
        v = ( v - np.mean(v)) / np.std(v) * 30 + 90
        frame = np.array(v, dtype=np.uint8)
            
        # 2次元地点検知コードが認識できなかった場合
        if a_center == -1 or b_center == -1:
            detect_wait_cnt = 10
            continue
        else:
            #認識し始めから検出まで10フレーム待つ
            if detect_wait_cnt > 0:
                detect_wait_cnt -= 1
                continue
            elif detect_wait_cnt == 0:
                # 検出域を制限する
                detect_area_top = max(int((a_top + b_top) / 2) - next_area_height, 1)
                detect_area_bottom = int((a_top + b_top) / 2)
                detect_area_left = 0
                detect_area_right = real_cam_w
                detect_area = frame[detect_area_top:detect_area_bottom, detect_area_left:detect_area_right]
                detect_area_height = detect_area_top - detect_area_bottom

        if avg is None or area_height != next_area_height or last_detect_area_height != detect_area_height:
            avg = detect_area.copy().astype("float")
            area_height = next_area_height
            last_detect_area_height = detect_area_height
            continue

        cv2.accumulateWeighted(detect_area, avg, weight)
        frameDelta = cv2.absdiff(detect_area, cv2.convertScaleAbs(avg))
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
                
                #線路の微妙な部分を排除する
                if h < 15:
                    continue
                if w > 100:
                    continue
                    
                y += detect_area_top
                
                #cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 5)
                
                max_x = int(max(max_x, x + w))
                if max_x == x + w:
                    max_x_x = x
                    max_x_w = w
                min_x = int(min(min_x, x))
                if min_x == x:
                    min_x_x = x
                    min_x_w = w
                
        if max_x != 0:
            print('動体検知')
            if train_from is None and is_still <= 0:                        
                if a_center < max_x_x + max_x_w < (a_center + b_center) / 2:
                    train_from = 'left'
                    passed_a_time = time.time()
                    print('列車が左から来ました')
                    first_pass_frame = frame
                elif (a_center + b_center) / 2 < min_x_x - min_x_w < b_center:
                    train_from = 'right'
                    passed_b_time = time.time()
                    print('列車が右から来ました')
                    first_pass_frame = frame
            
            if train_from == 'left' and passed_a_time + 0.5 < time.time():
                if passed_b_time is None:
                    if max_x_x + max_x_w > b_center:
                        print('右を通過しました')
                        passed_b_time = time.time()
            elif train_from == 'right' and passed_b_time + 0.5 < time.time():
                if passed_a_time is None:
                    if a_center > min_x - min_x_w:
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
            kph_shared.value = kph
            #speak(f'時速{kph}キロメートルです')
            #first_passed_time = min(passed_a_time, passed_b_time)
            #passed_time = max(passed_a_time, passed_b_time)
            #cv2.imwrite(f'pass_{first_passed_time}.jpg', first_pass_frame)
            #cv2.imwrite(f'pass_{passed_time}.jpg', frame)
            break

def display(frame, last_kph):
    display_frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

    if last_kph:
        kph_area = cv2.getTextSize(f'{last_kph}km/h', cv2.FONT_HERSHEY_DUPLEX, 2, 2)[0]
        cv2.rectangle(display_frame, (0, 0), (kph_area[0] + 70, kph_area[1] + 40), (150, 150 , 150), -1)
        cv2.putText(display_frame, f'{last_kph}km/h', (35, kph_area[1] + 20), cv2.FONT_HERSHEY_DUPLEX, 2, (255, 255, 255), 2)

    if fps:
        cv2.putText(display_frame, f'{fps}fps', (35, fps_area[1] + 100), cv2.FONT_HERSHEY_DUPLEX, 1, (255, 255, 255), 1)
    cv2.line(display_frame, (a_center, a_center_y), (a_center, 0), (255, 0, 0), 3)
    cv2.line(display_frame, (b_center, b_center_y), (b_center, 0), (255, 0, 0), 3)
    cv2.line(display_frame, (0, a_top), (2000, b_top), (255, 0, 0), 3)
    cv2.line(display_frame, (0, a_top - area_height), (2000, b_top - area_height), (255, 0, 0), 3)
    show(cv2, display_frame)
    
def ReaderWorker(frame_q, a_arr, b_arr):
    last_a_update = 0
    last_b_update = 0
    a_center_y = -1
    b_center_y = -1
    a_top = -1
    b_top = -1
    
    while True:
        frame = frame_q.get(True, 1)
        
        # 5秒間バーコードを検出できなかったら初期化する
        if last_a_update + 5 < time.time() or last_b_update + 5 < time.time():
            a_center = -1
            b_center = -1

        frame_width = frame.shape[1]
        frame_height = frame.shape[0]
        
        # シャープネスを上げる
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]], np.float32)
        frame_for_2d = cv2.filter2D(frame, -1, kernel)
        
        codedata = decode(frame_for_2d, timeout=150)

        print(codedata)

        scale = 'N'
        for d in codedata:
            if d.data == b'A':
                a_center = int(d.rect.left + d.rect.width/2)
                a_center_y = frame_height - int(d.rect.top + d.rect.height/2)
                a_top = frame_height - d.rect.top - d.rect.height
                last_a_update = time.time()

            if d.data == b'B' or d.data == b'C' or d.data == b'D':
                if d.data == b'C':
                    scale = 'HO'
                elif d.data == b'D':
                    scale = 'Z'
                b_center = int(d.rect.left + d.rect.width/2)
                b_center_y = frame_height - int(d.rect.top + d.rect.height/2)
                b_top = frame_height - d.rect.top - d.rect.height
                last_b_update = time.time()
                
        a_arr[0] = a_center
        a_arr[1] = a_center_y
        a_arr[2] = a_top
        b_arr[0] = b_center
        b_arr[1] = b_center_y
        b_arr[2] = b_top

def create2DReader(frame_q_reader, a_arr, b_arr):
    reader = Process(target=ReaderWorker, args=(frame_q_reader, a_arr, b_arr))
    reader.daemon = True
    reader.start()
    return reader

def createMeasure(frame_q, kph_shared, a_arr, b_arr):
    measure = Process(target=MeasureSpeedWorker, args=(frame_q, kph_shared, a_arr, b_arr))
    measure.daemon = True
    measure.start()
    return measure

frame_q_measure = Queue()
frame_q_reader = Queue()
kph_shared = Value('i', -1)
a_arr = Array('i', [-1, -1, -1])
b_arr = Array('i', [-1, -1, -1])
reader = create2DReader(frame_q_reader, a_arr, b_arr)
m = createMeasure(frame_q_measure, kph_shared, a_arr, b_arr)

# fps計測
tm = cv2.TickMeter()
tm.start()
cnt_fps = 10

while True:
    ret, frame = cap.read()
    if ret == False:
        continue
    
    frame_q_measure.put(frame)
    frame_q_reader.put(frame)
    kph = kph_shared.value
    show(cv2, frame)
    
    if not m.is_alive():
        m = createMeasure(frame_q_measure, kph_shared, a_arr, b_arr)
    
    if cnt_fps <= 0:
        tm.stop()
        fps = int(1.0 / (tm.getTimeSec() / 10.0))
        print(fps)
        fps_area =  cv2.getTextSize(f'{fps}fps', cv2.FONT_HERSHEY_DUPLEX, 1, 1)[0]
        tm.reset()
        tm.start()
        cnt_fps = 10
    else:
        cnt_fps -= 1
        
    # キューがさばききれなくなってたらどうにかする
        
#while (cap.isOpened()):
    #MeasureSpeed(cap)
    
