from pyzbar.pyzbar import decode, ZBarSymbol
import cv2
import os
import sys
from contextlib import contextmanager
import time
import subprocess

camera_id = 0
camera_width = 1280
camera_height = 720
camera_fps = 30

if False:
    # logicool C270n WebCam
    cap = cv2.VideoCapture(2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT,960)

    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FPS, 30)
else:
    # Integrated Camera Lenovo
    cap = cv2.VideoCapture(camera_id)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, camera_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_height)

    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FPS, camera_fps)

a_center = None
b_center = None
avg = None
train_from = None
passed_a_time = None
passed_b_time = None
    
while (cap.isOpened()):
    with stderr_redirected():
        ret, frame = cap.read()
    
    if ret == False:
        continue
        
    qrdata = decode(frame, symbols=[ZBarSymbol.QRCODE])
    
    for d in qrdata:
        if d.data == b'A':
            a_center = int((d.polygon[0].x + d.polygon[2].x) / 2)
        if d.data == b'B':
            b_center = int((d.polygon[0].x + d.polygon[2].x) / 2)
    
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    if avg is None:
        avg = frame.copy().astype("float")
        continue

    cv2.accumulateWeighted(frame, avg, 0.3)
    frameDelta = cv2.absdiff(frame, cv2.convertScaleAbs(avg))
    thresh = cv2.threshold(frameDelta, 20, 255, cv2.THRESH_BINARY)[1]
    
    contours, hierarchy = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
    max_x = 0
    min_x = 99999
    for i in range(0, len(contours)):
        if len(contours[i]) > 0:
            # remove small objects
            if cv2.contourArea(contours[i]) < 700:
                continue

            rect = contours[i]
            x, y, w, h = cv2.boundingRect(rect)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 0), 10)
            
            max_x = max(max_x, x + w)
            min_x = min(min_x, x)

    if a_center and b_center:     
        train_from = 'left'
 
        if train_from == 'left':
            if max_x > a_center and passed_a_time is None:
                passed_a_time = time.time()
                print('left passed at ', passed_a_time)
            if max_x > b_center and passed_b_time is None and passed_a_time is not None:
                passed_b_time = time.time()
                print('right passed at ', passed_b_time)

    if passed_a_time is not None and passed_b_time is not None:
        passing_time = abs(passed_a_time - passed_b_time)
        if passing_time > 0.1:
            qr_length = 0.15
            kph = int((qr_length / passing_time) * 3.6 * 150)
            print('kph:', kph)
            a_center = None
            b_center = None
            avg = None
            train_from = None
            passed_a_time = None
            passed_b_time = None
            speech_text = f'スケールスピードは{kph}キロメートル毎時です'
            subprocess.call(f"echo '{speech_text}' | open_jtalk -x /var/lib/mecab/dic/open-jtalk/naist-jdic -m /usr/share/hts-voice/nitech-jp-atr503-m001/nitech_jp_atr503_m001.htsvoice -ow /dev/stdout | aplay --quiet", shell=True)
            break
        else:
            break
    
    if a_center and b_center:
        cv2.line(frame, (a_center, 0), (a_center, 9999), (255, 0, 0), 3)
        cv2.line(frame, (b_center, 0), (b_center, 9999), (255, 0, 0), 3)
    cv2.imshow('frame',frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# When everything done, release the capture
cap.release()
cv2.destroyAllWindows()

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

