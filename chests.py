import sys
import time

# pip install pyqt5
from PyQt5.QtGui import QPainter, QPen
from PyQt5.QtWidgets import QMainWindow, QApplication, QPushButton, QWidget, QVBoxLayout, QListWidget, QListWidgetItem
from PyQt5.QtCore import Qt

# pip install screeninfo
from screeninfo import get_monitors

# pip install pillow
from PIL import ImageGrab

# pip install pytesseract
try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'
except ModuleNotFoundError:
    pass

# pip install easyocr
import easyocr

# pip install numpy
import numpy

# pip install pyautogui
import pyautogui


class Chest:

    player = ''
    source = ''
    name = ''
    
    def __str__(self):
        return f'{self.player}: {self.source}'
    
    def __iter__(self):
        return iter((self.player, self.source, self.name))

    def valid(self):
        return len(self.name) > 0 and len(self.player) > 0 and len(self.source) > 0


class ChestException(Exception):
    pass


class ChestCounter:

    def __init__(self, log_callback):
        self.log_callback = log_callback

    def parse(self, text_lines):
        chests = []
        chest = Chest()
        for line in text_lines:
            if len(line) == 0:
                continue

            if 'PRBS' in line:
                pass # what's going on with this one?

            if len(chest.player) == 0 and  line.startswith('From'):
                s = line.split(' ')
                s.pop(0)
                chest.player = ' '.join(s).replace('.', '') # faulty dots are sometimes added by OCR 
            elif len(chest.source) == 0 and line.startswith('Source'):
                s = line.split(' ')
                s.pop(0)
                chest.source = ' '.join(s)
            else:
                chest.name = ' '.join([chest.name, line]).strip()

            if chest.valid():
                chests.append(chest)
                self.log_callback(str(chest))
                chest = Chest()

        return chests
    
    def export(self, chests):
        SEP = ';'
        EOL = '\n'

        self.players = []
        self.sources = ['']
        self.player_chests = {}
        for chest in chests:
            # sometimes OCR doesn't recognize lettering, so add some magic here
            real_player = chest.player
            has_player = False
            for p in self.players:
                if p.upper() == chest.player.upper():
                    real_player = p
                    has_player = True

            if not has_player:
                self.players.append(real_player)

            if not chest.source in self.sources:
                self.sources.append(chest.source)
            
            if not real_player in self.player_chests:
                self.player_chests[real_player] = []
            
            self.player_chests[real_player].append(chest)            

        with open("chests.csv", "w") as f:
            header = SEP.join(self.sources) + EOL
            f.write(header)

            for player in self.players:
                sources = [player]
                for source in self.sources:
                    if len(source) == 0:
                        continue
                    counter = 0
                    for chest in self.player_chests[player]:
                        if chest.source == source:
                            counter += 1
                    sources.append(str(counter))
                line = SEP.join(sources) + EOL
                f.write(line)    


class Dialog(QWidget):

    def __init__(self, ocr):
        super().__init__()
        self.ocr = ocr

        self.setGeometry(1500, 400, 300, 500)
        self.setWindowTitle("Chest counter")

        self.listWidget = QListWidget()
        
        button = QPushButton('Start', self)
        button.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        #button.setGeometry(80, 450, 150, 30)
        button.clicked.connect(self.ocr.start)

        layout = QVBoxLayout()
        layout.addWidget(self.listWidget)
        layout.addWidget(button)
        self.setLayout(layout)

    def log_entry(self, entry):
        self.listWidget.addItem(QListWidgetItem(entry))

    def closeEvent(self, event):
        self.ocr.close()
        event.accept()


class OCRWindow(QMainWindow):
    
    OCR_BOX = (785, 400, 400, 380)
    BUTTON = (1340, 460, 16, 16)

    OCR_VERSION = 'easyocr'

    def __init__(self):
        super().__init__()

        self.ocr = easyocr.Reader(['en', 'de'])

        self.dialog = Dialog(self)
        self.dialog.show()

        self.counter = ChestCounter(self.dialog.log_entry)
        self.dialog.log_entry("Ready")

        for m in get_monitors():
            print(str(m))
            if m.is_primary:
                self.setGeometry(m.x, m.y, m.width, m.height)

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setWindowFlags(Qt.FramelessWindowHint)

    def paintEvent(self, e):
        qp = QPainter()
        qp.begin(self)
        pen = QPen(Qt.red, 2, Qt.SolidLine)
        qp.setPen(pen)
        qp.drawRect(self.OCR_BOX[0], self.OCR_BOX[1], self.OCR_BOX[2], self.OCR_BOX[3])
        qp.drawRect(self.BUTTON[0], self.BUTTON[1], self.BUTTON[2], self.BUTTON[3])
        qp.end()

    def start(self):
        total_chests = []
        while (True):    
            chests = self.grab()
            if len(chests) > 0:
                total_chests.extend(chests)
                self.next()
            else:
                break

        self.dialog.log_entry(f'Found chests: {len(total_chests)}')

        self.dialog.activateWindow()

        self.counter.export(total_chests)

    def grab(self):
        screenshot = ImageGrab.grab(bbox=(self.OCR_BOX[0], self.OCR_BOX[1], self.OCR_BOX[0] + self.OCR_BOX[2], self.OCR_BOX[1] + self.OCR_BOX[3]))

        if self.OCR_VERSION == 'easyocr':
            try:
                image = numpy.array(screenshot)
                text_lines = self.ocr.readtext(image, detail=0)
            except Exception as e:
                text_lines = []
        else:
            try:
                text_lines = pytesseract.image_to_string(screenshot).split("\n")
            except Exception as e:
                text_lines = []

        screenshot.close()

        try:
            chests = self.counter.parse(text_lines)
        except ChestException:
            chests = []

        return chests
    
    def next(self):
        for i in range(4):
            pyautogui.click(self.BUTTON[0] + (self.BUTTON[2] / 2), self.BUTTON[1] + (self.BUTTON[3] / 2))
            time.sleep(0.5)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = OCRWindow()
    window.show()
    sys.exit(app.exec_())
