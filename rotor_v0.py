from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.uic import loadUi
import sys, datetime, time
import minimalmodbus, serial
from icecream import ic

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

        # Окно точного шагания
        self.cBox_ScanStepGeneratrix.addItems(['0,5 мм', '1 мм', '2 мм'])
        self.cBox_ScanStepGeneratrix.setCurrentIndex(1)
        self.cBox_ScanStepGeneratrix.currentIndexChanged.connect(self.SetupScanStepGeneratrix)
        self.pBtn_Position.clicked.connect(self.LinearAbsMotion)
        self.tab5_pBtn1_Turn.clicked.connect(self.SimpleStepLinear)
        self.tab5_pBtn2_Step.clicked.connect(self.PreciseStepLinear)
        self.tab5_pBtn3_Stop.clicked.connect(self.StopRotor)
        # self.tab5_pBtn5_Scan.clicked.connect(self.ScanGeneratrix)
        self.pBtn_ShowData.clicked.connect(self.ShowData)

    def SetupScanStepGeneratrix(self, index: int) -> None:
        match index:
            case 0:
                self.LinearStep = 500
            case 1:
                self.LinearStep = 1000
            case 2:
                self.LinearStep = 2000

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

    def SimpleStepLinear(self, speed=100, step=2050, precision=10) -> None:
        Z = Z0 = self.GetData()[3] # Запоминаем начальную позицию
        try:
            move = round((step-abs(Z-Z0)*2)*2/3)
            while (step-abs(Z-Z0)*2) > precision:
                ic(move)
                # Формирование массива параметров для команды:
                # 0x0041 - 65 - режим однократного увеличения позиции (шаг), записывается по адресу 0x6200
                # 0x0000 - верхние два байта кол-ва оборотов (=0 обычно), записывается по адресу 0x6201
                # 0x0000 - нижние два байта кол-ва оборотов  (=шаг), записывается по адресу 0x6202
                # 0x0000 - значение скорости вращения (об/мин), записывается по адресу 0x6203
                # 0x0064 - значение времени ускорения (100 мс), записывается по адресу 0x6204
                # 0x03E8 - значение времени торможения (1000 мс), записывается по адресу 0x6205
                # 0x0000 - задержка перед началом движения (0 мс), записывается по адресу 0x6206
                # 0x0010 - значение триггера для начала движения, записывается по адресу 0x6207
                self.instrumentLinear.write_registers(0x6200, [0x0041, 0, move, speed, 0x0064, 0x0064, 0x0000, 0x0010])
                time.sleep(1)
                line = self.GetData()
                Z = line[3]
                ic(Z)
                move = round((step-abs(Z-Z0)*2)*2/3)
            line = self.GetData()
            ic(line[3]-Z0)

        except (IOError, AttributeError, ValueError):
            message = "Команда не прошла"
            print(message)

    def PreciseStepRotor(self) -> None:
        speed = 1
        step = 91  # 1 градус
        precision = 9 # Точность - 0.1 градуса
        # Запоминаем начальную позицию
        line = self.GetData()
        PHI = PHI0 = line[5]
        # ic('Start', PHI)
        try:
            move = round((step-abs(PHI-PHI0)*100)*2/3)
            # instrument.write_registers(0x0007, [dir]) # Выбор направления движения
            while (step-abs(PHI-PHI0)*100) > precision:
                ic(move)
                # Формирование массива параметров для команды:
                # 0x0041 - 65 - режим однократного увеличения позиции (шаг), записывается по адресу 0x6200
                # 0x0000 - верхние два байта кол-ва оборотов (=0 обычно), записывается по адресу 0x6201
                # 0x0000 - нижние два байта кол-ва оборотов  (=шаг), записывается по адресу 0x6202
                # 0x0000 - значение скорости вращения (об/мин), записывается по адресу 0x6203
                # 0x0064 - значение времени ускорения (100 мс), записывается по адресу 0x6204
                # 0x03E8 - значение времени торможения (1000 мс), записывается по адресу 0x6205
                # 0x0000 - задержка перед началом движения (0 мс), записывается по адресу 0x6206
                # 0x0010 - значение триггера для начала движения, записывается по адресу 0x6207
                self.instrumentRotor.write_registers(0x6200, [0x0041, 0, move, speed, 0x0064,  0x0064, 0x0000, 0x0010])
                time.sleep(0.2)
                line = self.GetData()
                PHI = line[5]
                # ic('Finish', PHI)
                move = round((step-abs(PHI-PHI0)*100)*2/3)
            line = self.GetData()
            # ic(line[5]-PHI0)
        except (IOError, AttributeError, ValueError):
            message = "Команда не прошла"
            print(message)

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

    def ScanGeneratrixUp(self) -> None:
        finish = self.UpperLimit
        start = self.LowerLimit
        distance = abs(finish-start)
        step = self.LinearStep
        steps = distance/step

    def ShowData(self) -> None:
        self.txtBrwser_ShowData.setText(str(self.GetData()))

    def GetData(self) -> list:
        try:
            with (serial.Serial('COM8', baudrate=115200)) as self.serialData:
                # Read data from COM port
                command = 'R'
                # Send the command to the DataPort
                self.serialData.write(command.encode())
                line = str(self.serialData.readline().strip()) # Строка вида
            self.lbl_Data.setText(line)
            Bx = float(line.split(';')[0][5:-3].replace(',','.'))
            By = float(line.split(';')[1][4:-3].replace(',','.'))
            Bz = float(line.split(';')[2][5:-3].replace(',','.'))
            Z = int(line.split(';')[3][3:-3].replace(',','.'))
            try:    Zerr = int(line.split(';')[4][6:].replace(',','.'))
            except: Zerr = line.split(';')[4][6:].replace(',','.')
            PHI = float(line.split(';')[5][5:-4].replace(',','.'))
            try:    PHIErr = float(line.split(';')[6][8:-4].replace(',','.'))
            except: PHIErr = line.split(';')[6][8:].replace(',','.')
            T = float(line.split(';')[7][3:-7].replace(',','.'))

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