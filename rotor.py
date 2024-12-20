from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.uic import loadUi
import sys, datetime, time, json, os
import minimalmodbus, serial, threading
import serial.tools.list_ports

import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objs as go
import plotly.offline as offline

from pyqtgraph import PlotWidget, plot

class MainUI(QMainWindow):
    def __init__(self):
        super(MainUI, self).__init__()
        loadUi("rotor.ui", self)

        self.LinearSpeed = 100
        self.RotSpeed = 5

        try:     # Загрузка параметров из файла конфигурации
            with open('config.json', 'r') as config_file: 
                config_data = json.load(config_file)
        except (FileNotFoundError):
            print('Файл конфигурации повреждён или отсутствует')
            config_data = {     # Если файл конфигурации не подгрузился, берутся значения для подстановки
                'Date': '01.11.2024',
                'Time': '12:12',
                'FIO': 'Имя Фамилия',
                'RtrName': 'RotorName',
                'RtrNumber': 'RotorNumber',
                'RtrDiam': 155,
                'RtrHght': 140,
                'ZeroPhi': 0.0,
                'ZeroZ': 0.0}
        self.pBtn_SaveConfig.clicked.connect(self.SaveConfig)

        # ---------- Serial ports ----------
        portList = serial.tools.list_ports.comports(include_links=False)
        self.comPorts = []
        for item in portList:
            self.comPorts.append(item.device)
        message = "Доступные COM-порты: " + str(self.comPorts)
        print(message)
        self.statusbar.showMessage(message)

        # Окно информации
        self.tab1_dateEdit.setDate(datetime.datetime.now())
        self.tab1_dateEdit.setCalendarPopup(True)
        self.tab1_timeEdit.setTime(datetime.datetime.now().time())
        self.tab1_lEd_FIO.setText(str(config_data['FIO']))
        self.tab1_lEd_RotorName.setText(str(config_data['RtrName']))
        self.tab1_lEd_RotorNum.setText(str(config_data['RtrNumber']))
        self.lEd_RotorDiam.setText(str(config_data['RtrDiam']))
        self.lEd_RotorHght.setText(str(config_data['RtrHght']))
        self.ZeroPhi = config_data['ZeroPhi']
        self.ZeroZ = config_data['ZeroZ']

        self.SetScanHeight()
        self.lEd_RotorDiam.editingFinished.connect(self.Angle2MM)
        self.lEd_RotorHght.editingFinished.connect(self.SetScanHeight)
        
        # Окно настроек
        self.cBox_PortMotor.addItems(self.comPorts)
        self.cBox_PortMotor.setCurrentIndex(0)
        self.cBox_PortData.addItems(self.comPorts)
        self.cBox_PortData.setCurrentIndex(1)
        self.pBtn_Init.clicked.connect(self.Init)

        self.pBtn_ShowData.clicked.connect(self.ShowData)
        self.pBtn_Calibrate.clicked.connect(self.CalibrateThread)

        self.pBtn_RotateCW.pressed.connect(self.RotateCW)
        self.pBtn_RotateCW.released.connect(self.StopRotor)
        self.pBtn_RotateCCW.pressed.connect(self.RotateCCW)
        self.pBtn_RotateCCW.released.connect(self.StopRotor)

        self.pBtn_MoveUp.pressed.connect(self.LinearMotionUp)
        self.pBtn_MoveUp.released.connect(self.StopLinear)
        self.pBtn_MoveDown.pressed.connect(self.LinearMotionDown)
        self.pBtn_MoveDown.released.connect(self.StopLinear)

        self.pBtn_ZeroPhi.clicked.connect(self.SetZeroPhi)
        self.pBtn_ZeroZ.clicked.connect(self.SetZeroZ)

        # Окно точного шагания
        self.cBox_ScanStepGeneratrix.addItems(['0,5 мм', '1 мм', '2 мм','4 мм'])
        self.cBox_ScanStepGeneratrix.setCurrentIndex(1)
        self.LinearStep = 1000 # 1mm default
        self.cBox_ScanStepGeneratrix.currentIndexChanged.connect(self.SetupScanStepGeneratrix)
        self.pBtn_Position.clicked.connect(self.AbsPositionThread)
        self.dSpBox_ScanStepAngle.textChanged.connect(self.Angle2MM)
        self.pBtn_ScanGeneratrix.clicked.connect(self.ScanThread)
        self.pBtn_ScanGeneratrixStop.clicked.connect(self.Stop)

        # Окно спирального режима
        self.pBtn_ScanRotorSpiral.clicked.connect(self.ScanRotorFastThread)

        # Окно вывода результатов
        self.cBox_FieldComponent.addItems(['Bx', 'By', 'Bz'])
        self.cBox_FieldComponent.setCurrentIndex(0)
        self.componentName = 'Bx'
        self.cBox_FieldComponent.currentIndexChanged.connect(self.SetFieldComponent)
        self.spBox_LayerNum.valueChanged.connect(lambda: self.graphWidget.clear())
        self.spBox_LayerNum.setRange(1, 410)

        self.graphWidget.setBackground('w')
        self.pBtn_Result.clicked.connect(self.ShowGraph)
        self.pBtn_ResultInFrame.clicked.connect(self.PlotData)
        self.pBtn_SaveImg.clicked.connect(self.SaveImg)

    def SetScanHeight(self) -> None:
        ''' Введённая высота ротора записывается как высота области сканирования '''
        self.dSpBox_Range_Z.setValue(float(self.lEd_RotorHght.text().replace(',','.')))
        self.dSpBox_Range_Z_spiral.setValue(float(self.lEd_RotorHght.text().replace(',','.')))

    def SetupScanStepGeneratrix(self, index: int) -> None:
        ''' Выбор шага по образующей '''
        match index:
            case 0:
                self.LinearStep = 500
            case 1:
                self.LinearStep = 1000
            case 2:
                self.LinearStep = 2000
            case 3:
                self.LinearStep = 4000
        print('Задан шаг по образующей:', self.LinearStep, ' мкм')

    def Angle2MM(self) -> None:
        ''' Пересчёт шага сканирования по углу из градусов в мм
            в зависимости от диаметра ротора'''
        try:
            millimeters = round(self.dSpBox_ScanStepAngle.value()*3.14159*float(self.lEd_RotorDiam.text().replace(',', '.'))/360, 3)
            self.lbl_ScanStepAngleMM.setText(str(millimeters).replace('.', ','))
        except ValueError:
            message = "Неверные значения в поле диаметра ротора"
            print(message)
            self.statusbar.showMessage(message)

    def Init(self) -> None:
        ''' Запускается инициализация двигателей вращения и линейки, если удачно, кнопка зеленеет '''
        if self.InitRotMotor() and self.InitLinearMotor():
            self.pBtn_Init.setStyleSheet('QPushButton {background-color : forestgreen;}'
                                         'QPushButton:hover { background-color: #45a049;}') 

    def InitRotMotor(self) -> bool:
        ''' Инициализация двигателя вращения ротора '''
        try:
            # Modbus-адрес драйвера по умолчанию - 1
            self.instrumentRotor = minimalmodbus.Instrument(self.cBox_PortMotor.currentText(), 1) #COM9, 1 - вращение, 2 - линейка
            # Настройка порта: скорость - 38400 бод/с, четность - нет, кол-во стоп-бит - 2.
            self.instrumentRotor.mode = minimalmodbus.MODE_RTU
            print(self.instrumentRotor.serial.port)
            self.instrumentRotor.serial.baudrate = 38400
            self.instrumentRotor.serial.parity = minimalmodbus.serial.PARITY_NONE
            self.instrumentRotor.serial.stopbits = 2
            # self.instrumentRotor.serial.databits = 8
            self.instrumentRotor.serial.timeout  = 0.05          # seconds
            self.instrumentRotor.close_port_after_each_call = True
            print(self.instrumentRotor)
            print('Вращение подключено')
        except (IOError, AttributeError, ValueError) as err: # minimalmodbus.serial.serialutil.SerialException:
            message = "Привод вращения не виден, Error: " + str(err)
            print(message)
            self.statusbar.showMessage(message)
            return False

        try:
            # Команда включения серво; 0x0405 - адрес параметра; 0x83 - значение параметра
            self.instrumentRotor.write_register(0x00F, 1)
            return True
        except (IOError, AttributeError, ValueError) as err: # minimalmodbus.serial.serialutil.SerialException:
            message = "Запуск привода вращения не удался, Error: " + str(err)
            print(message)
            self.statusbar.showMessage(message)
            return False

    def InitLinearMotor(self) -> bool:
        ''' Инициализация двигателя линейки '''
        try:
            # Modbus-адрес драйвера по умолчанию - 1
            self.instrumentLinear = minimalmodbus.Instrument(self.cBox_PortMotor.currentText(), 2) #COM9, 1 - вращение, 2 - линейка
            # Настройка порта: скорость - 38400 бод/с, четность - нет, кол-во стоп-бит - 2.
            self.instrumentLinear.mode = minimalmodbus.MODE_RTU
            print(self.instrumentLinear.serial.port)
            self.instrumentLinear.serial.baudrate = 38400
            self.instrumentLinear.serial.parity = minimalmodbus.serial.PARITY_NONE
            self.instrumentLinear.serial.stopbits = 2
            # self.instrumentLinear.serial.databits = 8
            self.instrumentLinear.serial.timeout  = 0.05          # seconds
            self.instrumentLinear.close_port_after_each_call = True
            print(self.instrumentLinear)
            print('Линейка подключена')
        except (IOError, AttributeError, ValueError) as err: # minimalmodbus.serial.serialutil.SerialException:
            message = "Привод линейки не виден, Error: " + str(err)
            print(message)
            self.statusbar.showMessage(message)
            return False

        try:
            # Команда включения серво; 0x0405 - адрес параметра; 0x83 - значение параметра
            self.instrumentLinear.write_register(0x00F, 1)
            return True
        except (IOError, AttributeError, ValueError) as err: # minimalmodbus.serial.serialutil.SerialException:
            message = "Запуск привода линейки не удался, Error: " + str(err)
            print(message)
            self.statusbar.showMessage(message)
            return False

    def CalibrateThread(self) -> None:
        ''' Калибровка позиционирования поворотом на 360 и перемещением вверх-вниз до концевиков '''
        self.thread1 = threading.Thread(target=self.Calibrate)
        self.thread1.start()

    def Calibrate(self) -> None:
        ''' Калибровка позиционирования поворотом на 360 и перемещением вверх-вниз до концевиков '''
        try:
            # Калибровка вращения
            if self.GetData()[6] == "NULL":
                self.RotateCW()
                while self.GetData()[6] == "NULL":
                    time.sleep(0.5)
                self.StopRotor()
                time.sleep(0.5)

            # Калибровка линейного перемещения
            if self.GetData()[4] == "NULL":
                self.LinearMotionUp() # Вверх
                while self.instrumentLinear.read_register(0x0179) != 1:
                    time.sleep(0.5)
                self.LinearMotionDown() # Вниз
                while self.instrumentLinear.read_register(0x0179) != 2:
                    time.sleep(0.5)
                self.StopLinear()

            line = self.GetData()
            if (line[4] != 'NULL') and (line[6] != 'NULL'):
                message = 'Калибровка завершена успешно'
                print(message)
                self.statusbar.showMessage(message)
                self.pBtn_Calibrate.setStyleSheet('QPushButton {background-color : forestgreen;}'
                                                'QPushButton:hover { background-color: #45a049;}')
            else:
                message = 'Повторите калибровку'
                print(message)
                self.statusbar.showMessage(message)
                print(line)
        except (IOError, AttributeError, ValueError): # minimalmodbus.serial.serialutil.SerialException:
            message = "Подключите приводы"
            print(message)
            self.statusbar.showMessage(message)
        
    def RotateCW(self, speed=5) -> None:
        ''' Запуск вращения по часовой '''
        try:
            '''
            Формирование массива параметров для команды:
            0x0002 - режим управления скоростью, записывается по адресу 0x6200
            0x0000 - верхние два байта кол-ва оборотов (=0 для режима управления скоростью), записывается по адресу 0x6201
            0x0000 - нижние два байта кол-ва оборотов  (=0 для режима управления скоростью), записывается по адресу 0x6202
            0x03E8 - значение скорости вращения (1000 об/мин), записывается по адресу 0x6203
            0x03E8 - значение времени ускорения (1000 мс), записывается по адресу 0x6204
            0x03E8 - значение времени торможения (1000 мс), записывается по адресу 0x6205
            0x0000 - задержка перед началом движения (0 мс), записывается по адресу 0x6206
            0x0010 - значение триггера для начала движения, записывается по адресу 0x6207
            '''
            message = "Движение запущено"
            print(message)
            self.statusbar.showMessage(message)
            self.instrumentRotor.write_registers(0x6200, [0x0002, 0x0000, 0x0000, speed, 0x03E8, 0x03E8, 0x0000, 0x0010])
        except (IOError, AttributeError, ValueError):
            message = "Команда для движения не прошла"
            print(message)
            self.statusbar.showMessage(message)

    def RotateCCW(self, speed=5) -> None:
        ''' Запуск вращения против часовой '''
        speed = 65536-speed
        try:
            message = "Движение запущено"
            print(message)
            self.statusbar.showMessage(message)
            self.instrumentRotor.write_registers(0x6200, [0x0002, 0x0000, 0x0000, speed, 0x03E8, 0x03E8, 0x0000, 0x0010])
        except (IOError, AttributeError, ValueError):
            message = "Команда для движения не прошла"
            print(message)
            self.statusbar.showMessage(message)

    def LinearMotionDown(self, speed=200) -> None:
        ''' Запуск движения по образующей вниз '''
        try:
            '''
            Формирование массива параметров для команды:
            0x0002 - режим управления скоростью, записывается по адресу 0x6200
            0x0000 - верхние два байта кол-ва оборотов (=0 для режима управления скоростью), записывается по адресу 0x6201
            0x0000 - нижние два байта кол-ва оборотов  (=0 для режима управления скоростью), записывается по адресу 0x6202
            0x03E8 - значение скорости вращения (1000 об/мин), записывается по адресу 0x6203
            0x0064 - значение времени ускорения (100 мс/1000rpm), записывается по адресу 0x6204
            0x0064 - значение времени торможения (100 мс/1000rpm), записывается по адресу 0x6205
            0x0000 - задержка перед началом движения (0 мс), записывается по адресу 0x6206
            0x0010 - значение триггера для начала движения, записывается по адресу 0x6207 '''
            message = "Движение запущено"
            print(message)
            self.statusbar.showMessage(message)
            self.instrumentLinear.write_registers(0x6200, [0x0002, 0x0000, 0x0000, speed, 0x0064, 0x0064, 0x0000, 0x0010])
        except (IOError, AttributeError, ValueError):
            message = "Команда для движения не прошла"
            print(message)
            self.statusbar.showMessage(message)

    def LinearMotionUp(self, speed=200) -> None:
        ''' Запуск движения по образующей вверх '''
        speed = 65536-speed # Скорость "отрицательная"
        try:
            message = "Движение запущено"
            print(message)
            self.statusbar.showMessage(message)
            self.instrumentLinear.write_registers(0x6200, [0x0002, 0x0000, 0x0000, speed, 0x0064, 0x0064, 0x0000, 0x0010])
        except (IOError, AttributeError, ValueError):
            message = "Команда для движения не прошла"
            print(message)
            self.statusbar.showMessage(message)

    def AbsPositionThread(self) -> None:
        ''' Перемещение каретки в заданные координаты Zpos PHIpos '''
        self.thread4 = threading.Thread(target=self.AbsPosition)
        self.thread4.start()

    def AbsPosition(self) -> None:
        ''' Перемещение каретки в заданные координаты Zpos PHIpos '''
        Zpos = int(self.dSpBox_Pos_Z.value()*1000) # Считываем мм, переводим в мкм и округляем до целого
        self.LinearPositioning(Zpos+self.ZeroZ)
        PHIpos = self.dSpBox_Pos_PHI.value() # Угловое положение в градусах с точностью до 3-го знака
        self.AngularPositioning(PHIpos + self.ZeroPhi)
        line = self.GetData()
        print('Приехали в точку: Z=', line[3]-self.ZeroZ, ' Phi=', line[5]-self.ZeroPhi)

    def LinearPositioning(self, Zpos: int) -> None:
        ''' Перемещение каретки в заданную координату Zpos '''
        line = self.GetData()
        distance = line[3] - Zpos
        print('Перемещение по образующей')
        count = 0
        while abs(distance) > 1 and count < 3:
            if self.pBtn_ScanGeneratrixStop.isChecked():
                break
            self.SimpleStepLinear(speed=100, step=-1*int(distance*2))
            line = self.GetData()
            distance = line[3] - Zpos
            # print(count, distance)
            count += 1

    def AngularPositioning(self, PHIpos: float) -> None:
        ''' Перемещение каретки в заданную координату PHIpos '''
        line = self.GetData()
        distance = (PHIpos-line[5])%360
        if distance > 180: distance -= 360 # Чтобы вращалось не более чем полокружности
        print(f'Вращение на {distance:.2f} градусов')
        if abs(distance) > 50:
            turnspeed = 3
        elif abs(distance) > 20:
            turnspeed = 2
        else:
            turnspeed = 1
        count = 0
        while abs(distance*100) > 2 and count < 2:
            if self.pBtn_ScanGeneratrixStop.isChecked():
                break
            self.SimpleStepRotor(speed=turnspeed, angle=round(distance*100))
            line = self.GetData()
            distance = (PHIpos-line[5])%360
            if 180 < distance < 360: distance -= 360
            turnspeed = 1
            count += 1

    def SetZeroPhi(self) -> None:
        ''' Задать нулевую точку отсчёта по вращению '''
        line = self.GetData()
        self.ZeroPhi = round(float(line[5]), 3)
        message = ''.join(["Установлено начало координат по вращению - ", str(self.ZeroPhi)])
        print(message)
        self.statusbar.showMessage(message)

    def SetZeroZ(self) -> None:
        ''' Задать нулевую точку отсчёта по образующей '''
        line = self.GetData()
        self.ZeroZ = int(line[3])
        message = ''.join(["Установлено начало координат по образующей - ", str(self.ZeroZ)])
        print(message)
        self.statusbar.showMessage(message)

    def SimpleStepLinear(self, speed=100, step=2000) -> int:
        ''' Простой шаг по образующей на заданное расстояние '''
        sleepStep = abs(step)/speed/100 # Время на паузу в сек, чтобы мотор успел прокрутиться
        if sleepStep < 0.2: sleepStep = 0.2
        Z0 = self.GetData()[3] # Запоминаем начальную позицию
        step *= -1 # Ось линейки направлена вверх, а ось двигателя - вниз, поэтому меняется знак
        if step < 0:
            step = 0xFFFFFFFF+step
        step1, step2 = divmod(step, 0x10000) # Разбиваем шаг на регистры. Верхний регистр обычно по нулям
        '''
        Формирование массива параметров для команды:
        0x0041 - 65 - режим однократного увеличения позиции (шаг), записывается по адресу 0x6200
        0x0000 - верхние два байта кол-ва оборотов (=0 обычно), записывается по адресу 0x6201
        0x0000 - нижние два байта кол-ва оборотов  (=шаг), записывается по адресу 0x6202
        0x0000 - значение скорости вращения (об/мин), записывается по адресу 0x6203
        0x0064 - значение времени ускорения (100 мс), записывается по адресу 0x6204
        0x0064 - значение времени торможения (100 мс), записывается по адресу 0x6205
        0x000A - задержка перед началом движения (10 мс), записывается по адресу 0x6206
        0x0010 - значение триггера для начала движения, записывается по адресу 0x6207
        ''' 
        try:
            self.instrumentLinear.write_registers(0x6200, [0x0041, step1, step2, speed, 0x0064, 0x0064, 0x0000, 0x0010])
            time.sleep(sleepStep) # Пауза, чтобы мотор успел прокрутиться
            realstep = self.GetData()[3]-Z0

        except (IOError, AttributeError, ValueError):
            message = "Команда на линейный шаг не прошла"
            print(message)
            realstep = 0

        return realstep

    def SimpleStepRotor(self, speed=1, angle=100) -> int:
        ''' Простой поворот на заданный угол '''
        sleepStep = abs(angle)/speed/400 # Время на паузу в сек, чтобы мотор успел прокрутиться
        if sleepStep < 0.5: sleepStep = 0.5
        PHI0 = self.GetData()[5] # Запоминаем начальный угол
        if angle<0:
            angle = 0xFFFFFFFF+angle
        step1, step2 = divmod(angle, 0x10000)
        '''
        Формирование массива параметров для команды:
        0x0041 - 65 - режим однократного увеличения позиции (шаг), записывается по адресу 0x6200
        0x0000 - верхние два байта кол-ва оборотов (=0 обычно), записывается по адресу 0x6201
        0x0000 - нижние два байта кол-ва оборотов  (=шаг), записывается по адресу 0x6202
        0x0000 - значение скорости вращения (об/мин), записывается по адресу 0x6203
        0x03E8 - значение времени ускорения (1000 мс), записывается по адресу 0x6204
        0x03E8 - значение времени торможения (1000 мс), записывается по адресу 0x6205
        0x000A - задержка перед началом движения (10 мс), записывается по адресу 0x6206
        0x0010 - значение триггера для начала движения, записывается по адресу 0x6207
        '''
        try:
            self.instrumentRotor.write_registers(0x6200, [0x0041, step1, step2, speed, 0x03E8, 0x03E8, 0x0000, 0x0010])
            time.sleep(sleepStep) # Пауза на поворот
            rotationstep = self.GetData()[5]-PHI0

        except (IOError, AttributeError, ValueError):
            message = "Команда на поворот не прошла"
            print(message)
            self.statusbar.showMessage(message)
            rotationstep = 0

        return rotationstep

    def PresizeStepRotor(self, speed=1, angle=100) -> int:
        ''' Точный поворот на заданный угол '''
        # угол указывается в сотых долях градуса (1 градус = 100 импульсов энкодера)
        line = self.GetData()
        PHI0 = line[5]*100 # Запоминаем начальный угол
        PHIFinish = (PHI0 + angle)%360 # Куда надо докрутить

        angle2Go = angle # angle2Go - сколько осталось пройти
        count = 0
        while angle2Go > 1.5 and count < 5:
            rotationstep = self.SimpleStepRotor(speed, round(angle2Go*0.9))
            line = self.GetData()
            angle2Go = (PHIFinish-line[5]*100)%360
            if angle2Go > 100: angle2Go = 0
            count += 1

        line = self.GetData()
        realrotation = round((line[5] - PHI0/100)%360, 2) # На сколько реально прокрутился ротор
        return realrotation

    def Stop(self) -> None:
        ''' Остановить оба двигателя ''' 
        self.StopRotor()
        self.StopLinear()

    def StopRotor(self) -> None:
        ''' Остановить вращение ротора '''
        try:
            self.instrumentRotor.write_registers(0x6002, [0x0040])
            print('Стоп!')
        except (IOError, AttributeError, ValueError):
            message = "Команда не прошла"
            print(message)

    def StopLinear(self) -> None:
        ''' Остановить линейное движение '''
        try:
            self.instrumentLinear.write_registers(0x6002, [0x0040])
            print('Стоп!')
        except (IOError, AttributeError, ValueError):
            message = "Команда не прошла"
            print(message)

    def ScanGeneratrix(self, steps: int, step: int) -> None:
        ''' Сканирование в одну сторону вдоль образующей ротора '''
        # steps - количество точек сканирования, шт
        # step  - расстояние между точками, имп (2 имп/мкм)
        
        GeneratrixScanStepData = pd.Series()
        ZerrAlert = False
        line = self.GetData()
        line[3] = round(line[3] - self.ZeroZ)
        line[5] = round(line[5] - self.ZeroPhi, 3)%360
        self.data.loc[len(self.data)] = line
        step *= -1 # Меняем знак, потому что ось двигателя и ось энкодера разнонаправлены
        gap = 0
        for s in range(steps):
            if self.pBtn_ScanGeneratrixStop.isChecked():
                break
            jump = step + gap # gap - поправка с учётом точности предыдущего шага
            realstep = self.SimpleStepLinear(speed=100, step=jump) # Делаем шаг, вычисляем реальное перемещение в мкм.
            gap = int(step - 2*realstep + gap) # Разница между заданным и искомым перемещением с учётом предыдущей поправки
            GeneratrixScanStepData.loc[len(GeneratrixScanStepData)] = realstep
            line = self.GetData()
            line[3] = round(line[3] - self.ZeroZ)
            line[5] = round(line[5] - self.ZeroPhi, 3)%360
            self.data.loc[len(self.data)] = line
            if line[4] <= 5:
                ZerrAlert = False
            elif not ZerrAlert and line[4] > 30:
                message = "Ошибка измерения Zerr больше 30!"
                print(message)
                self.statusbar.showMessage(message)
                ZerrAlert = True

        print('Среднее значение шага по образующей:', GeneratrixScanStepData.mean())

    def ScanThread(self) -> None:
        ''' Сканирование по образующей вниз и вверх от заданных границ '''
        self.thread2 = threading.Thread(target=self.Scan)
        self.thread2.start()

    def Scan(self) -> None:
        ''' Сканирование по образующей вниз и вверх от заданных границ '''
        self.data = pd.DataFrame(columns=['Bx', 'By', 'Bz', 'Z', 'Zerr', 'PHI', 'PHIerr', 'T'])

        line = self.GetData()

        self.AbsPosition()

        start = round(self.dSpBox_Pos_Z.value()*1000)+self.ZeroZ # Координаты точки начала измерений по Z, в мкм
        distance = round(self.dSpBox_Range_Z.value()*1000) # Дистанция прохода по образующей в мкм
        step = int(self.LinearStep*2000/1000) # Шаг вдоль образующей в импульсах двигателя (2000 имп/мм)
        
        steps = round(distance/self.LinearStep) # Количество шагов на образующую
        finish = start + self.LinearStep*steps # Уточнённое значение нижнего лимита по образующей

        imp_in_degree = 100 # Количество импульсов двигателя на угловой градус
        rotation = round(self.dSpBox_ScanStepAngle.value()*imp_in_degree)

        self.pBtn_ScanGeneratrixStop.setChecked(False)
        self.pBtn_ScanGeneratrix.setStyleSheet('QPushButton {background-color : green;}')

        message = "Съёмка начата"
        print(message)
        self.statusbar.showMessage(message)

        NumberOfRuns = round(self.dSpBox_Range_PHI.value()/(2*self.dSpBox_ScanStepAngle.value())) # Задаём количество шагов по окружности (пополам, потому что вверх-вниз)
        self.rotationgap = 0
        for n in range(NumberOfRuns+1):
            print('Проход номер', n)

            if self.pBtn_ScanGeneratrixStop.isChecked():
                break

            # Выборка люфта снизу
            self.SimpleStepLinear(speed=100, step=-4000)
            self.SimpleStepLinear(speed=100, step=3000)

            line = self.GetData()
            shift = start-line[3]

            # Парковка
            print('Парковка по нижней границе и движение вверх...')
            count = 0
            while shift > 2 and count < 5:
                time.sleep(0.5)
                self.SimpleStepLinear(speed=100, step=int(shift*1.9))
                line = self.GetData()
                shift = start-line[3]
                count += 1
            
            # Движение вверх
            self.ScanGeneratrix(steps=steps, step=-step)

            if self.pBtn_ScanGeneratrixStop.isChecked():
                break

            # Шаг по окружности
            realrotation = self.PresizeStepRotor(speed=1, angle=(rotation+self.rotationgap))
            self.rotationgap = round(rotation - realrotation*100 + self.rotationgap)
            print('Поворот на угол - ', realrotation)

            time.sleep(1)

            line = self.GetData()
            shift = line[3]-finish

            # Выборка люфта сверху
            self.SimpleStepLinear(speed=100, step=4000)
            self.SimpleStepLinear(speed=100, step=-3000)

            line = self.GetData()
            shift = line[3]-finish

            # Парковка
            print('Парковка по верхней границе и движение вниз...')
            count = 0
            while shift > 2 and count < 5:
                time.sleep(0.5)
                self.SimpleStepLinear(speed=100, step=-1*int(shift*1.9))
                line = self.GetData()
                shift = line[3]-finish
                count += 1
            
            # Движение вниз
            self.ScanGeneratrix(steps=steps, step=step)

            if self.pBtn_ScanGeneratrixStop.isChecked():
                break

            # Шаг по окружности
            realrotation = self.PresizeStepRotor(speed=1, angle=(rotation+self.rotationgap))
            self.rotationgap = round(rotation - realrotation*100 + self.rotationgap)
            print('Поворот на угол - ', realrotation)
            
            time.sleep(1)
            
            line = self.GetData()
            # print('Нижняя координата', line[3])
            shift = start-line[3]

        self.pBtn_ScanGeneratrixStop.setChecked(False)
        self.pBtn_ScanGeneratrix.setStyleSheet('QPushButton {background-color : #E1E1E1;}'
                                               'QPushButton:hover { background-color: #66FF66;}')
        self.pBtn_ScanGeneratrixStop.setStyleSheet('QPushButton {background-color : #E1E1E1;}'
                                                   'QPushButton:hover { background-color: salmon;}')
        
        # Сохранение датафрейма в файл
        self.data['Zx'] = self.data['Z'] + 2000
        self.data['Zy'] = self.data['Z']
        self.data['Zz'] = self.data['Z'] - 2000
        self.data = self.data[['Bx', 'By', 'Bz', 'Zx', 'Zy', 'Zz', 'Zerr', 'PHI', 'PHIerr', 'T']]
        datadir = 'data'
        filename = time.strftime("%Y-%m-%d_%H-%M")
        os.makedirs(datadir, exist_ok = True)
        self.data.to_csv(os.path.join(datadir, f'data_{filename}.csv'))
        self.LayersSum()
        message = 'Съёмка завершена!'
        print(message)
        self.statusbar.showMessage(message)

    def ScanRotorFastThread(self) -> None:
        ''' Сканирование поверхности ротора в спиральном режиме '''
        self.thread3 = threading.Thread(target=self.ScanRotorFast)
        self.thread3.start()

    def ScanRotorFast(self) -> None:
        ''' Сканирование поверхности ротора в спиральном режиме '''
        self.data = pd.DataFrame(columns=['Bx', 'By', 'Bz', 'Z', 'Zerr', 'PHI', 'PHIerr', 'T'])

        # self.AbsPosition()
        line = self.GetData()
        start = line[3]
        print('Start:', start)
        finish = int(line[3]+self.dSpBox_Range_Z_spiral.value()*1000)
        print('Finish:', finish)
        line[3] = round(line[3] - self.ZeroZ)
        line[5] = round(line[5] - self.ZeroPhi, 3)%360
        self.data.loc[len(self.data)] = line

        self.pBtn_ScanRotorSpiralStop.setChecked(False)
        self.pBtn_ScanRotorSpiral.setStyleSheet('QPushButton {background-color : green;}')
        self.RotateCW(speed=5)
        self.LinearMotionUp(speed=1)

        scan = True
        while scan:
            line = self.GetData()
            if line[3] > finish:
                scan = False
            if self.pBtn_ScanRotorSpiralStop.isChecked():
                scan = False
            line[3] = round(line[3] - self.ZeroZ)
            line[5] = round(line[5] - self.ZeroPhi, 3)%360
            self.data.loc[len(self.data)] = line
            time.sleep(0.05)

        self.pBtn_ScanRotorSpiralStop.setChecked(False)
        self.pBtn_ScanRotorSpiralStop.setStyleSheet('QPushButton {background-color : #E1E1E1;}'
                                                    'QPushButton:hover { background-color: salmon;}')
        self.pBtn_ScanRotorSpiral.setStyleSheet('QPushButton {background-color : #E1E1E1;}'
                                                'QPushButton:hover { background-color: #66FF66;}')
        self.StopRotor()
        self.StopLinear()

        print('Конец сканирования!')
        self.data['Zx'] = self.data['Z'] + 2000
        self.data['Zy'] = self.data['Z']
        self.data['Zz'] = self.data['Z'] - 2000
        self.data = self.data[['Bx', 'By', 'Bz', 'Zx', 'Zy', 'Zz', 'Zerr', 'PHI', 'PHIerr', 'T']]
        # self.data.reindex(columns=['Bx', 'By', 'Bz', 'Zx', 'Zy', 'Zz', 'Zerr', 'PHI', 'PHIerr', 'T'])
        datadir = 'data'
        filename = time.strftime('%Y-%m-%d_%H-%M')
        os.makedirs(datadir, exist_ok = True)
        self.data.to_csv(os.path.join(datadir, f'qdata_{filename}.csv'))
        self.LayersSum()
        message = 'Съёмка завершена!'
        print(message)
        self.statusbar.showMessage(message)

    def ShowData(self) -> None:
        ''' Отражение данных с дата-порта в GUI '''
        line = self.GetData()
        text = ''.join(['B = ', str(line[:3]), '\nZ = ', str(line[3:5]), '\nPhi=', str(line[5:7]), '\nT = ', str(line[7:])])
        self.txtBrwser_ShowData.setText(text)

    def GetData(self) -> list:
        ''' Получение данных с дата-порта '''
        try:
            with (serial.Serial(self.cBox_PortData.currentText(), baudrate=115200)) as self.serialData:
                # Read data from COM port
                command = 'R'
                # Send the command to the DataPort
                self.serialData.write(command.encode())
                line = str(self.serialData.readline().strip()).split(';') # Строка вида
            # self.lbl_Data.setText(str(line))
            Bx = float(line[0][5:-3].replace(',','.'))
            By = float(line[1][4:-3].replace(',','.'))
            Bz = float(line[2][4:-3].replace(',','.'))
            Z = int(line[3][3:-3].replace(',','.'))
            try:    Zerr = int(line[4][6:-3].replace(',','.'))
            except: Zerr = line[4][6:]
            PHI = float(line[5][5:-4].replace(',','.'))
            try:    PHIErr = float(line[6][8:-4].replace(',','.'))
            except: PHIErr = line[6][8:]
            T = float(line[7][3:-7].replace(',','.'))

            return [Bx, By, Bz, Z, Zerr, PHI, PHIErr, T]

        except ValueError as ve:
            print("Error:", str(ve))
            print(line)
        except serial.SerialException as se: 
            print("Serial port error:", str(se))
            print(line)
        except Exception as e:               
            print("An error occurred:", str(e))
            print(line)

        return [0, 0, 0, 0, 0, 0, 0, 0]

    def SaveConfig(self) -> None:
        ''' Сохранение настроек в файл '''
        config_data = {
            'Date': self.tab1_dateEdit.text(),
            'Time': self.tab1_timeEdit.text(),
            'FIO': self.tab1_lEd_FIO.text(),
            'RtrName': self.tab1_lEd_RotorName.text(),
            'RtrNumber': self.tab1_lEd_RotorNum.text(),
            'RtrDiam': self.lEd_RotorDiam.text(),
            'RtrHght': self.lEd_RotorHght.text(),
            'ZeroPhi': self.ZeroPhi,
            'ZeroZ': self.ZeroZ}
        with open('config.json', 'w') as config_file: 
            json.dump(config_data, config_file)

    # Графический блок

    def SetFieldComponent(self, index: int):
        self.graphWidget.clear()
        match index:
            case 0:
                self.componentName = 'Bx'
            case 1:
                self.componentName = 'By'
            case 2:
                self.componentName = 'Bz'
                      
    def ShowGraph(self):
        ''' Отображение датафрейма в html '''
        self.TrueZ()       
        self.filename = 'graph.html'
        src = [
            go.Scatter(
                x=self.data["PHI"],
                y=self.data[self.coordZ],
                mode="markers",
                marker=dict(
                    colorscale="RdBu",
                    showscale=True,
                    color=self.data[self.componentName],
                line=dict(color="white", width=0.01),
                ),
            )
        ]

        figure = go.Figure(
            data=src,
            layout=go.Layout(
                xaxis=dict(title="Угловая позиция"),
                yaxis=dict(title="Z"),
                title=f"Распределение {self.componentName}",
            ),
        )
        offline.plot(figure, filename = self.filename, auto_open = True)
 
    def LayersSum(self):
        self.TrueZ()
        layersSum = len(self.uniq_Z)
        self.lbl_LayersSum.setText(str(layersSum))
        self.spBox_LayerNum.setRange(1, layersSum)
        print('Всего слоев', layersSum)

    def TrueZ(self):
        match self.componentName:
            case 'Bx':
                self.coordZ = 'Zx'
            case 'By':
                self.coordZ = 'Zy'
            case 'Bz':
                self.coordZ = 'Zz'
        
        uniq_phi = self.data['PHI'].unique()
        self.uniq_Z = self.data[self.data['PHI'] == uniq_phi[0]].loc[::, self.coordZ].unique()

    def DataPrepare(self):
        self.TrueZ()
        indices = []
        levelNumber = self.spBox_LayerNum.value()
        Z = self.data[self.coordZ]

        for i, item in enumerate(Z):
            if round(item, -2) == round(self.uniq_Z[levelNumber-1], -2):
                indices.append(i)
               
        self.x_coord = self.data.loc[indices, 'PHI'].tolist()
        self.y_coord = self.data.loc[indices, self.componentName].tolist()
       
    def PlotData(self):
        ''' Отрисовка графика в поле '''
        self.DataPrepare()
        styles = {'color': 'black', 'font-size': '12px'}
        self.graphWidget.setLabel('left', f"Индукция {self.componentName}", **styles)
        self.graphWidget.setLabel('bottom', "Угол поворота ротора", **styles)
        self.graphWidget.showGrid(x = True, y = True)
        self.graphWidget.setXRange(min(self.x_coord), max(self.x_coord))
        self.graphWidget.setYRange(min(self.y_coord), max(self.y_coord))
        self.plotData = self.graphWidget.plot(x = self.x_coord, y = self.y_coord, pen = 'b', symbol = 'h')

    def SaveImg(self):
        ''' Сохранение графика в файл '''
        graphDir = 'graph'
        filename = time.strftime("%Y-%m-%d_%H-%M")
        os.makedirs(graphDir, exist_ok = True)
        plt.plot(self.x_coord, self.y_coord, marker = 'o')
        plt.grid(visible = True, which = 'both', axis = 'both', color = 'grey', linestyle = ':', linewidth = 0.5)
        plt.xlabel("Угол поворота ротора")
        plt.ylabel(f"Индукция {self.componentName}")
        plt.savefig(os.path.join(graphDir, f"{filename}_{self.componentName}_layer_{self.spBox_LayerNum.value()}.jpg"), dpi = 300)
        plt.close()
        print('График сохранен успешно')

if __name__ == '__main__':
    app = QApplication([])
    
    rotor = MainUI()
    rotor.show()
    
    sys.exit(app.exec_())