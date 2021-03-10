#coding:utf-8

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
        
        ret, preprocessed = cv2.threshold(frame, 170, 255, cv2.THRESH_BINARY)
        
        codedata = decode(preprocessed, timeout=300, max_count=2, shape=DmtxSymbolSize.DmtxSymbolSquareAuto)

        scale_shared.value = 'N'
        for d in codedata:
            if d.data == b'A':
                a_center = int(d.rect.left + d.rect.width/2)
                a_center_y = frame_height - int(d.rect.top + d.rect.height/2)
                a_top = frame_height - d.rect.top - d.rect.height
                last_a_update = time.time()

            if d.data == b'B' or d.data == b'C' or d.data == b'D':
                if d.data == b'C':
                    scale_shared.value = 'H'
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
