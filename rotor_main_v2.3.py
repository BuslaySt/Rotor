from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.uic import loadUi
import sys, datetime, time, json
import minimalmodbus, serial

import pandas as pd
import plotly.graph_objs as go
import plotly.offline as offline

class MainUI(QMainWindow):
    def __init__(self):
        super(MainUI, self).__init__()
        loadUi("rotor_ui_v2.3.ui", self)

        try:
            with open('config.json', 'r') as config_file: 
                config_data = json.load(config_file)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            print('Файл конфига повреждён или отсутствует')
            config_data = {
                'Date': '01.11.2024',
                'Time': '12:12',
                'FIO': 'Имя Фамилия',
                'RtrName': 'RotorName',
                'RtrNumber': 'RotorNunber',
                'RtrDiam': 155,
                'RtrHght': 140,
                'ZeroPhi': 0,
                'ZeroZ': 0}

        self.pBtn_SaveConfig.clicked.connect(self.SaveConfig)
        
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

        self.lEd_RotorDiam.textChanged.connect(self.Angle2MM)
        self.lEd_RotorHght.textChanged.connect(self.SetScanHeight)
        
        # Окно настроек
        self.pBtn_Init.clicked.connect(self.Init)
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

        # self.pBtn_UpperLimit.clicked.connect(self.SetUpperLimit)
        self.pBtn_LowerLimit.clicked.connect(self.PresizeStepRotor)

        # Окно точного шагания
        self.cBox_ScanStepGeneratrix.addItems(['0,5 мм', '1 мм', '2 мм','4 мм'])
        self.cBox_ScanStepGeneratrix.setCurrentIndex(1)
        self.LinearStep = 1000 # 1mm default
        self.cBox_ScanStepGeneratrix.currentIndexChanged.connect(self.SetupScanStepGeneratrix)
        self.pBtn_Position.clicked.connect(self.AbsPositioning)
        self.lEd_ScanStepAngle.textChanged.connect(self.Angle2MM)
        self.pBtn_ScanGeneratrix.clicked.connect(self.Scan)
        self.pBtn_ShowData.clicked.connect(self.ShowData)

        # Окно вывода результатов
        self.pBtn_Result.clicked.connect(self.ShowGraph)

    def SetScanHeight(self) -> None:
        ''' Введённая высота ротора записывается как высота области сканирования '''
        self.lEd_Range_Z.setText(self.lEd_RotorHght.text())

    def SetupScanStepGeneratrix(self, index: int) -> None:
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
            millimeters = round(float(self.lEd_ScanStepAngle.text())*3.14159*int(self.lEd_RotorDiam.text())/360, 3)
            self.lbl_ScanStepAngleMM.setText(str(millimeters))
        except ValueError:
            pass

    def Init(self) -> None:
        self.InitRotMotor()
        self.InitLinearMotor()

    def InitRotMotor(self) -> None:
        try: # Инициализация двигателя вращения ротора
            # Modbus-адрес драйвера по умолчанию - 1
            self.instrumentRotor = minimalmodbus.Instrument('COM9', 1) #COM9, 1 - вращение, 2 - линейка
            # Настройка порта: скорость - 38400 бод/с, четность - нет, кол-во стоп-бит - 2.
            self.instrumentRotor.mode = minimalmodbus.MODE_RTU
            print(self.instrumentRotor.serial.port)
            self.instrumentRotor.serial.baudrate = 38400
            self.instrumentRotor.serial.parity = minimalmodbus.serial.PARITY_NONE
            self.instrumentRotor.serial.stopbits = 2
            # self.instrumentRotor.serial.databits = 8
            self.instrumentRotor.serial.timeout  = 0.05          # seconds
            # self.instrumentRotor.close_port_after_each_call = True
            print(self.instrumentRotor)
            print('Вращение подключено')
        except (IOError, AttributeError, ValueError): # minimalmodbus.serial.serialutil.SerialException:
            message = "Привод вращения не виден"
            print(message)

        try:
            # Команда включения серво; 0x0405 - адрес параметра; 0x83 - значение параметра
            self.instrumentRotor.write_registers(0x00F, [1])
        except (IOError, AttributeError, ValueError): # minimalmodbus.serial.serialutil.SerialException:
            message = "Запуск привода вращения не удался"
            print(message)

    def InitLinearMotor(self) -> None:
        try: # Инициализация двигателя линейки
            # Modbus-адрес драйвера по умолчанию - 1
            self.instrumentLinear = minimalmodbus.Instrument('COM9', 2) #COM9, 1 - вращение, 2 - линейка
            # Настройка порта: скорость - 38400 бод/с, четность - нет, кол-во стоп-бит - 2.
            self.instrumentLinear.mode = minimalmodbus.MODE_RTU
            print(self.instrumentLinear.serial.port)
            self.instrumentLinear.serial.baudrate = 38400
            self.instrumentLinear.serial.parity = minimalmodbus.serial.PARITY_NONE
            self.instrumentLinear.serial.stopbits = 2
            # self.instrumentLinear.serial.databits = 8
            self.instrumentLinear.serial.timeout  = 0.05          # seconds
            # self.instrumentLinear.close_port_after_each_call = True
            print(self.instrumentLinear)
            print('Линейка подключена')
        except (IOError, AttributeError, ValueError): # minimalmodbus.serial.serialutil.SerialException:
            message = "Привод линейки не виден"
            print(message)

        try:
            # Команда включения серво; 0x0405 - адрес параметра; 0x83 - значение параметра
            self.instrumentLinear.write_registers(0x00F, [1])
            # self.instrumentLinear.write_registers(0x0007, [0x0000])
        except (IOError, AttributeError, ValueError): # minimalmodbus.serial.serialutil.SerialException:
            message = "Запуск привода линейки не удался"
            print(message)

    def RotateCW(self) -> None:
        try:
            speed = int(self.lEd_RotorSpeed.text())
        except ValueError:
            speed = 1
            self.lEd_RotorSpeed.setText('1')
            message = "Скорость задана неверно"
            print(message)
            self.statusbar.showMessage(message)
        try:
            # Формирование массива параметров для команды:
            # 0x0002 - режим управления скоростью, записывается по адресу 0x6200
            # 0x0000 - верхние два байта кол-ва оборотов (=0 для режима управления скоростью), записывается по адресу 0x6201
            # 0x0000 - нижние два байта кол-ва оборотов  (=0 для режима управления скоростью), записывается по адресу 0x6202
            # 0x03E8 - значение скорости вращения (1000 об/мин), записывается по адресу 0x6203
            # 0x03E8 - значение времени ускорения (1000 мс), записывается по адресу 0x6204
            # 0x03E8 - значение времени торможения (1000 мс), записывается по адресу 0x6205
            # 0x0000 - задержка перед началом движения (0 мс), записывается по адресу 0x6206
            # 0x0010 - значение триггера для начала движения, записывается по адресу 0x6207
            message = "Движение запущено"
            print(message)
            self.statusbar.showMessage(message)
            self.instrumentRotor.write_registers(0x6200, [0x0002, 0x0000, 0x0000, speed, 0x03E8, 0x03E8, 0x0000, 0x0010])
        except (IOError, AttributeError, ValueError):
            message = "Команда для движения не прошла"
            print(message)
            self.statusbar.showMessage(message)

    def RotateCCW(self) -> None:
        try:
            speed = 65536-int(self.lEd_RotorSpeed.text())
        except ValueError:
            speed = 65536-1
            self.lEd_RotorSpeed.setText('1')
            message = "Скорость задана неверно"
            print(message)
            self.statusbar.showMessage(message)
        try:
            # Формирование массива параметров для команды:
            # 0x0002 - режим управления скоростью, записывается по адресу 0x6200
            # 0x0000 - верхние два байта кол-ва оборотов (=0 для режима управления скоростью), записывается по адресу 0x6201
            # 0x0000 - нижние два байта кол-ва оборотов  (=0 для режима управления скоростью), записывается по адресу 0x6202
            # 0x03E8 - значение скорости вращения (1000 об/мин), записывается по адресу 0x6203
            # 0x03E8 - значение времени ускорения (1000 мс), записывается по адресу 0x6204
            # 0x03E8 - значение времени торможения (1000 мс), записывается по адресу 0x6205
            # 0x0000 - задержка перед началом движения (0 мс), записывается по адресу 0x6206
            # 0x0010 - значение триггера для начала движения, записывается по адресу 0x6207
            message = "Движение запущено"
            print(message)
            self.statusbar.showMessage(message)
            self.instrumentRotor.write_registers(0x6200, [0x0002, 0x0000, 0x0000, speed, 0x03E8, 0x03E8, 0x0000, 0x0010])
        except (IOError, AttributeError, ValueError):
            message = "Команда для движения не прошла"
            print(message)
            self.statusbar.showMessage(message)

    def LinearMotionDown(self) -> None:
        try:
            speed = int(self.lEd_LinearSpeed.text())
        except ValueError:
            speed = 100
            self.lEd_LinearSpeed.setText('100')
            message = "Скорость задана неверно"
            print(message)
            self.statusbar.showMessage(message)
        try:
            # Формирование массива параметров для команды:
            # 0x0002 - режим управления скоростью, записывается по адресу 0x6200
            # 0x0000 - верхние два байта кол-ва оборотов (=0 для режима управления скоростью), записывается по адресу 0x6201
            # 0x0000 - нижние два байта кол-ва оборотов  (=0 для режима управления скоростью), записывается по адресу 0x6202
            # 0x03E8 - значение скорости вращения (1000 об/мин), записывается по адресу 0x6203
            # 0x03E8 - значение времени ускорения (1000 мс), записывается по адресу 0x6204
            # 0x03E8 - значение времени торможения (1000 мс), записывается по адресу 0x6205
            # 0x0000 - задержка перед началом движения (0 мс), записывается по адресу 0x6206
            # 0x0010 - значение триггера для начала движения, записывается по адресу 0x6207
            message = "Движение запущено"
            print(message)
            self.statusbar.showMessage(message)
            self.instrumentLinear.write_registers(0x6200, [0x0002, 0x0000, 0x0000, speed, 0x0064, 0x0064, 0x0000, 0x0010])
        except (IOError, AttributeError, ValueError):
            message = "Команда для движения не прошла"
            print(message)
            self.statusbar.showMessage(message)

    def LinearMotionUp(self) -> None:
        try:
            speed = 65536-int(self.lEd_LinearSpeed.text())
        except ValueError:
            speed = 65536-100
            self.lEd_LinearSpeed.setText('100')
            message = "Скорость задана неверно"
            print(message)
            self.statusbar.showMessage(message)
        try:
            # Формирование массива параметров для команды:
            # 0x0002 - режим управления скоростью, записывается по адресу 0x6200
            # 0x0000 - верхние два байта кол-ва оборотов (=0 для режима управления скоростью), записывается по адресу 0x6201
            # 0x0000 - нижние два байта кол-ва оборотов  (=0 для режима управления скоростью), записывается по адресу 0x6202
            # 0x03E8 - значение скорости вращения (1000 об/мин), записывается по адресу 0x6203
            # 0x0064 - значение времени ускорения (1000 мс), записывается по адресу 0x6204
            # 0x0064 - значение времени торможения (1000 мс), записывается по адресу 0x6205
            # 0x0000 - задержка перед началом движения (0 мс), записывается по адресу 0x6206
            # 0x0010 - значение триггера для начала движения, записывается по адресу 0x6207
            message = "Движение запущено"
            print(message)
            self.statusbar.showMessage(message)
            self.instrumentLinear.write_registers(0x6200, [0x0002, 0x0000, 0x0000, speed, 0x0064, 0x0064, 0x0000, 0x0010])
        except (IOError, AttributeError, ValueError):
            message = "Команда для движения не прошла"
            print(message)
            self.statusbar.showMessage(message)

    def AbsMotion(self) -> None:
        ''' Перемещение в заданные координаты в системе двигателя'''
        coord1, coord2 = divmod(int(self.lEd_Pos.text()), 0x10000)
        try:
            # Формирование массива параметров для команды:
            # 0x0002 - режим управления скоростью, записывается по адресу 0x6200
            # 0x0000 - верхние два байта кол-ва оборотов (=0 для режима управления скоростью), записывается по адресу 0x6201
            # 0x0000 - нижние два байта кол-ва оборотов  (=0 для режима управления скоростью), записывается по адресу 0x6202
            # 0x03E8 - значение скорости вращения (1000 об/мин), записывается по адресу 0x6203
            # 0x03E8 - значение времени ускорения (1000 мс), записывается по адресу 0x6204
            # 0x03E8 - значение времени торможения (1000 мс), записывается по адресу 0x6205
            # 0x0000 - задержка перед началом движения (0 мс), записывается по адресу 0x6206
            # 0x0010 - значение триггера для начала движения, записывается по адресу 0x6207
            message = "Движение запущено"
            print(message)
            self.statusbar.showMessage(message)
            self.instrumentLinear.write_registers(0x6200, [0x0001, coord1, coord2, 200, 1000, 1000, 0, 0x0010])

        except (IOError, AttributeError, ValueError):
            message = "Команда для движения не прошла"
            print(message)
            self.statusbar.showMessage(message)      

    def AbsPositioning(self) -> None:
        Zpos = int(round(float(self.lEd_Pos_Z.text()), 3)*1000) # Считываем мм, переводим в мкм и округляем до целого
        self.LinearPositioning(Zpos+self.ZeroZ)
        PHIpos = round(float(self.lEd_Pos_PHI.text()), 3) # Угловое положение в градусах с точностью до 3-го знака
        self.AngularPositioning(PHIpos + self.ZeroPhi)
        line = self.GetData()
        print('Приехали в точку: Z=', line[3]-self.ZeroZ, ' Phi=', line[5]-self.ZeroPhi)

    def LinearPositioning(self, Zpos: int) -> None:
        ''' Перемещение каретки в заданную координату Zpos '''
        line = self.GetData()
        distance = line[3] - Zpos
        print('Перемещение по образующей...')
        count = 0
        while abs(distance) > 1 and count < 5:
            time.sleep(0.5)
            self.SimpleStepLinear(speed=100, step=-1*int(distance*2))
            line = self.GetData()
            distance = line[3] - Zpos
            count += 1

    def AngularPositioning(self, PHIpos: float) -> None:
        ''' Перемещение каретки в заданную координату Zpos '''
        line = self.GetData()
        distance = PHIpos - line[5]
        print('Перемещение по радиусу...')
        count = 0
        while abs(distance*100) > 2 and count < 5:
            time.sleep(0.5)
            self.SimpleStepRotor(speed=1, angle=round(distance*100))
            line = self.GetData()
            distance = PHIpos - line[5]
            count += 1

    def SetUpperLimit(self) -> None:
        self.UpperLimit = int(self.GetData()[3])
        message = "".join(["Установлена верхняя граница ротора - ", str(self.UpperLimit)])
        print(message)
        self.statusbar.showMessage(message)
        self.pBtn_UpperLimit.setText("".join(["Верхняя граница ротора: ", str(self.UpperLimit)]))

    def SetLowerLimit(self) -> None:
        self.LowerLimit = int(self.GetData()[3])
        message = "".join(["Установлена нижняя граница ротора - ", str(self.LowerLimit)])
        print(message)
        self.statusbar.showMessage(message)
        self.pBtn_LowerLimit.setText("".join(["Нижняя граница ротора: ", str(self.LowerLimit)]))

    def SetZeroPhi(self) -> None:
        line = self.GetData()
        self.ZeroPhi = round(float(line[5]), 3)
        message = ''.join(["Установлено начало координат по вращению - ", str(self.ZeroPhi)])
        print(message)
        self.statusbar.showMessage(message)

    def SetZeroZ(self) -> None:
        line = self.GetData()
        self.ZeroZ = int(line[3])
        message = ''.join(["Установлено начало координат по образующей - ", str(self.ZeroZ)])
        print(message)
        self.statusbar.showMessage(message)

    def Step(self):
        ''' Функция для кнопки Шаг '''
        step = round(int(self.lEd_Step.text())*2000/1000)
        speed = int(self.lEd_LinearSpeed.text()) 
        print('Шаг на', self.SimpleStepLinear(speed=speed, step=step))

    def SimpleStepLinear(self, speed: int, step: int) -> int:
        ''' Простой шаг по образующей на заданное расстояние '''
        sleepStep = abs(step)/speed/100 # Время на паузу в сек, чтобы мотор успел прокрутиться
        if sleepStep < 0.3: sleepStep = 0.3
        Z0 = self.GetData()[3] # Запоминаем начальную позицию
        step *= -1 # Ось линейки направлена вверх, а ось двигателя - вниз, поэтому меняется знак
        if step < 0:
            step = 0xFFFFFFFF+step
        step1, step2 = divmod(step, 0x10000)
        # Формирование массива параметров для команды:
        # 0x0041 - 65 - режим однократного увеличения позиции (шаг), записывается по адресу 0x6200
        # 0x0000 - верхние два байта кол-ва оборотов (=0 обычно), записывается по адресу 0x6201
        # 0x0000 - нижние два байта кол-ва оборотов  (=шаг), записывается по адресу 0x6202
        # 0x0000 - значение скорости вращения (об/мин), записывается по адресу 0x6203
        # 0x0064 - значение времени ускорения (100 мс), записывается по адресу 0x6204
        # 0x0064 - значение времени торможения (100 мс), записывается по адресу 0x6205
        # 0x000A - задержка перед началом движения (10 мс), записывается по адресу 0x6206
        # 0x0010 - значение триггера для начала движения, записывается по адресу 0x6207
        try:
            self.instrumentLinear.write_registers(0x6200, [0x0041, step1, step2, speed, 0x0064, 0x0064, 0x0000, 0x0010])
            time.sleep(sleepStep) # Пауза, чтобы мотор успел прокрутиться
            realstep = self.GetData()[3]-Z0

        except (IOError, AttributeError, ValueError):
            message = "Команда на линейный шаг не прошла"
            print(message)
            realstep = 0

        return realstep

    def Rotate(self):
        ''' Оборот вокруг оси на заданное число градусов (шагов)'''
        rotationData = pd.Series()
        rotation = int(self.lEd_Rotation.text())
        line = self.GetData()
        start = line[5]
        for _ in range(5):
            time1 = time.time()
            realangle = self.SimpleStepRotor(speed=1, angle=rotation)
            rotationData.loc[len(rotationData)] = realangle
            time2 = time.time()
        line = self.GetData()
        finish = line[5]
        rotationData = rotationData.loc[(rotationData>-10)&(rotationData<10)]
        print(rotationData.describe())

    def SimpleStepRotor(self, speed: int, angle: int) -> int:
        ''' Простой поворот на заданный угол '''
        sleepStep = abs(angle)/speed/400 # Время на паузу в сек, чтобы мотор успел прокрутиться
        if sleepStep < 0.5: sleepStep = 0.5
        PHI0 = self.GetData()[5] # Запоминаем начальный угол
        if angle<0:
            angle = 0xFFFFFFFF+angle
        step1, step2 = divmod(angle, 0x10000)
        # Формирование массива параметров для команды:
        # 0x0041 - 65 - режим однократного увеличения позиции (шаг), записывается по адресу 0x6200
        # 0x0000 - верхние два байта кол-ва оборотов (=0 обычно), записывается по адресу 0x6201
        # 0x0000 - нижние два байта кол-ва оборотов  (=шаг), записывается по адресу 0x6202
        # 0x0000 - значение скорости вращения (об/мин), записывается по адресу 0x6203
        # 0x03E8 - значение времени ускорения (1000 мс), записывается по адресу 0x6204
        # 0x03E8 - значение времени торможения (1000 мс), записывается по адресу 0x6205
        # 0x000A - задержка перед началом движения (10 мс), записывается по адресу 0x6206
        # 0x0010 - значение триггера для начала движения, записывается по адресу 0x6207
        try:
            self.instrumentRotor.write_registers(0x6200, [0x0041, step1, step2, speed, 0x03E8, 0x03E8, 0x0000, 0x0010])
            time.sleep(sleepStep) # Пауза на поворот
            rotationstep = self.GetData()[5]-PHI0

        except (IOError, AttributeError, ValueError):
            message = "Команда на поворот не прошла"
            print(message)
            rotationstep = 0

        return rotationstep

    def PresizeStepRotor(self, speed=1, angle=100) -> int:
        ''' Точный поворот на заданный угол, указывается в сотых долях градуса (1 градус = 100) '''
        if self.sender() == self.pBtn_LowerLimit:
            ''' Точный поворот с кнопки Временно '''
            speed=1
            angle=36000

        line = self.GetData()
        PHI0 = line[5]*100 # Запоминаем начальный угол
        PHIFinish = PHI0 + angle # Куда надо докрутить

        angleShift = angle
        count = 0
        while angleShift > 0.5 and count < 5:
            rotationstep = self.SimpleStepRotor(speed, round(angleShift*0.8))
            line = self.GetData()
            angleShift = (PHIFinish-line[5]*100)%360
            count += 1
        
        line = self.GetData()
        realrotation = round((line[5] - PHI0/100)%360, 2) # На сколько реально прокрутился ротор
        return realrotation

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
        ''' Сканирование в одну сторону вдоль образующей ротора
            steps - количество точек сканирования, шт
            step  - расстояние между точками, имп (~2 имп/мкм)
        '''
        GeneratrixScanStepData = pd.Series()
        line = self.GetData()
        line[3] = round(line[3] - self.ZeroZ)
        line[5] = round(line[5] - self.ZeroPhi, 3)%360
        self.data.loc[len(self.data)] = line
        step *= -1 # Меняем знак, потому что ось двигателя и ось энкодера разнонаправлены
        gap = 0
        for s in range(steps):
            jump = step + 2*gap # gap - поправка с учётом точности предыдущего шага
            realstep = self.SimpleStepLinear(speed=100, step=jump) # Делаем шаг, вычисляем реальное перемещение.
            gap = int(step/2 - realstep + gap) # Разница между заданным и искомым перемещением с учётом предыдущей поправки
            GeneratrixScanStepData.loc[len(GeneratrixScanStepData)] = realstep
            line = self.GetData()
            line[3] = round(line[3] - self.ZeroZ)
            line[5] = round(line[5] - self.ZeroPhi, 3)%360
            self.data.loc[len(self.data)] = line
        print('Среднее значение шага по образующей:', GeneratrixScanStepData.mean())

    def Scan(self) -> None:
        ''' Сканирование по образующей вниз и вверх от заданных границ '''
        self.data = pd.DataFrame(columns=['Bx', 'By', 'Bz', 'Z', 'Zerr', 'PHI', 'PHIerr', 'T'])

        line = self.GetData()

        self.AbsPositioning()

        start = round(float(self.lEd_Pos_Z.text())*1000)+self.ZeroZ # Координаты точки начала измерений по Z, в мкм
        distance = round(float(self.lEd_Range_Z.text())*1000) # Дистанция прохода по образующей в мкм
        step = int(self.LinearStep*2000/1000) # Шаг вдоль образующей в импульсах двигателя (2000 имп/мм)
        
        steps = round(distance/self.LinearStep) # Количество шагов на образующую
        finish = start + self.LinearStep*steps # Уточнённое значение нижнего лимита по образующей

        # imp_in_degree = int(self.lEd_Rotation.text()) # Количество импульсов двигателя на угловой градус
        imp_in_degree = 100 # Количество импульсов двигателя на угловой градус
        # imp_in_mm = round(360*imp_in_degree/(3.14159*int(self.lEd_RotorDiam.text()))) # Количество импульсов двигателя на один мм поверхности вращения
        rotation = round(float(self.lEd_ScanStepAngle.text())*imp_in_degree)

        NumberOfRuns = round(float(self.lEd_Range_PHI.text())/(2*round(float(self.lEd_ScanStepAngle.text()), 2))) # Задаём количество шагов по окружности (пополам, потому что вверх-вниз)
        rotationgap = 0
        for n in range(NumberOfRuns):
            print('Проход номер', n)

            # Выборка люфта снизу
            self.SimpleStepLinear(speed=100, step=-4000)
            self.SimpleStepLinear(speed=100, step=3000)

            line = self.GetData()
            shift = start-line[3]

            # Парковка
            print('Парковка по нижней границе')
            count = 0
            while shift > 2 and count < 5:
                time.sleep(0.5)
                self.SimpleStepLinear(speed=100, step=int(shift*1.9))
                line = self.GetData()
                shift = start-line[3]
                count += 1
            
            # Движение вверх
            self.ScanGeneratrix(steps=steps, step=-step)

            # Шаг по окружности
            realrotation = self.PresizeStepRotor(speed=1, angle=(rotation+rotationgap))
            rotationgap = round(rotation - realrotation*100 + rotationgap)
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
            print('Парковка по верхней границе...')
            count = 0
            while shift > 2 and count < 5:
                time.sleep(0.5)
                self.SimpleStepLinear(speed=100, step=-1*int(shift*1.9))
                line = self.GetData()
                shift = line[3]-finish
                count += 1
            
            # Движение вниз
            self.ScanGeneratrix(steps=steps, step=step)

            # Шаг по окружности
            realrotation = self.PresizeStepRotor(speed=1, angle=(rotation+rotationgap))
            rotationgap = round(rotation - realrotation*100 + rotationgap)
            print('Поворот на угол - ', realrotation)
            
            time.sleep(1)
            
            line = self.GetData()
            # print('Нижняя координата', line[3])
            shift = start-line[3]

        filename = time.strftime("%Y-%m-%d_%H-%M")
        self.data.to_csv(f"data_{filename}.csv")
        message = "Съёмка завершена!"
        print(message)
        self.statusbar.showMessage(message)

    def ShowData(self) -> None:
        ''' Отражение данных в виджете '''
        line = self.GetData()
        text = ''.join(['B = ', str(line[:3]), '\nZ = ', str(line[3:5]), '\nPhi=', str(line[5:7]), '\nT = ', str(line[7:])])
        self.txtBrwser_ShowData.setText(text)

    def GetData(self) -> list:
        ''' Получение данных с дата-порта '''
        try:
            with (serial.Serial('COM8', baudrate=115200)) as self.serialData:
                # Read data from COM port
                command = 'R'
                # Send the command to the DataPort
                self.serialData.write(command.encode())
                line = str(self.serialData.readline().strip()).split(';') # Строка вида
            self.lbl_Data.setText(str(line))
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
        except serial.SerialException as se: print("Serial port error:", str(se))
        except Exception as e:               print("An error occurred:", str(e))

        return [0, 0, 0, 0, 0, 0, 0, 0]

    def ShowGraph(self):
        self.setWindowTitle('PyQt Graph')
        #self.data_f = pd.read_csv('full_360_0911.csv') #обработка внешнего дф
        self.filename = 'graph.html'
        src = [
            go.Scatter(
                x=self.data["PHI"],
                y=self.data["Z"],
                #text=df["title"],
                mode="markers",
                marker=dict(
                    colorscale="RdBu",
                    showscale=True,
                    color=self.data["Bx"],
                line=dict(color="white", width=0.01),
                ),
            )
        ]

        figure = go.Figure(
            data=src,
            layout=go.Layout(
                xaxis=dict(title="Угловая позиция"),
                yaxis=dict(title="Z"),
                title="Распределение Вx",
            ),
        )
        offline.plot(figure, filename = self.filename, auto_open = True)
        #self.view = QWebEngineView()
        #self.view.load(QUrl.fromLocalFile(self.filename))
        #self.setCentralWidget(self.view)

    def SaveConfig(self) -> None:
        print(self.tab1_dateEdit.text())
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

if __name__ == '__main__':
    from PyQt5.QtWebEngineWidgets import QWebEngineView # нашел рекомендацию этот импорт делать тут
    # app = QApplication(sys.argv)
    app = QApplication([])
    
    rotor = MainUI()
    rotor.show()
    
    # app.exec_()
    sys.exit(app.exec_())