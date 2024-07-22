from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.uic import loadUi
import sys, datetime

class MainUI(QMainWindow):
    def __init__(self):
        super(MainUI, self).__init__()
        loadUi("rotor_ui.ui", self)
        self.tab1_dateEdit.setDate(datetime.datetime.now())
        self.tab1_dateEdit.setCalendarPopup(True)
        self.tab1_timeEdit.setTime(datetime.datetime.now().time())


   
if __name__ == '__main__':
    app = QApplication(sys.argv)
    # app = QApplication([])
    harm = MainUI()
    harm.show()
    
    app.exec_()
    # sys.exit(app.exec_())