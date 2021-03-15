#coding:utf-8

import tkinter
from tkinter import ttk
from Icon import ICON

class Greeting:
    def __init__(self, root, camera_ids, version):
        self.root = root
        iconimg = tkinter.PhotoImage(data=ICON) 
        root.iconphoto(True, iconimg)
        self.root.title("ScaleSpeedCamera")
        self.root.resizable(False, False)
        s = ttk.Style()
        s.theme_use('alt')

        mainframe = ttk.Frame(self.root, padding="12 12 12 12")
        mainframe.grid(column=0, row=0, sticky=(tkinter.N, tkinter.W, tkinter.E, tkinter.S))
        
        greeting = tkinter.Label(mainframe, text=f'バージョン{version}  初期設定を行ってください')
        greeting.grid(column=1, row=1)
        
        scale_frame = ttk.LabelFrame(mainframe, text='縮尺(直接入力可)', padding="12 12 12 12")
        self.custom_gauge = tkinter.StringVar(value='1/150')
        self.gauge_input = ttk.Entry(scale_frame, textvariable=self.custom_gauge)
        gauges = tkinter.StringVar(value=('(N) 1/150', '(HO) 1/80', '(N) 1/160', '(HO) 1/87', '(Z) 1/220'))
        gauges_box = tkinter.Listbox(scale_frame, listvariable=gauges, height=5)
        self.gauge_input.grid(column=0, row=0, padx=20, pady=20)
        gauges_box.grid(column=0, row=1, padx=20)
        scale_frame.grid(column=1, row=2, sticky=tkinter.N+tkinter.S)
        
        self.speed_system = tkinter.StringVar()
        speed_system_frame = ttk.LabelFrame(mainframe, padding="12 12 12 12", text='単位系')
        kph_sys = ttk.Radiobutton(speed_system_frame, text='km/h', variable=self.speed_system, value='kph')
        mph_sys = ttk.Radiobutton(speed_system_frame, text='MPH', variable=self.speed_system, value='mph')
        kph_sys.grid(column=0, row=0, sticky=tkinter.N, padx=20)
        mph_sys.grid(column=0, row=1, sticky=tkinter.N, padx=20)
        self.speed_system.set('kph')
        speed_system_frame.grid(column=2, row=2, sticky=tkinter.N+tkinter.S)
        
        camera_names = []
        for cam in camera_ids:
            camera_names.append(f'カメラ {cam}')
        camera_frame = ttk.LabelFrame(mainframe, text='カメラ選択', padding="12 12 12 12")
        self.cameras = tkinter.StringVar(value=tuple(camera_names))
        self.camera_box = tkinter.Listbox(camera_frame, listvariable=self.cameras, height=5)
        self.camera_box.grid(column=0, row=0, padx=20)
        camera_frame.grid(column=3, row=2, sticky=tkinter.N+tkinter.S)
        
        self.save_photo = tkinter.BooleanVar()
        save_checkbox = ttk.Checkbutton(mainframe, text='通過時写真を保存する', variable=self.save_photo)
        save_checkbox.grid(column=3, row=3)
        
        for child in mainframe.winfo_children(): 
            child.grid_configure(padx=5, pady=5)

        ttk.Button(mainframe, text="はじめる", command=self.final).grid(column=3, row=4, sticky=(tkinter.E, tkinter.S))

        gauges_box.bind("<<ListboxSelect>>", self.selectGauge)
        self.root.bind("<Return>", self.final)
        
        self.root.mainloop()

    def selectGauge(self, event):
        selection = event.widget.curselection()
        if selection:
            i = selection[0]
            gauge_text = event.widget.get(i)
            scale = gauge_text.split(' ')[1]
            self.gauge_input.delete(0, 'end')
            self.gauge_input.insert(0, scale)
            
    def final(self, *args):
        scale = self.custom_gauge.get()
        try:
            scale_howsmall = scale.split('/')[1]
            int(scale_howsmall)
        except IndexError:
            return
        except ValueError:
            return
        
        speed_system = self.speed_system.get()
        
        index = self.camera_box.curselection()
        if len(index) > 0:
            camera_name = self.camera_box.get(index[0])
        else:
            return
        camera_id = camera_name.split(' ')[1]
        
        self.init_value = {'scale': scale_howsmall, 'speed_system': speed_system, 'camera_id': camera_id, 'save_photo': self.save_photo.get()}
        self.root.destroy()
