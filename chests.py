import sys
import time

# pip install pyqt5
from PyQt5.QtGui import QPainter, QPen
from PyQt5.QtWidgets import QMainWindow, QApplication, QPushButton
from PyQt5.QtCore import Qt, pyqtSlot

# pip install screeninfo
from screeninfo import get_monitors

# pip install pillow
from PIL import ImageGrab

# pip install pytesseract
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'

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


class OCRWindow(QMainWindow):
    
    BOX = (785, 400, 400, 380)
    BUTTON = (1340, 460, 16, 16)

    def __init__(self):
        super().__init__()

        for m in get_monitors():
            print(str(m))
            if m.is_primary:
                self.setGeometry(m.x, m.y, m.width, m.height)

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.FramelessWindowHint)

        button = QPushButton('Start chest tracker', self)
        button.move(1300, 900)
        button.clicked.connect(self.on_start)

        self.show()

    @pyqtSlot()
    def on_start(self):
        total_chests = []
        while (True):    
            chests = self.grab()
            if len(chests) > 0:
                total_chests.extend(chests)
                self.next()
            else:
                break

            #break

        export = Export()
        export.csv(total_chests)

    def paintEvent(self, e):
        qp = QPainter()
        qp.begin(self)
        pen = QPen(Qt.red, 2, Qt.SolidLine)
        qp.setPen(pen)
        qp.drawRect(self.BOX[0], self.BOX[1], self.BOX[2], self.BOX[3])
        qp.drawRect(self.BUTTON[0], self.BUTTON[1], self.BUTTON[2], self.BUTTON[3])
        qp.end()

    def grab(self):
        screenshot = ImageGrab.grab(bbox=(self.BOX[0], self.BOX[1], self.BOX[0] + self.BOX[2], self.BOX[1] + self.BOX[3]))
        try:
            text_lines = pytesseract.image_to_string(screenshot).split("\n")
        except Exception:
            text_lines = []
        screenshot.close()

        try:
            chests = self.parse(text_lines)
        except ChestException:
            chests = []

        return chests
    
    def next(self):
        for i in range(4):
            pyautogui.click(self.BUTTON[0] + (self.BUTTON[2] / 2), self.BUTTON[1] + (self.BUTTON[3] / 2))
            time.sleep(0.5)

    def parse(self, text_lines):
        chests = []
        chest = Chest()
        for line in text_lines:
            if len(line) == 0:
                continue
            if len(chest.name) == 0:
                chest.name = line
            elif len(chest.player) == 0:
                if not line.startswith('From'):
                    raise ChestException()
                s = line.split(' ')
                s.pop(0)
                chest.player = ' '.join(s)
            elif len(chest.source) == 0:
                if not line.startswith('Source'):
                    raise ChestException()
                s = line.split(' ')
                s.pop(0)
                chest.source = ' '.join(s)
            if chest.valid():
                chests.append(chest)
                print(chest)
                chest = Chest()
        return chests


class Export:

    def csv(self, chests):
        SEP = ';'
        EOL = '\n'

        self.players = []
        self.sources = ['']
        self.player_chests = {}
        for chest in chests:
            if not chest.player in self.players:
                self.players.append(chest.player)

            if not chest.source in self.sources:
                self.sources.append(chest.source)
            
            if not chest.player in self.player_chests:
                self.player_chests[chest.player] = []
            self.player_chests[chest.player].append(chest)            

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


if __name__ == '__main__':

    app = QApplication(sys.argv)
    ocr = OCRWindow()
    sys.exit(app.exec_())
