from pyzbar.pyzbar import decode, ZBarSymbol
import numpy as np
import cv2
import os
import sys
from contextlib import contextmanager
import time
import platform
import collision

print('''ScaleSpeedCamera (鉄道模型車速計測ソフト) by mipsparc

起動中です
しばらくお待ちください……''')

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

def MeasureSpeed(cap):
    a_center = None
    b_center = None
    avg = None
    train_from = None
    passed_a_time = None
    passed_b_time = None
    while True:
        if OS == 'Windows':
            ret, frame = cap.read()
        else:
            with stderr_redirected():
                ret, frame = cap.read()
        
        if ret == False:
            continue
            
        qrdata = decode(frame, symbols=[ZBarSymbol.QRCODE])
        print(qrdata)
        
        scale = 'N'
        for d in qrdata:
            if d.data == b'A':
                a_center = int((d.polygon[0].x + d.polygon[1].x + d.polygon[2].x + d.polygon[3].x) / 4)
                a_center_y = int((d.polygon[0].y + d.polygon[1].y + d.polygon[2].y + d.polygon[3].y) / 4)
                a_top = d.rect.top
                a_bottom_center = int((d.polygon[0].x + d.polygon[1].x) / 2)
                a_bottom_center_y = int((d.polygon[0].y + d.polygon[1].y) / 2)
                try:
                    a_tilt = (a_center_y - a_bottom_center_y) / (a_center - a_bottom_center)
                except ZeroDivisionError:
                    a_tilt = 0
                    
                print('a_tilt', a_tilt)

                #a_line = collision.Poly(collision.Vector(a_center, a_center_y), [
                    #collision.Vector(a_center + 1, a_center_y)
                    
                #])


            if d.data == b'B' or d.data == b'C':
                if d.data == b'C':
                    scale = 'HO'
                b_center = int((d.polygon[0].x + d.polygon[1].x + d.polygon[2].x + d.polygon[3].x) / 4)
                b_center_y = int((d.polygon[0].y + d.polygon[1].y + d.polygon[2].y + d.polygon[3].y) / 4)
                b_top = d.rect.top
                b_bottom_center = int((d.polygon[1].x + d.polygon[2].x) / 2)
                b_bottom_center_y = int((d.polygon[1].y + d.polygon[2].y) / 2)
                try:
                    b_tilt = (b_center_y - b_bottom_center_y) / (b_center - b_bottom_center)
                except ZeroDivisionError:
                    b_tilt = 0
                    
                print('b_tilt', b_tilt)

                #b_line = collision.Poly(collision.Vector(b_center, b_center_y), [
                    #collision.Vector(b_bottom_center, b_bottom_center_y)
                #])

        if a_center and b_center:
            qrrect_top = int((a_top + b_top) / 2)
        
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if avg is None:
            avg = frame.copy().astype("float")
            continue
        
        # コントラストを1.8に設定
        dst = frame * 1.8
        frame = np.clip(frame, 0, 255).astype(np.uint8)

        cv2.accumulateWeighted(frame, avg, 0.3)
        frameDelta = cv2.absdiff(frame, cv2.convertScaleAbs(avg))
        thresh = cv2.threshold(frameDelta, 20, 255, cv2.THRESH_BINARY)[1]
        
        contours, hierarchy = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
        max_x = 0
        min_x = 99999
        for i in range(0, len(contours)):
            if len(contours[i]) > 0:
                # remove small objects
                if cv2.contourArea(contours[i]) < 900:
                    continue

                rect = contours[i]
                x, y, w, h = cv2.boundingRect(rect)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 0), 10)
                
                box = collision.Poly.from_box(collision.Vector(x, y), w, h)
                
                max_x = int(max(max_x, x + w/2))
                min_x = int(min(min_x, x + w/2))
                
                if a_center and b_center:
                    if train_from is None:
                        if a_center < (x + w/2) < a_center + 100:
                            if a_top > (y + h/2) > qrrect_top - 200:
                                train_from = 'left'
                                print('left')
                        elif b_center < (x + w/2) < b_center + 100:
                            if b_top > (y + h/2) > qrrect_top - 200:
                                train_from = 'right'
                                print('right')

        if train_from == 'left':
            if passed_a_time is None:
                passed_a_time = time.time()
            elif max_x > b_center and passed_b_time is None:
                passed_b_time = time.time()
            if passed_a_time and (time.time() > passed_a_time + 6):
                break
        elif train_from == 'right':
            if passed_b_time is None:
                passed_b_time = time.time()
            elif min_x < a_center and passed_a_time is None:
                passed_a_time = time.time()
            if passed_b_time and (time.time() > passed_b_time + 6):
                break

        if passed_a_time is not None and passed_b_time is not None:
            passing_time = abs(passed_a_time - passed_b_time)
            if passing_time > 0.3:
                qr_length = 0.15
                if scale == 'N':
                    kph = int((qr_length / passing_time) * 3.6 * 150)
                else:
                    # HO
                    kph = int((qr_length / passing_time) * 3.6 * 80)
                print('kph:', kph)

                speech_text = f'{kph}キロメートル毎時です'
                if OS == 'Windows':
                    voice.Speak(speech_text)
                else:
                    subprocess.run(f"echo '{speech_text}' | open_jtalk -x /var/lib/mecab/dic/open-jtalk/naist-jdic -m /usr/share/hts-voice/nitech-jp-atr503-m001/nitech_jp_atr503_m001.htsvoice -ow /dev/stdout | aplay --quiet", shell=True)
                break
            else:
                break
        
        if a_center and b_center:
            intercept_a = -a_tilt * a_bottom_center_y - a_bottom_center
            intercept_b = a_tilt * b_bottom_center_y - b_bottom_center
            print(b_tilt)
            cv2.line(frame, (a_bottom_center, a_bottom_center_y), (int(-intercept_a / a_tilt), 0), (255, 0, 0), 3)
            cv2.line(frame, (b_bottom_center, b_bottom_center_y), (int(-intercept_b / -a_tilt), 0), (255, 0, 0), 3)
            cv2.rectangle(frame, (a_center, qrrect_top - 200), (a_center + 100, a_top), (0,255,0), 10)
            cv2.rectangle(frame, (b_center - 100, qrrect_top - 200), (b_center, b_top), (0,255,0), 10)
            cv2.circle(frame, (b_center, b_center_y), 15, (0,255,0), -1)
            cv2.circle(frame, (b_bottom_center, b_bottom_center_y), 10, (0,255,0), -1)

        cv2.imshow('ScaleSpeed',frame)
        if cv2.waitKey(1) & 0xFF == ord('q') or cv2.getWindowProperty('ScaleSpeed', 0) == -1:
            raise KeyboardInterrupt
try:
    while (cap.isOpened()):
        MeasureSpeed(cap)
finally:
    cap.release()
    cv2.destroyAllWindows()
