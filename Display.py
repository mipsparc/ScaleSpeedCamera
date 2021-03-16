#coding:utf-8

import tkinter
from tkinter import ttk
from Icon import ICON
from PIL import Image, ImageTk
import queue
import cv2
import numpy as np
import sys
import platform
OS = platform.system()
if OS == 'Windows':
    import ctypes

def DisplayWorker(frame_shared, camera_width, camera_height, measure_params):
    if OS == 'Windows':
        ctypes.windll.shcore.SetProcessDpiAwareness(True)
    root = tkinter.Tk()
    disp = Display(root, frame_shared, camera_width, camera_height, measure_params)

class Display:
    def __init__(self, root, frame_shared, camera_width, camera_height, measure_params):
        self.root = root
        iconimg = tkinter.PhotoImage(data=ICON) 
        root.iconphoto(True, iconimg)
        self.root.title("ScaleSpeedCamera")
        self.root.resizable(False, False)
        s = ttk.Style()
        if 'winnative' in s.theme_names():
            s.theme_use('winnative')
        else:
            s.theme_use('alt')
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.frame_shared = frame_shared
        self.camera_width = camera_width
        self.camera_height = camera_height
        self.measure_params = measure_params
        
        mainframe = ttk.Frame(self.root, padding="12 12 12 12")
        mainframe.grid(column=0, row=0, sticky=(tkinter.N, tkinter.W, tkinter.E, tkinter.S))
        
        self.canvas = tkinter.Canvas(mainframe)
        self.canvas.configure(width=camera_width, height=camera_height)
        self.canvas.grid(column=1, row=1, padx=10, pady=10, sticky=(tkinter.N, tkinter.W))
        
        scales = ttk.Frame(mainframe, padding="12 12 12 12")
        scales.grid(column=1, row=2)
        
        rect_frame = ttk.LabelFrame(scales, text='最小動体面積', padding="12 12 12 12")
        self.rect_size = tkinter.IntVar()
        rect_scale = tkinter.Scale(rect_frame, orient=tkinter.HORIZONTAL, length=200, from_=1.0, to=100.0, variable=self.rect_size)
        rect_scale.set(15)
        rect_scale.grid(column=0, row=0, sticky=tkinter.W)
        rect_frame.grid(column=1, row=0, sticky=(tkinter.W))
        
        weight_frame = ttk.LabelFrame(scales, text='動体検知しきい値', padding="12 12 12 12")
        self.weight = tkinter.IntVar()
        weight_scale = tkinter.Scale(weight_frame, orient=tkinter.HORIZONTAL, length=200, from_=1.0, to=50.0, variable=self.weight)
        weight_scale.set(25)
        weight_scale.grid(column=0, row=0, sticky=tkinter.W)
        weight_frame.grid(column=2, row=0, sticky=(tkinter.W))
        
        area_height_frame = ttk.LabelFrame(scales, text='検知域高さ', padding="12 12 12 12")
        self.area_height = tkinter.IntVar()
        area_height_scale = tkinter.Scale(area_height_frame, orient=tkinter.HORIZONTAL, length=200, from_=1.0, to=300.0, variable=self.area_height)
        area_height_scale.set(150)
        area_height_scale.grid(column=0, row=0, sticky=tkinter.W)
        area_height_frame.grid(column=3, row=0, sticky=(tkinter.W))
        
        code_distance_frame = ttk.LabelFrame(scales, text='バーコード間隔(cm)', padding="12 12 12 12")
        self.code_distance = tkinter.IntVar()
        code_distance_scale = tkinter.Scale(code_distance_frame, orient=tkinter.HORIZONTAL, length=400, from_=15.0, to=75.0, variable=self.code_distance)
        code_distance_scale.set(15)
        code_distance_scale.grid(column=0, row=0, sticky=tkinter.W)
        code_distance_frame.grid(column=4, row=0, sticky=(tkinter.W))
        
        self.update()
        self.root.mainloop()

    def update(self):
        frame = np.array(self.frame_shared, dtype=np.uint8).reshape(self.camera_height, self.camera_width, 3)

        image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self.photo = ImageTk.PhotoImage(image=Image.fromarray(image_rgb))
        self.canvas.create_image(0, 0, image=self.photo, anchor=tkinter.NW)
        
        self.measure_params[0] = self.rect_size.get()
        self.measure_params[1] = self.weight.get()
        self.measure_params[2] = self.area_height.get()
        self.measure_params[4] = self.code_distance.get()
        
        self.root.after(50, self.update)
        
    def on_close(self):
        self.root.destroy()
        sys.exit()
