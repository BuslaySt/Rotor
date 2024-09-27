from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.uic import loadUi
import sys, datetime
import serial.tools.list_ports
import minimalmodbus
from icecream import ic
import time

class MainUI(QMainWindow):
    def __init__(self):
        super(MainUI, self).__init__()
        loadUi("Rotor_move.ui", self)

        self.InitRotMotor()
        self.InitLinearMotor()
        self.Zcoor = self.GetData()[3]
        self.PHIcoor = self.GetData()[5]


        ''' Привязка кнопок '''
        # Движение ротора
        self.Rtr_pBtn1_Forward.pressed.connect(self.StartMotion)
        self.Rtr_pBtn1_Forward.released.connect(self.Stop)
        self.Rtr_pBtn2_Backward.pressed.connect(self.StartMotion)
        self.Rtr_pBtn2_Backward.released.connect(self.Stop)

        self.Rtr_pBtn3_Step_Fwd.clicked.connect(self.StartStep)
        self.Rtr_pBtn4_Step_Bkwd.clicked.connect(self.StartStep)
        
        self.Rtr_pBtn6_Stop.clicked.connect(self.Stop)
        
        # Движение линейки
        self.Line_pBtn1_Forward.pressed.connect(self.StartMotion)
        self.Line_pBtn1_Forward.released.connect(self.Stop)
        self.Line_pBtn2_Backward.pressed.connect(self.StartMotion)
        self.Line_pBtn2_Backward.released.connect(self.Stop)

        self.Line_pBtn3_Step_Fwd.clicked.connect(self.StartStep)
        self.Line_pBtn4_Step_Bkwd.clicked.connect(self.StartStep)
        
        self.Line_pBtn5_Home.clicked.connect(self.Homing)
        self.Line_pBtn6_Stop.clicked.connect(self.Stop)
        
        # Получение данных с датчиков
        self.Data_pBtn_ShowData.clicked.connect(self.ShowData)

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
            # print('Вращение подключено')
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
        except (IOError, AttributeError, ValueError): # minimalmodbus.serial.serialutil.SerialException:
            message = "Запуск привода линейки не удался"
            print(message)

    def StartMotion(self) -> None:
        if self.sender() == self.Line_pBtn1_Forward:
            instrument = self.instrumentLinear
            speed = int(self.Line_lEd1_Speed.text())
            direction = "F"
            self.Motion(instrument, speed, direction)
        elif self.sender() == self.Line_pBtn2_Backward:
            instrument = self.instrumentLinear
            speed = int(self.Line_lEd1_Speed.text())
            direction = "B"
        
        if self.sender() == self.Rtr_pBtn1_Forward:
            instrument = self.instrumentRotor
            speed = int(self.Rtr_lEd1_Speed.text())
            direction = "F"
            self.Motion(instrument, speed, direction)
        elif self.sender() == self.Rtr_pBtn2_Backward:
            instrument = self.instrumentRotor
            speed = int(self.Rtr_lEd1_Speed.text())
            direction = "B"
        
        self.Motion(instrument, speed, direction)

    def StartStep(self) -> None:
        if self.sender() == self.Line_pBtn3_Step_Fwd:
            instrument = self.instrumentLine
            speed = int(Line_lEd1_Speed.text())
            self.Motion(self.instrumentLine, int(Line_lEd1_Speed.text()), 'F')
        elif self.sender() == self.Line_pBtn2_Backward:
            instrument = self.instrumentLinear
            speed = int(self.Line_lEd1_Speed.text())
            self.Motion(self.instrumentLine, int(Line_lEd1_Speed.text()), 'W')

    def Motion(self, instrument, speed, direction) -> None:
        if direction == "F":
            dir = 0x0000
        elif direction == "B":
            dir = 0x0001
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
            instrument.write_registers(0x0007, [dir]) # Ось движения прямо
            instrument.write_registers(0x6200, [0x0002, 0x0000, 0x0000, speed, 0x03E8, 0x03E8, 0x0000, 0x0010])
        except (IOError, AttributeError, ValueError):
            message = "Команда для движения не прошла"
            print(message)

    def StepSimple(self, instrument, speed, step, direction) -> None:
        # if self.sender() == self.Rtr_pBtn4_Step_Bkwd:
        #     self.instrument = self.instrumentRotor
        #     speed = int(self.Rtr_lEd1_Speed.text())
        #     step = int(self.Rtr_lEd3_Step.text())
        # elif self.sender() == self.Line_pBtn4_Step_Bkwd:
        #     self.instrument = self.instrumentLinear
        #     speed = int(self.Line_lEd1_Speed.text())
        #     step = int(self.Line_lEd2_Step.text())
        if direction == "F":
            dir = 0x0000
        elif direction == "B":
            dir = 0x0001
        try:
            print('Шаг')
            instrument.write_registers(0x0007, [dir])
            instrument.write_registers(0x6200, [0x0041, 0, step, speed, 0x03E8, 0x03E8, 0x0000, 0x0010])
        except (IOError, AttributeError, ValueError):
            message = "Команда не прошла"
            print(message)
        # time.sleep(1)

    def Step(self, instrument, speed, step, direction, precision) -> None:
        # self.GetData()
        # Z0 = int(self.Data_lbl08_ZData.text().split()[0])
        # Phi0 = float(self.Data_lbl14_PhiData.text().split()[0].replace('\u00B0','').replace('\\xb0','').replace(',','.'))

        # if self.sender() == self.Rtr_pBtn3_Step_Fwd:
        #     self.instrument = self.instrumentRotor
        #     speed = int(self.Rtr_lEd1_Speed.text())
        #     step = int(self.Rtr_lEd3_Step.text())
        # elif self.sender() == self.Line_pBtn3_Step_Fwd:
        #     self.instrument = self.instrumentLinear
        #     speed = int(self.Line_lEd1_Speed.text())
        #     step = int(self.Line_lEd2_Step.text())

        # Формирование массива параметров для команды:
        # 0x0041 - 65 - режим однократного увеличения позиции (шаг), записывается по адресу 0x6200
        # 0x0000 - верхние два байта кол-ва оборотов (=0 обычно), записывается по адресу 0x6201
        # 0x0000 - нижние два байта кол-ва оборотов  (=шаг), записывается по адресу 0x6202
        # 0x0000 - значение скорости вращения (об/мин), записывается по адресу 0x6203
        # 0x03E8 - значение времени ускорения (1000 мс), записывается по адресу 0x6204
        # 0x03E8 - значение времени торможения (1000 мс), записывается по адресу 0x6205
        # 0x0000 - задержка перед началом движения (0 мс), записывается по адресу 0x6206
        # 0x0010 - значение триггера для начала движения, записывается по адресу 0x6207
        n = 1
        Z = Z0
        while not (step-(Z0-Z) < 3):
            try:
                print(f'{n}-й подход')
                self.instrument.write_registers(0x0007, [0x0000])
                move = int((step-(Z0-Z))*1.9)
                print('шаг -', move)
                self.instrument.write_registers(0x6200, [0x0041, 0, move, speed, 0x03E8, 0x03E8, 0x0000, 0x0010])
                n += 1
            except (IOError, AttributeError, ValueError):
                message = "Команда не прошла"
                print(message)
            time.sleep(2)
            self.GetData()
            time.sleep(2)
            Z = int(self.Data_lbl08_ZData.text().split()[0])
            print(step - (Z0 - Z))

    def StepPresize(self, instrument, speed, step, direction, precision) -> None:
        # Запоминаем начальную позицию
        line = self.GetData()
        Z = Z0 = line[3]
        Phi0 = line[5]
        if direction == "F":
            dir = 0x0000
        elif direction == "B":
            dir = 0x0001
        try:
            move = round(step*2/3)
            instrument.write_registers(0x0007, [dir])
            while ((ABS(Z-Z0)-step > precision) and (ABS(PHI-PHI0)-step > precision)):
                # Формирование массива параметров для команды:
                # 0x0041 - 65 - режим однократного увеличения позиции (шаг), записывается по адресу 0x6200
                # 0x0000 - верхние два байта кол-ва оборотов (=0 обычно), записывается по адресу 0x6201
                # 0x0000 - нижние два байта кол-ва оборотов  (=шаг), записывается по адресу 0x6202
                # 0x0000 - значение скорости вращения (об/мин), записывается по адресу 0x6203
                # 0x03E8 - значение времени ускорения (1000 мс), записывается по адресу 0x6204
                # 0x03E8 - значение времени торможения (1000 мс), записывается по адресу 0x6205
                # 0x0000 - задержка перед началом движения (0 мс), записывается по адресу 0x6206
                # 0x0010 - значение триггера для начала движения, записывается по адресу 0x6207
                instrument.write_registers(0x6200, [0x0041, 0, move, speed, 0x03E8, 0x03E8, 0x0000, 0x0010])
                move = round(move*2/3)
        except (IOError, AttributeError, ValueError):
            message = "Команда не прошла"
            print(message)

    def AbsMotion(self):
        try:
            print('Поехали')
            coord1, coord2 = divmod(int(self.lEd2_Coord.text()), 0x10000)
            self.instrumentRotor.write_registers(0x6200, [0x0001, coord1, coord2, 0x0258, 0x0064, 0x0064, 0x0000, 0x0010])
        except (IOError):
            message = "Команда не прошла"
            print(message)

    def Homing(self):
        try:
            print('Домой!')
            self.instrumentRotor.write_registers(0x600A, [0x0002, 0x0000, 0x0000, 0x0000, 0x0000, 0x0064, 0x001E, 0x0020])
        except (IOError, AttributeError, ValueError):
            message = "Команда не прошла"
            print(message)
   
    def Stop(self) -> None:
        if self.sender() in [self.Rtr_pBtn6_Stop, self.Rtr_pBtn1_Forward, self.Rtr_pBtn2_Backward]:
            instrument = self.instrumentRotor
        elif self.sender() in [self.Line_pBtn6_Stop, self.Line_pBtn1_Forward, self.Line_pBtn2_Backward]:
            instrument = self.instrumentLinear
        try:
            instrument.write_registers(0x6002, [0x0040])
            print('Стоп!')
        except (IOError, AttributeError, ValueError):
            message = "Команда не прошла"
            print(message)

    def ShowData(self) -> None:
        data = self.GetData()
        self.Data_txtBrowser.setText(str(data))
        self.Data_lbl02_BxData.setText(str(data[0])+" mT")
        self.Data_lbl04_ByData.setText(str(data[1])+" mT")
        self.Data_lbl06_BzData.setText(str(data[2])+" mT")
        self.Data_lbl08_ZData.setText(str(data[3])+" um")
        self.Data_lbl10_ZerrData.setText(str(data[4]))
        self.Data_lbl12_ZstepData.setText(str(data[3]-self.Zcoor))
        self.Data_lbl14_PhiData.setText(str(data[5])+"°")
        self.Data_lbl16_PhiErrData.setText(str(data[6]))
        self.Data_lbl18_PhiStepData.setText(str(data[5]-self.PHIcoor))
        self.Data_lbl20_TData.setText(str(data[7])+" °C")
        self.Zcoor = data[3]
        self.PHIcoor = data[5]

    def GetData(self) -> list:
        try:
            with (serial.Serial('COM8', baudrate=115200)) as self.serialData:

                # Read data from COM port
                command = 'R'

                # Send the command to the DataPort
                self.serialData.write(command.encode())
                line = str(self.serialData.readline().strip()) # Строка вида 

            # print(line)
            Bx = float(line.split(';')[0][5:-3].replace(',','.'))
            By = float(line.split(';')[1][4:-3].replace(',','.'))
            Bz = float(line.split(';')[2][5:-3].replace(',','.'))
            Z = float(line.split(';')[3][3:-3].replace(',','.'))
            try:    Zerr = float(line.split(';')[4][6:].replace(',','.'))
            except: Zerr = line.split(';')[4][6:].replace(',','.')
            PHI = float(line.split(';')[5][5:-4].replace(',','.'))
            try:    PHIErr = float(line.split(';')[6][8:].replace(',','.'))
            except: PHIErr = line.split(';')[6][8:].replace(',','.')
            T = float(line.split(';')[7][3:-7].replace(',','.'))

            # print([Bx, By, Bz, Z, Zerr, PHI, PHIErr, T])
            return [Bx, By, Bz, Z, Zerr, PHI, PHIErr, T]

        except ValueError as ve:             print("Error:", str(ve))
        except serial.SerialException as se: print("Serial port error:", str(se))
        except Exception as e:               print("An error occurred:", str(e))

if __name__ == '__main__':
    # app = QApplication(sys.argv)
    app = QApplication([])
    
    rotor = MainUI()
    rotor.show()
    
    # app.exec_()
    sys.exit(app.exec_())