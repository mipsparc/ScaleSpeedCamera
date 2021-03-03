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
from multiprocessing import Process, Array, Value, Queue, freeze_support
import queue
OS = platform.system()
if OS == 'Windows':
    import win32com.client as wincl


# リリースバージョン
version = 1.07

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
    OS = platform.system()
    if OS == 'Windows':
        voice = wincl.Dispatch("SAPI.SpVoice")
        voice.Speak(speech_text)
    else:
        subprocess.Popen(f"echo '{speech_text}' | open_jtalk -x /var/lib/mecab/dic/open-jtalk/naist-jdic -m /usr/share/hts-voice/nitech-jp-atr503-m001/nitech_jp_atr503_m001.htsvoice -ow /dev/stdout | aplay --quiet", shell=True)

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

def MeasureSpeedWorker(frame_q, kph_shared, a_arr, b_arr, box_q, scale_shared, params):
    avg = None
    train_from = None
    passed_a_time = None
    passed_b_time = None
    last_time = 0

    # 列車が去るまで(rectがなくなるまで)なにもしない。20フレーム数える
    is_still = 20

    detect_wait_cnt = 10
    last_detect_area_height = 300
    
    save_photo = params[3]

    while True:
        try:
            frame = frame_q.get(True, 1.0)
        except queue.Empty:
            sys.exit()
        # 5フレ以上残ってたら
        if frame_q.qsize() >= 5:
            # 1フレ残して落とす
            for i in range(frame_q.qsize() - 1):
                try:
                    frame = frame_q.get(False)
                except queue.Empty:
                    pass
        
        if (-1 in a_arr) or (-1 in b_arr):
            # 2次元地点検知コードが認識できなかった場合
            detect_wait_cnt = 10
            continue
        else:
            a_center = a_arr[0]
            a_center_y = a_arr[1]
            a_top = a_arr[2]
        
            b_center = b_arr[0]
            b_center_y = b_arr[1]
            b_top = b_arr[2]
            
            rect_size = params[0]
            weight = params[1] / 10
            area_height = params[2]
            
            #認識し始めから検出まで10フレーム待つ
            if detect_wait_cnt > 0:
                detect_wait_cnt -= 1
                continue

            # 検出域を制限する
            detect_area_top = max(int((a_top + b_top) / 2) - area_height, 1)
            detect_area_bottom = int((a_top + b_top) / 2)
            detect_area_left = 0
            detect_area = frame[detect_area_top:detect_area_bottom, detect_area_left:]
            detect_area_height = detect_area_top - detect_area_bottom
                
            normalized_frame = normalizeFrame(frame)
            # シャープネスを上げる
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]], np.float32)
            normalized_frame = cv2.filter2D(normalized_frame, -1, kernel)

        if avg is None or detect_area_height != last_detect_area_height:
            avg = detect_area.copy().astype("float")
            last_detect_area_height = detect_area_height
            continue

        cv2.accumulateWeighted(detect_area, avg, weight)
        frameDelta = cv2.absdiff(detect_area, cv2.convertScaleAbs(avg))
        thresh = cv2.threshold(frameDelta, 40, 255, cv2.THRESH_TOZERO)[1]
        
        contours, hierarchy = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
        max_x = 0
        min_x = 99999
        boxes = []
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
                
                boxes.append([x, y, w, h])
                
                max_x = int(max(max_x, x + w))
                if max_x == x + w:
                    max_x_x = x
                    max_x_w = w
                min_x = int(min(min_x, x))
                if min_x == x:
                    min_x_x = x
                    min_x_w = w
                    
        box_q.put(boxes)
                
        if max_x != 0:
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
            if scale_shared.value == 'N':
                kph = int((qr_length / passing_time) * 3.6 * 150)
            elif scale_shared.value == 'HO':
                kph = int((qr_length / passing_time) * 3.6 * 80)
            else: # Z
                kph = int((qr_length / passing_time) * 3.6 * 220)
            print(f'時速{kph}キロメートルです')
            kph_shared.value = kph
            speak(f'時速{kph}キロメートルです')
            first_passed_time = min(passed_a_time, passed_b_time)
            passed_time = max(passed_a_time, passed_b_time)

            if save_photo:
                OS = platform.system()
                if OS == 'Windows':
                    path = os.path.expanduser('~/Pictures')
                else:
                    path = os.path.expanduser('~')
                
                kph_area = cv2.getTextSize(f'{kph}km/h', cv2.FONT_HERSHEY_DUPLEX, 2, 2)[0]
                cv2.rectangle(first_pass_frame, (0, 0), (kph_area[0] + 70, kph_area[1] + 40), (150, 150 , 150), -1)
                cv2.putText(first_pass_frame, f'{kph}km/h', (35, kph_area[1] + 20), cv2.FONT_HERSHEY_DUPLEX, 2, (255, 255, 255), 2)
                cv2.imwrite(path + f'/train_{first_passed_time}.jpg', first_pass_frame)
                
                cv2.rectangle(frame, (0, 0), (kph_area[0] + 70, kph_area[1] + 40), (150, 150 , 150), -1)
                cv2.putText(frame, f'{kph}km/h', (35, kph_area[1] + 20), cv2.FONT_HERSHEY_DUPLEX, 2, (255, 255, 255), 2)
                cv2.imwrite(path + f'/train_{passed_time}.jpg', frame)

            break

