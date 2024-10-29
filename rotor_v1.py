from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.uic import loadUi
import sys, datetime, time
import minimalmodbus, serial
from icecream import ic
import pandas as pd

class MainUI(QMainWindow):
    def __init__(self):
        super(MainUI, self).__init__()
        loadUi("rotor_ui.ui", self)

        # Окно инициализации
        self.tab1_dateEdit.setDate(datetime.datetime.now())
        self.tab1_dateEdit.setCalendarPopup(True)
        self.tab1_timeEdit.setTime(datetime.datetime.now().time())
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

        self.pBtn_UpperLimit.clicked.connect(self.SetUpperLimit)
        self.pBtn_LowerLimit.clicked.connect(self.SetLowerLimit)
        self.pBtn_Center.clicked.connect(self.SetCenterZero)

        # Окно точного шагания
        self.cBox_ScanStepGeneratrix.addItems(['0,5 мм', '1 мм', '2 мм','4 мм'])
        self.cBox_ScanStepGeneratrix.setCurrentIndex(1)
        self.LinearStep = 1000 # 1mm default
        self.cBox_ScanStepGeneratrix.currentIndexChanged.connect(self.SetupScanStepGeneratrix)
        self.pBtn_Position.clicked.connect(self.LinearAbsMotion)
        self.tab3_pBtn1_Rotate.clicked.connect(self.Rotate)
        self.tab3_pBtn2_Step.clicked.connect(self.Step)
        self.tab3_pBtn3_Stop.clicked.connect(self.StopRotor)
        self.tab3_pBtn5_Scan.clicked.connect(self.Scan)
        self.pBtn_ShowData.clicked.connect(self.ShowData)

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
            speed = 65535
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
            speed = 200
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
            self.instrumentLinear.write_registers(0x6200, [0x0002, 0x0000, 0x0000, speed, 0x03E8, 0x03E8, 0x0000, 0x0010])
        except (IOError, AttributeError, ValueError):
            message = "Команда для движения не прошла"
            print(message)
            self.statusbar.showMessage(message)

    def LinearMotionUp(self) -> None:
        try:
            speed = 65535-int(self.lEd_LinearSpeed.text())
        except ValueError:
            speed = 65535-200
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
            self.instrumentLinear.write_registers(0x6200, [0x0002, 0x0000, 0x0000, speed, 0x03E8, 0x03E8, 0x0000, 0x0010])
        except (IOError, AttributeError, ValueError):
            message = "Команда для движения не прошла"
            print(message)
            self.statusbar.showMessage(message)

    def LinearAbsMotion(self) -> None:
        coord1, coord2 = divmod(int(self.lEd_Pos.text()), 0x10000)
        ic(hex(coord1), hex(coord2))
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

    def SetCenterZero(self) -> None:
        line = self.GetData()
        self.ZeroZ = int(line[3])
        self.ZeroPhi = float(line[5])
        message = "".join(["Установлен нулевой отсчёт - ", str(self.ZeroZ), str(self.ZeroPhi)])
        print(message)
        self.statusbar.showMessage(message)

    def Step(self):
        step = round(int(self.lEd_Step.text())*2010/1000)
        speed = int(self.lEd_LinearSpeed.text()) 
        self.SimpleStepLinear(speed=speed, step=step)

    def SimpleStepLinear(self, speed=50, step=2010) -> int:
        ''' Простой шаг по образующей на заданное расстояние '''
        sleepStep = abs(step)/speed/100 # Время на паузу в сек, чтобы мотор успел прокрутиться
        if sleepStep < 0.5: sleepStep = 0.5
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
        # 0x03E8 - значение времени ускорения (1000 мс), записывается по адресу 0x6204
        # 0x03E8 - значение времени торможения (1000 мс), записывается по адресу 0x6205
        # 0x000A - задержка перед началом движения (10 мс), записывается по адресу 0x6206
        # 0x0010 - значение триггера для начала движения, записывается по адресу 0x6207
        try:
            self.instrumentLinear.write_registers(0x6200, [0x0041, step1, step2, speed, 0x03E8, 0x03E8, 0x0000, 0x0010])
            time.sleep(sleepStep) # Пауза, чтобы мотор успел прокрутиться
            realstep = self.GetData()[3]-Z0
            # ic("Шаг:", realstep)

        except (IOError, AttributeError, ValueError):
            message = "Команда на линейный шаг не прошла"
            print(message)
            realstep = 0

        return realstep

    def Rotate(self):
        ''' Полный оборот вокруг оси '''
        rotationData = pd.Series()
        rotation = int(self.lEd_Rotation.text())
        line = self.GetData()
        start = line[5]
        ic('Старт', start)
        for _ in range(360):
            realangle = self.SimpleStepRotor(speed=1, angle=rotation)
            rotationData.loc[len(rotationData)] = realangle
        line = self.GetData()
        finish = line[5]
        ic('Финиш:', finish)
        ic('Оборот:', finish-start)
        rotationData = rotationData.loc[(rotationData>-10)&(rotationData<10)]
        print(rotationData.describe())

    def SimpleStepRotor(self, speed=1, angle=67) -> int:
        ''' Простой поворот на заданный угол '''
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
            time.sleep(1) # Пауза на устаканивание
            realrotation = self.GetData()[5]-PHI0
            print("Угол:", realrotation)

        except (IOError, AttributeError, ValueError):
            message = "Команда на поворот не прошла"
            print(message)
            realrotation = 0

        return realrotation

    def StopRotor(self) -> None:
        try:
            self.instrumentRotor.write_registers(0x6002, [0x0040])
            print('Стоп!')
        except (IOError, AttributeError, ValueError):
            message = "Команда не прошла"
            print(message)

    def StopLinear(self) -> None:
        try:
            self.instrumentLinear.write_registers(0x6002, [0x0040])
            print('Стоп!')
        except (IOError, AttributeError, ValueError):
            message = "Команда не прошла"
            print(message)

    def ScanGeneratrix(self, steps: int, step: int) -> None:
        GeneratrixScanStepData = pd.Series()
        for s in range(steps):
            realstep = abs(self.SimpleStepLinear(speed=100, step=-1*step))
            GeneratrixScanStepData.loc[len(GeneratrixScanStepData)] = realstep
            line = self.GetData()
            self.data.loc[len(self.data)] = line
        ic('Среднее значение шага по образующей:', GeneratrixScanStepData.mean())

    def Scan(self) -> None:
        ''' Сканирование по образующей вниз и вверх от заданных границ '''
        self.data = pd.DataFrame(columns=['Bx', 'By', 'Bz', 'Z', 'Zerr', 'PHI', 'PHIerr', 'T'])

        line = self.GetData()
        start = int(line[3])
        distance = abs(start-self.LowerLimit) # Дистанция прохода по образующей в мкм
        ic('Дистанция прохода по образующей в мкм', distance)
        step = int(self.LinearStep*2010/1000) # Шаг вдоль образующей в импульсах двигателя
        ic('Шаг вдоль образующей в импульсах двигателя', step)
        steps = round(distance/self.LinearStep) # Количество шагов на образующую
        ic('Количество шагов на образующую', steps)
        finish = start - self.LinearStep*steps # Уточнённое значение нижнего лимита по образующей
        ic('Уточнённое значение нижнего лимита по образующей', finish)
        ic('Разница между лимитом и реальной дистанцией', finish-self.LowerLimit)
        imp_in_degree = 100 # Количество импульсов двигателя на угловой градус
        imp_in_mm = round(360*imp_in_degree/(3.14159*int(self.lEd_RotorDiam.text()))) # Количество импульсов двигателя на один мм поверхности вращения
        rotation = int(self.lEd_ScanStepAngle.text())*imp_in_degree

        for n in range(180*3):
            print('Проход номер', n)
            # Выборка люфта сверху
            self.SimpleStepLinear(speed=200, step=4*2010)
            self.SimpleStepLinear(speed=200, step=-3*2010)

            line = self.GetData()
            shift = line[3]-start
            print('Сдвиг выборки люфта:', shift)

            # Парковка
            print('Парковка по верхней границе...')
            count = 0
            while shift > 5 and count < 10:
                time.sleep(0.5)
                self.SimpleStepLinear(speed=100, step=-1*shift)
                line = self.GetData()
                shift = line[3]-start
                count += 1
            print('Сдвиг после парковки:', shift)
            
            # Движение вниз
            self.ScanGeneratrix(steps=steps, step=step)

            time.sleep(1)
            line = self.GetData()
            ic(line[3])
            ic('Зазор снизу:', finish-line[3])
            
            # Шаг по окружности
            self.SimpleStepRotor(speed=1, angle=rotation)

            line = self.GetData()
            shift = finish - line[3]
            print('Сдвиг после скана:', shift)

            # Выборка люфта снизу
            self.SimpleStepLinear(speed=200, step=-4*2010)
            self.SimpleStepLinear(speed=200, step=3*2010)

            line = self.GetData()
            shift = finish-line[3]
            print('Сдвиг выборки люфта:', shift)

            # Парковка
            print('Парковка по нижней границе')
            count = 0
            while shift > 5 and count < 10:
                time.sleep(0.5)
                self.SimpleStepLinear(speed=100, step=shift)
                line = self.GetData()
                shift = finish-line[3]
                count += 1
            print('Сдвиг:', shift)
            
            # Движение вверх
            self.ScanGeneratrix(steps=steps, step=-1*step)

            # Шаг по окружности
            self.SimpleStepRotor(speed=1, angle=rotation)

            time.sleep(1)
            line = self.GetData()
            ic(line[3])
            ic('Зазор сверху:', line[3]-start)
            shift = line[3]-start

        filename = time.strftime("%Y-%m-%d_%H-%M")
        self.data.to_csv(f"data_{filename}.csv")

    def ShowData(self) -> None:
        line = self.GetData()
        text = ''.join(['B = ', str(line[:3]), '\nZ = ', str(line[3:5]), '\nPhi=', str(line[5:7]), '\nT = ', str(line[7:])])
        self.txtBrwser_ShowData.setText(text)

    def GetData(self) -> list:
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

if __name__ == '__main__':
    # app = QApplication(sys.argv)
    app = QApplication([])
    
    rotor = MainUI()
    rotor.show()
    
    # app.exec_()
    sys.exit(app.exec_())