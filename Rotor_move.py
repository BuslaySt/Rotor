from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.uic import loadUi
import sys, datetime
import serial.tools.list_ports
import minimalmodbus
from icecream import ic

class MainUI(QMainWindow):
    def __init__(self):
        super(MainUI, self).__init__()
        loadUi("Rotor_move.ui", self)

        self.GetData()

        try:
            # Modbus-адрес драйвера по умолчанию - 1
            self.instrumentRotor = minimalmodbus.Instrument('COM9', 1) #COM9, 1 - вращение, 2 - линейка
            # Настройка порта: скорость - 38400 бод/с, четность - нет, кол-во стоп-бит - 2.
            self.instrumentRotor.mode = minimalmodbus.MODE_RTU
            print(self.instrumentRotor.serial.port)
            self.instrumentRotor.serial.baudrate = 38400
            self.instrumentRotor.serial.parity = minimalmodbus.serial.PARITY_NONE
            self.instrumentRotor.serial.stopbits = 2
            # self.instrument.serial.databits = 8
            self.instrumentRotor.serial.timeout  = 0.05          # seconds
            # self.instrument.close_port_after_each_call = True
            print(self.instrumentRotor)
        except (IOError, AttributeError, ValueError): # minimalmodbus.serial.serialutil.SerialException:
            message = "Привод вращения не виден"
            print(message)

        try:
            # Команда включения серво; 0x0405 - адрес параметра; 0x83 - значение параметра
            self.instrumentRotor.write_registers(0x00F, [1])
        except (IOError, AttributeError, ValueError): # minimalmodbus.serial.serialutil.SerialException:
            message = "Запуск привода вращения не удался"
            print(message)


        self.Rtr_pBtn1_Forward.pressed.connect(self.ForwardMotion)
        self.Rtr_pBtn1_Forward.released.connect(self.Stop)
        self.Rtr_pBtn2_Backward.pressed.connect(self.BackwardMotion)
        self.Rtr_pBtn2_Backward.released.connect(self.Stop)

        self.Rtr_pBtn3_Step_Fwd.pressed.connect(self.StepFwd)
        self.Rtr_pBtn4_Step_Bkwd.pressed.connect(self.StepBkwd)
        
        self.Rtr_pBtn5_Stop.clicked.connect(self.Stop)
        
        self.Rtr_pBtn6_Data.clicked.connect(self.GetData)
        
    def ForwardMotion(self):
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
            print('Поехали')
            speed = int(self.Rtr_lEd1_Speed.text())
            self.instrumentRotor.write_registers(0x0007, [0x0000])
            self.instrumentRotor.write_registers(0x6200, [0x0002, 0x0000, 0x0000, speed, 0x03E8, 0x03E8, 0x0000, 0x0010])
        except (IOError, AttributeError, ValueError):
            message = "Команда не прошла"
            print(message)

    def BackwardMotion(self):
        try:
            print('Поехали')
            speed = 0xFFFF-int(self.Rtr_lEd1_Speed.text())+1
            speed = int(self.Rtr_lEd1_Speed.text())
            self.instrumentRotor.write_registers(0x0007, [0x0001])
            self.instrumentRotor.write_registers(0x6200, [0x0002, 0x0000, 0x0000, speed, 0x0064, 0x0064, 0x0000, 0x0010])
        except (IOError, AttributeError, ValueError):
            message = "Команда не прошла"
            print(message)
 
    def StepFwd(self):
        # Формирование массива параметров для команды:
        # 0x0041 - 65 - режим однократного увеличения позиции (шаг), записывается по адресу 0x6200
        # 0x0000 - верхние два байта кол-ва оборотов (=0 обычно), записывается по адресу 0x6201
        # 0x0000 - нижние два байта кол-ва оборотов  (=шаг), записывается по адресу 0x6202
        # 0x0005 - значение скорости вращения (5 об/мин), записывается по адресу 0x6203
        # 0x03E8 - значение времени ускорения (1000 мс), записывается по адресу 0x6204
        # 0x03E8 - значение времени торможения (1000 мс), записывается по адресу 0x6205
        # 0x0000 - задержка перед началом движения (0 мс), записывается по адресу 0x6206
        # 0x0010 - значение триггера для начала движения, записывается по адресу 0x6207
        try:
            print('Шаг вперёд')
            step = int(self.Rtr_lEd2_Step.text())
            self.instrumentRotor.write_registers(0x0007, [0x0000])
            self.instrumentRotor.write_registers(0x6200, [0x0041, 0, step, 0x0005, 0x03E8, 0x03E8, 0x0000, 0x0010])
        except (IOError, AttributeError, ValueError):
            message = "Команда не прошла"
            print(message)
        self.GetData()

    def StepBkwd(self):
        try:
            print('Шаг назад')
            step = int(self.Rtr_lEd2_Step.text())
            self.instrumentRotor.write_registers(0x0007, [0x0001])
            self.instrumentRotor.write_registers(0x6200, [0x0041, 0, step, 0x0005, 0x03E8, 0x03E8, 0x0000, 0x0010])
        except (IOError, AttributeError, ValueError):
            message = "Команда не прошла"
            print(message)
        self.GetData()

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
   
    def Stop(self):
        try:
            self.instrumentRotor.write_registers(0x6002, [0x0040])
            print('Стоп!')
        except (IOError, AttributeError, ValueError):
            message = "Команда не прошла"
            print(message)

    def GetData(self):
        # try:
        # Find and open the COM port
        ports = serial.tools.list_ports.comports()
        for p in ports:
            print(p.device)
            port = p.device
        # port = next((p.device for p in ports), None) # COM8 - датчики
        print(port)
        if port is None:
            raise ValueError("No COM port found.")

        port = 'COM8'
        ser = serial.Serial(port, baudrate=115200)

        # Read data from COM port
        command = 'R'

        # Send the command to the ArduinoR
        ser.write(command.encode())
        line = ser.readline().strip()
        
        # Запись данных в форму
        Z0 = int(self.Rtr_lbl07_ZData.text().split()[0])
        Phi0 = float(self.Rtr_lbl10_PhiData.text().split()[0].replace('\\xb0','').replace(',','.'))

        self.Rtr_lbl03_Data.setText(str(line))
        Bx, By, Bz, Z, Zerr, Phi, PhiErr, T = str(line).split(';')
        self.Rtr_lbl04_BxData.setText(Bx.split('=')[1])
        self.Rtr_lbl05_ByData.setText(By.split('=')[1])
        self.Rtr_lbl06_BzData.setText(Bz.split('=')[1])
        self.Rtr_lbl07_ZData.setText(Z.split('=')[1])
        self.Rtr_lbl08_ZerrData.setText(Zerr.split('=')[1])
        self.Rtr_lbl09_ZstepData.setText(str(int(Z.split('=')[1].split()[0])-Z0))
        self.Rtr_lbl10_PhiData.setText(Phi.split('=')[1])
        self.Rtr_lbl11_PhiErrData.setText(PhiErr.split('=')[1])
        self.Rtr_lbl12_PhiStepData.setText(str(float(Phi.split('=')[1].split()[0].replace('\\xb0','').replace(',','.'))-Phi0))
        self.Rtr_lbl13_TData.setText(T.split('=')[1])


            
        ser.close()
        print("Данные получены.")

        # except ValueError as ve:
        #     print("Error:", str(ve))

        # except serial.SerialException as se:
        #     print("Serial port error:", str(se))

        # except Exception as e:
        #     print("An error occurred:", str(e))

        # finally:
        #     print('Сессия закрыта')

if __name__ == '__main__':
    # app = QApplication(sys.argv)
    app = QApplication([])
    
    rotor = MainUI()
    rotor.show()
    
    # app.exec_()
    sys.exit(app.exec_())