def ReaderWorker(frame_q, a_arr, b_arr, scale_shared):
    last_a_update = 0
    last_b_update = 0
    a_center_y = -1
    b_center_y = -1
    a_top = -1
    b_top = -1
    
    while True:
        try:
            frame = frame_q.get(True, 1.0)
        except queue.Empty:
            sys.exit()
        # 5フレ以上残ってたら
        if frame_q.qsize() >= 5:
            # 1フレ残して落とす
            for i in range(frame_q.qsize() - 1):
                try:
                    frame = frame_q.get(False)
                except queue.Empty:
                    pass
        
        # 5秒間バーコードを検出できなかったら初期化する
        if last_a_update + 10 < time.time() or last_b_update + 10 < time.time():
            a_center = -1
            b_center = -1

        frame_width = frame.shape[1]
        frame_height = frame.shape[0]
        
        frame = normalizeFrame(frame)
        
        codedata = decode(frame, timeout=300)

        scale_shared.value = 'N'
        for d in codedata:
            if d.data == b'A':
                a_center = int(d.rect.left + d.rect.width/2)
                a_center_y = frame_height - int(d.rect.top + d.rect.height/2)
                a_top = frame_height - d.rect.top - d.rect.height
                last_a_update = time.time()

            if d.data == b'B' or d.data == b'C' or d.data == b'D':
                if d.data == b'C':
                    scale_shared.value = 'HO'
                elif d.data == b'D':
                    scale_shared.value = 'Z'
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
        print('終了しています。しばらくお待ちください')
        cap.release()
        cv2.destroyAllWindows()
        sys.exit()

def createMeasure(frame_q, kph_shared, a_arr, b_arr, box_q, scale_shared, params):
    measure = Process(target=MeasureSpeedWorker, args=(frame_q, kph_shared, a_arr, b_arr, box_q, scale_shared, params))
    measure.start()
    return measure

def normalizeFrame(v):
    # 明るさを平準化する
    # https://qiita.com/s-kajioka/items/9c9fc6c0e9e8a9d05800
    v = ( v - np.mean(v)) / np.std(v) * 30 + 90
    frame = np.array(v, dtype=np.uint8)
    return frame

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
    
    print('通過時の画像をピクチャフォルダに保存する場合はEnter')
    save_photo = input('保存しない場合はNを入力してEnter > ') != 'N'

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
    measure_params = Array('i', [150, 3, 300, int(save_photo)])

    cv2.createTrackbar('MinRect', 'ScaleSpeedCamera', 50 , 300, WindowChange.changeRectSize)
    cv2.createTrackbar('Weight', 'ScaleSpeedCamera', 3 , 5, WindowChange.changeWeight)
    cv2.createTrackbar('Height', 'ScaleSpeedCamera', 300, 400, WindowChange.changeHeight)
    WindowChange.changeRectSize(50)
    WindowChange.changeWeight(3)
    WindowChange.changeHeight(300)

    # fps計測
    tm = cv2.TickMeter()
    tm.start()
    cnt_fps = 10
    fps = -1

    measure = None
    reader = None

    while cap.isOpened():
        ret, frame = cap.read()
        if ret == False:
            continue
                
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_q_measure.put(gray_frame)
        frame_q_reader.put(gray_frame)
        kph = kph_shared.value
        
        measure_params[0] = WindowChange.rect_size
        measure_params[1] = WindowChange.weight
        measure_params[2] = WindowChange.area_height
        
        try:
            boxes = box_q.get(False)
        except queue.Empty:
            pass
        
        area_height = WindowChange.area_height
        display(frame, kph, boxes, fps, a_arr, b_arr, area_height)
        
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
