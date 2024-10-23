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

        self.data = pd.DataFrame(columns=['Bx', 'By', 'Bz', 'Z', 'Zerr', 'PHI', 'PHIerr', 'T', 'Zstep'])

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

        # Окно точного шагания
        self.cBox_ScanStepGeneratrix.addItems(['0,5 мм', '1 мм', '2 мм'])
        self.cBox_ScanStepGeneratrix.setCurrentIndex(1)
        self.LinearStep = 1000 # 1mm default
        self.cBox_ScanStepGeneratrix.currentIndexChanged.connect(self.SetupScanStepGeneratrix)
        self.pBtn_Position.clicked.connect(self.LinearAbsMotion)
        self.tab3_pBtn1_Rotate.clicked.connect(self.Rotate)
        self.tab3_pBtn2_Step.clicked.connect(self.Step)
        self.tab3_pBtn3_Stop.clicked.connect(self.StopRotor)
        self.tab3_pBtn5_Scan.clicked.connect(self.ScanGeneratrix)
        self.pBtn_ShowData.clicked.connect(self.ShowData)

    def SetupScanStepGeneratrix(self, index: int) -> None:
        match index:
            case 0:
                self.LinearStep = 500
            case 1:
                self.LinearStep = 1000
            case 2:
                self.LinearStep = 2000
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

    def Step(self):
        step = round(int(self.lEd_Step.text())*2015/1000)
        self.SimpleStepLinear(speed=100, step=step)

    def SimpleStepLinear(self, speed=100, step=2015) -> int:
        Z0 = self.GetData()[3] # Запоминаем начальную позицию
        if step<0:
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
            time.sleep(0.5)
            realstep = self.GetData()[3]-Z0
            ic("Шаг:", realstep)

        except (IOError, AttributeError, ValueError):
            message = "Команда на линейный шаг не прошла"
            print(message)
            realstep = 0

        return realstep

    def Rotate(self):
        rotationData = pd.Series()
        rotation = int(self.lEd_Rotation.text())
        line = self.GetData()
        start = line[5]
        ic('Старт', start)
        for _ in range(1):
            realangle = self.SimpleStepRotor(speed=1, angle=rotation)
            rotationData.loc[len(rotationData)] = realangle
        line = self.GetData()
        finish = line[5]
        ic('Финиш:', finish)
        ic('Оборот:', finish-start)
        rotationData = rotationData.loc[(rotationData>-10)&(rotationData<10)]
        print(rotationData.describe())

    def SimpleStepRotor(self, speed=1, angle=67) -> int:
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
            time.sleep(0.5)
            realrotation = self.GetData()[5]-PHI0
            print("Угол:", realrotation)

        except (IOError, AttributeError, ValueError):
            message = "Команда на линейный шаг не прошла"
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

    def ScanAround(self) -> None:
        line = self.GetData()
        ic('Start', line[5])
        for r in range(360):
            self.PreciseStepRotor()
            line = self.GetData()
            ic('Go', line[5])
            time.sleep(0.2)
        line = self.GetData()
        ic('Finish', line[5])

    def ScanGeneratrix(self) -> None:
        # Сканирование по образующей вниз и вверх от заданных границ
        line = self.GetData()

        start = int(line[3])
        finish = self.LowerLimit
        distance = abs(finish-start)
        step = int(self.LinearStep*2015/1000)
        steps = int(distance/self.LinearStep)

        # Движение вниз
        for s in range(steps):
            realstep = abs(self.SimpleStepLinear(speed=100, step=step))
            line = self.GetData()
            line.append(realstep)
            self.data.loc[len(self.data)] = line

        line = self.GetData()
        ic(finish-line[3])

        # Движение вверх
        for s in range(steps):
            realstep = abs(self.SimpleStepLinear(speed=100, step=0xFFFFFFFF-step))
            line = self.GetData()
            line.append(realstep)
            self.data.loc[len(self.data)] = line

        line = self.GetData()
        ic(start-line[3])

        # print(self.data)
        # print(self.data.describe())



    def ShowData(self) -> None:
        self.txtBrwser_ShowData.setText(str(self.GetData()))

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
            Bz = float(line[2][5:-3].replace(',','.'))
            Z = int(line[3][3:-3].replace(',','.'))
            try:    Zerr = int(line[4][6:-3].replace(',','.'))
            except: Zerr = line[4][6:]
            PHI = float(line[5][5:-4].replace(',','.'))
            try:    PHIErr = float(line[6][8:-4].replace(',','.'))
            except: PHIErr = line[6][8:]
            T = float(line[7][3:-7].replace(',','.'))

            return [Bx, By, Bz, Z, Zerr, PHI, PHIErr, T]

        except ValueError as ve:             print("Error:", str(ve))
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