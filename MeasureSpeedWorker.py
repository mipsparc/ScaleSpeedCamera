#coding:utf-8
import time
import cv2
import numpy as np
import queue
import os
import sys
import platform
OS = platform.system()
if OS == 'Windows':
    import win32com.client as wincl
else:
    import subprocess
    
def speak(speech_text):
    OS = platform.system()
    if OS == 'Windows':
        voice = wincl.Dispatch("SAPI.SpVoice")
        voice.Speak(speech_text)
    else:
        subprocess.Popen(f"echo '{speech_text}' | open_jtalk -x /var/lib/mecab/dic/open-jtalk/naist-jdic -m /usr/share/hts-voice/nitech-jp-atr503-m001/nitech_jp_atr503_m001.htsvoice -ow /dev/stdout | aplay --quiet", shell=True)

def normalizeFrame(v):
    # 明るさを平準化する
    # https://qiita.com/s-kajioka/items/9c9fc6c0e9e8a9d05800
    v = ( v - np.mean(v)) / np.std(v) * 30 + 120
    frame = np.array(v, dtype=np.uint8)
    return frame

def MeasureSpeedWorker(frame_shared, speed_shared, a_arr, b_arr, box_q, params, scale, speed_system, camera_width, camera_height):
    avg = None
    train_from = None
    passed_a_time = None
    passed_b_time = None
    last_time = 0
    
    if speed_system == 'kph':
        scale_factor = float(scale)
    else:
        scale_factor = float(scale) * 0.621371

    # 列車が去るまで(rectがなくなるまで)なにもしない。20フレーム数える
    is_still = 20

    last_detect_area_height = 300
    
    save_photo = params[3]
    
    last_mean = 1

    while True:
        frame = np.array(frame_shared[:], dtype=np.uint8).reshape(camera_height, camera_width)
        
        if (-1 in a_arr) or (-1 in b_arr):
            # 2次元地点検知コードが認識できなかった場合
            continue
        else:
            a_center = a_arr[0]
            a_center_y = a_arr[1]
            a_top = a_arr[2]
        
            b_center = b_arr[0]
            b_center_y = b_arr[1]
            b_top = b_arr[2]
            
            rect_size = params[0]
            weight = params[1] / 100.0
            area_height = params[2]
            qr_length = params[4] / 100

            # 検出域を制限する
            detect_area_top = max(int((a_top + b_top) / 2) - area_height, 1)
            detect_area_bottom = int((a_top + b_top) / 2)
            detect_area_left = 0
            detect_area = frame[detect_area_top:detect_area_bottom, detect_area_left:]
            detect_area_height = detect_area_top - detect_area_bottom
            
            detect_area = normalizeFrame(detect_area)

        if avg is None or detect_area_height != last_detect_area_height:
            avg = detect_area.copy().astype("float")
            last_detect_area_height = detect_area_height
            continue

        cv2.accumulateWeighted(detect_area, avg, weight)
        frameDelta = cv2.absdiff(detect_area, cv2.convertScaleAbs(avg))
        
        # 点滅が発生している
        mean = cv2.mean(frameDelta)[0]
        if abs(mean - last_mean) > 1:
            last_mean = mean
            continue
        last_mean = mean
        
        thresh = cv2.threshold(frameDelta, 30, 255, cv2.THRESH_TOZERO)[1]
        
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
                if w < 15:
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
            
            if train_from == 'left' and passed_a_time + 0.3 < time.time():
                if passed_b_time is None:
                    if max_x_x + max_x_w > b_center:
                        print('右を通過しました')
                        passed_b_time = time.time()
            elif train_from == 'right' and passed_b_time + 0.3 < time.time():
                if passed_a_time is None:
                    if a_center > min_x - min_x_w:
                        print('左を通過しました')
                        passed_a_time = time.time()
        else:
            is_still -= 1
            if passed_a_time is None or passed_b_time is None:
                if passed_a_time and (time.time() > passed_a_time + 10):
                    print('列車検知をクリアしました')
                    break
                if passed_b_time and (time.time() > passed_b_time + 10):
                    print('列車検知をクリアしました')
                    break

        if passed_a_time is not None and passed_b_time is not None:
            passing_time = abs(passed_a_time - passed_b_time)

            result = int((qr_length / passing_time) * 3.6 * scale_factor)

            if speed_system == 'kph':
                print(f'時速{result}キロメートルです')
                speed_shared.value = result
                speak(f'時速{result}キロメートルです')
                speed_system_str = 'km/h'
            else:
                print(f'時速{result}マイルです')
                speed_shared.value = result
                speak(f'時速{result}マイルです')
                speed_system_str = 'MPH'
            first_passed_time = min(passed_a_time, passed_b_time)
            passed_time = max(passed_a_time, passed_b_time)

            if save_photo:
                OS = platform.system()
                if OS == 'Windows':
                    path = os.path.expanduser('~/Pictures')
                else:
                    path = os.path.expanduser('~')
                
                kph_area = cv2.getTextSize(f'{result}{speed_system_str}', cv2.FONT_HERSHEY_DUPLEX, 2, 2)[0]
                cv2.rectangle(first_pass_frame, (0, 0), (kph_area[0] + 70, kph_area[1] + 40), (150, 150 , 150), -1)
                cv2.putText(first_pass_frame, f'{result}{speed_system_str}', (35, kph_area[1] + 20), cv2.FONT_HERSHEY_DUPLEX, 2, (255, 255, 255), 2)
                cv2.imwrite(path + f'/train_{first_passed_time}.jpg', first_pass_frame)
                
                cv2.rectangle(frame, (0, 0), (kph_area[0] + 70, kph_area[1] + 40), (150, 150 , 150), -1)
                cv2.putText(frame, f'{result}{speed_system_str}', (35, kph_area[1] + 20), cv2.FONT_HERSHEY_DUPLEX, 2, (255, 255, 255), 2)
                cv2.imwrite(path + f'/train_{result}.jpg', frame)

            break
