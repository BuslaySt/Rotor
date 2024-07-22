from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.uic import loadUi
import sys

class MainUI(QMainWindow):
    def __init__(self):
        super(MainUI, self).__init__()
        loadUi("rotor_ui.ui", self)

   
if __name__ == '__main__':
    app = QApplication(sys.argv)
    # app = QApplication([])
    harm = MainUI()
    harm.show()
    
    app.exec_()
    # sys.exit(app.exec_())