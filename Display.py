#coding:utf-8

import tkinter
from tkinter import ttk
from Icon import ICON
from PIL import Image, ImageTk
import queue
import cv2
import numpy as np
import sys

def DisplayWorker(root, frame_shared, real_cam_w, real_cam_h, measure_params):
    disp = Display(root, frame_shared, real_cam_w, real_cam_h, measure_params)


#TODO: シークバー同期機能をつける
class Display:
    def __init__(self, root, frame_shared, real_cam_w, real_cam_h, measure_params):
        self.root = root
        iconimg = tkinter.PhotoImage(data=ICON) 
        root.iconphoto(True, iconimg)
        self.root.title("ScaleSpeedCamera")
        self.root.resizable(False, False)
        s = ttk.Style()
        s.theme_use('alt')
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.frame_shared = frame_shared
        self.real_cam_w = real_cam_w
        self.real_cam_h = real_cam_h
        
        mainframe = ttk.Frame(self.root, padding="12 12 12 12")
        mainframe.grid(column=0, row=0, sticky=(tkinter.N, tkinter.W, tkinter.E, tkinter.S))
        
        self.canvas = tkinter.Canvas(mainframe)
        self.canvas.configure(width=real_cam_w, height=real_cam_h)
        self.canvas.grid(column=1, row=1, padx=10, pady=10, sticky=(tkinter.N, tkinter.W))
        
        self.update()
        self.root.mainloop()

    def update(self):
        frame = np.array(self.frame_shared, dtype=np.uint8).reshape(self.real_cam_h, self.real_cam_w, 3)

        image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self.photo = ImageTk.PhotoImage(image=Image.fromarray(image_rgb))
        self.canvas.create_image(0, 0, image=self.photo, anchor=tkinter.NW)
        
        self.root.after(50, self.update)
        
    def on_close(self):
        self.root.destroy()
        sys.exit()
