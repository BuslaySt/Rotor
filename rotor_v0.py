from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.uic import loadUi
import sys, datetime

class MainUI(QMainWindow):
    def __init__(self):
        super(MainUI, self).__init__()
        loadUi("rotor_ui.ui", self)
        # Окно инициализации
        self.tab1_dateEdit.setDate(datetime.datetime.now())
        self.tab1_dateEdit.setCalendarPopup(True)
        self.tab1_timeEdit.setTime(datetime.datetime.now().time())
        # Окно настроек
        self.tab2_cBox_ScanStepGeneratrix.addItems(['0,5 мм', '1 мм', '2 мм'])
        self.tab2_cBox_ScanStepGeneratrix.setCurrentIndex(1)
        self.tab2_cBox_ScanStepGeneratrix.currentIndexChanged.connect(self.SetupScanStepGeneratrix)

    def SetupScanStepGeneratrix(self, index: int) -> None:
        match index:
            case 0:
                pass
            case 1:
                pass
            case 2:
                pass
   
if __name__ == '__main__':
    # app = QApplication(sys.argv)
    app = QApplication([])
    
    rotor = MainUI()
    rotor.show()
    
    # app.exec_()
    sys.exit(app.exec_())