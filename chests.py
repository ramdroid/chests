import sys
import time

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(filename='chests.log', encoding='utf-8', level=logging.DEBUG)

from datetime import datetime

# pip install pyqt5
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

# pip install screeninfo
from screeninfo import get_monitors

# pip install pillow
from PIL import ImageGrab

# pip install easyocr
import easyocr

# pip install numpy
import numpy

# pip install pyautogui
import pyautogui

# pip install reportlab
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.piecharts import Pie

SEP = ';'
EOL = '\n'


class Chest:

    player = ''
    source = ''
    name = ''
    count = 1
    
    def __str__(self):
        return f'{self.player}: {self.source}'
    
    def __iter__(self):
        return iter((self.player, self.source, self.name))

    def valid(self):
        return len(self.name) > 0 and len(self.player) > 0 and len(self.source) > 0
    
    def points(self):
        segs = self.source.split(' ')
        for seg in segs:
            try:
                idx = seg.find('-')
                if idx > 0:
                    # runic/ancient levels
                    return int(seg[idx+1:])
                else:
                    return int(seg)
            except ValueError:
                pass
        return 0
    
    def vault_level(self):
        segs = self.source.split(' ')
        for seg in segs:
            if '-' in seg:
                return seg
            elif '45' in seg:
                return seg
        return ''
    
    def is_crypt(self):
        return 'Crypt' in self.source
    
    def is_citadel(self):
        return 'Citadel' in self.source
    
    def is_runic(self):
        return 'Raid Runic squad' in self.source
    
    def is_vault(self):
        return 'Vault' in self.source
    
    def is_ancient(self):
        return 'Rise of the Ancients event' in self.source
    
    def is_heroic(self):
        return 'heroic Monster' in self.source
    

class ChestException(Exception):
    pass


class ChestCounter:

    def __init__(self, log_callback):
        self.log_callback = log_callback

    def parse(self, text_lines):
        chests = []
        chest = Chest()
        has_player = False
        has_source = False
        for line in text_lines:
            if len(line) == 0:
                continue

            logger.debug(line)

            if 'PRBS' in line:
                pass # what's going on with this one?

            if has_player or (len(chest.player) == 0 and line.startswith('From')):
                if has_player:
                    chest.player = line
                else:
                    s = line.split(' ')
                    s.pop(0)
                    chest.player = ' '.join(s).replace('.', '') # faulty dots are sometimes added by OCR
                has_player = len(chest.player) == 0 # split over two lines
            elif has_source or (len(chest.source) == 0 and line.startswith('Source')):
                if has_source:
                    chest.source = line
                else:
                    s = line.split(' ')
                    s.pop(0)
                    chest.source = ' '.join(s)
                has_source = len(chest.source) == 0 # split over two lines
            else:
                chest.name = ' '.join([chest.name, line]).strip()

            if chest.valid():
                chests.append(chest)
                self.log_callback(str(chest))
                logger.info(f' ---> {str(chest)}')
                chest = Chest()

        return chests
    
    def load(self):
        chests = []
        try:
            with open("chests.csv", "r", encoding='utf-8') as f:
                headers = []
                for line in f:
                    columns = line.replace("\n", "").split(SEP)
                    if len(columns[0]) == 0:
                        headers = columns
                    else:
                        for i in range(1, len(columns)):
                            chest = Chest()
                            chest.player = columns[0]
                            chest.source = chest.name = headers[i]
                            chest.count = int(columns[i])
                            if chest.count > 0:
                                chests.append(chest)
        except Exception:
            pass

        if len(chests) > 0:
            self.log_callback(f"Ready. Loaded {len(chests)} chests")
        else:
            self.log_callback("Ready.")

        return chests
    
    def _collect(self, chests):
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

    def save(self, chests):
        self._collect(chests)
        with open("chests.csv", "w", encoding='utf-8') as f:
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

    def report(self, chests):
        self._collect(chests)

        # calculate total chest points for each player
        player_points = {}
        player_crypts = {}
        player_citadels = {}
        player_runics = {}
        player_vaults = {}
        player_ancients = {}
        player_heroics = {}

        all_vaults = {}

        for player in self.players:
            points = 0
            crypts = 0
            citadels = 0
            runics = 0
            vaults = 0
            ancients = 0
            heroics = 0

            for chest in self.player_chests[player]:
                points += chest.points()
                if chest.is_crypt():
                    crypts += chest.count
                elif chest.is_citadel():
                    citadels += chest.count
                elif chest.is_runic():
                    runics += chest.count
                elif chest.is_vault():
                    vaults += chest.count
                    level = chest.vault_level()
                    if not level in all_vaults:
                        all_vaults[level] = 0
                    all_vaults[level] += chest.count
                elif chest.is_ancient():
                    ancients += chest.count
                elif chest.is_heroic():
                    points += chest.points()
                    heroics += chest.count

            player_points[player] = points
            player_crypts[player] = crypts
            player_citadels[player] = citadels
            player_runics[player] = runics
            player_vaults[player] = vaults
            player_ancients[player] = ancients
            player_heroics[player] = heroics

        sorted_points = sorted(player_points.items(), key=lambda x: x[1], reverse=True)

        # prepare PDF document

        date = datetime.today().strftime('%Y-%m-%d')
        filename = "report_" +  date + '.pdf'
        doc = SimpleDocTemplate(filename, pagesize=A4)
        elements = []
        elements.append(Paragraph("Chest Report " + date, ParagraphStyle(name='Normal',fontSize=18)))

        # collect table data 

        top_players = []
        top_points = []

        data = [['Name', 'Points', 'Crypts', 'Citadels', 'Raid runics', 'Vaults', 'Ancient chests', 'Heroics']]
        for pts in sorted_points:
            p = pts[0]
            data.append([
                p, 
                str(pts[1]), 
                str(player_crypts[p]), 
                str(player_citadels[p]), 
                str(player_runics[p]), 
                str(player_vaults[p]),
                str(player_ancients[p]),
                str(player_heroics[p])
            ])

            if len(top_players) < 5:
                top_players.append(pts[0])
                top_points.append(pts[1])

        # pie colors
        pie_colors = [colors.red, colors.blue, colors.green, colors.yellow, colors.gray]

        # top players
        
        pie = Pie()
        pie.x = 200
        pie.y = 40
        pie.sideLabels = True
        pie.data = top_points
        pie.labels = top_players
        for i in range(len(pie_colors)):
            pie.slices[i].fillColor = pie_colors[i]

        drawing = Drawing(400, 200)
        drawing.add(String(0, 140, 'Top players', fontSize=14))
        drawing.add(pie)
        elements.append(drawing)

        # vaults

        if len(all_vaults) > 0:
            pie = Pie()
            pie.x = 200
            pie.y = 50
            pie.sideLabels = True
            pie.data = list(all_vaults.values())
            pie.labels = list(all_vaults.keys())
            for i in range(len(pie_colors)):
                pie.slices[i].fillColor = pie_colors[i]

            drawing = Drawing(400, 200)
            drawing.add(String(0, 140, 'Vaults', fontSize=14))
            drawing.add(pie)
            elements.append(drawing)

        # table with player total points

        table = Table(data)
        style = TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black)])
        table.setStyle(style)
        elements.append(table)

        doc.build(elements)

def iconPushButton(base64, callback, width=0, height=0):
    pixmap = QPixmap()
    pixmap.loadFromData(QByteArray.fromBase64(base64))

    button = QPushButton()
    button.setIcon(QIcon(pixmap))
    button.setStyleSheet(f"max-width: {pixmap.width()}px; max-height: {pixmap.height()}px")
    if width > 0 and height > 0:
        button.setIconSize(QSize(width, height))
    button.clicked.connect(callback)
    return button

def button_style(color):
    style = ':enabled { background-color: ' + color + '; color: white; font-weight: bold }'
    style += ':disabled { background-color: gray; color: black; }'
    return style


class OCRControl(QWidget):

    STEP = 10

    ICON_LEFT = b"PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgZmlsbC1ydWxlPSJldmVub2RkIiBjbGlwLXJ1bGU9ImV2ZW5vZGQiPjxwYXRoIGQ9Ik0xMiAwYzYuNjIzIDAgMTIgNS4zNzcgMTIgMTJzLTUuMzc3IDEyLTEyIDEyLTEyLTUuMzc3LTEyLTEyIDUuMzc3LTEyIDEyLTEyem0wIDFjNi4wNzEgMCAxMSA0LjkyOSAxMSAxMXMtNC45MjkgMTEtMTEgMTEtMTEtNC45MjktMTEtMTEgNC45MjktMTEgMTEtMTF6bTMgNS43NTNsLTYuNDQgNS4yNDcgNi40NCA1LjI2My0uNjc4LjczNy03LjMyMi02IDcuMzM1LTYgLjY2NS43NTN6Ii8+PC9zdmc+"
    ICON_RIGHT = b"PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgZmlsbC1ydWxlPSJldmVub2RkIiBjbGlwLXJ1bGU9ImV2ZW5vZGQiPjxwYXRoIGQ9Ik0xMiAwYzYuNjIzIDAgMTIgNS4zNzcgMTIgMTJzLTUuMzc3IDEyLTEyIDEyLTEyLTUuMzc3LTEyLTEyIDUuMzc3LTEyIDEyLTEyem0wIDFjNi4wNzEgMCAxMSA0LjkyOSAxMSAxMXMtNC45MjkgMTEtMTEgMTEtMTEtNC45MjktMTEtMTEgNC45MjktMTEgMTEtMTF6bS0zIDUuNzUzbDYuNDQgNS4yNDctNi40NCA1LjI2My42NzguNzM3IDcuMzIyLTYtNy4zMzUtNi0uNjY1Ljc1M3oiLz48L3N2Zz4="
    ICON_UP = b"PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgZmlsbC1ydWxlPSJldmVub2RkIiBjbGlwLXJ1bGU9ImV2ZW5vZGQiPjxwYXRoIGQ9Ik0xMiAwYzYuNjIzIDAgMTIgNS4zNzcgMTIgMTJzLTUuMzc3IDEyLTEyIDEyLTEyLTUuMzc3LTEyLTEyIDUuMzc3LTEyIDEyLTEyem0wIDFjNi4wNzEgMCAxMSA0LjkyOSAxMSAxMXMtNC45MjkgMTEtMTEgMTEtMTEtNC45MjktMTEtMTEgNC45MjktMTEgMTEtMTF6bTUuMjQ3IDE1bC01LjI0Ny02LjQ0LTUuMjYzIDYuNDQtLjczNy0uNjc4IDYtNy4zMjIgNiA3LjMzNS0uNzUzLjY2NXoiLz48L3N2Zz4="
    ICON_DOWN = b"PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgZmlsbC1ydWxlPSJldmVub2RkIiBjbGlwLXJ1bGU9ImV2ZW5vZGQiPjxwYXRoIGQ9Ik0xMiAwYzYuNjIzIDAgMTIgNS4zNzcgMTIgMTJzLTUuMzc3IDEyLTEyIDEyLTEyLTUuMzc3LTEyLTEyIDUuMzc3LTEyIDEyLTEyem0wIDFjNi4wNzEgMCAxMSA0LjkyOSAxMSAxMXMtNC45MjkgMTEtMTEgMTEtMTEtNC45MjktMTEtMTEgNC45MjktMTEgMTEtMTF6bTUuMjQ3IDhsLTUuMjQ3IDYuNDQtNS4yNjMtNi40NC0uNzM3LjY3OCA2IDcuMzIyIDYtNy4zMzUtLjc1My0uNjY1eiIvPjwvc3ZnPg=="

    def __init__(self, ocr):
        super().__init__()
        self.ocr = ocr
        self.type = 'ocr'

        self.setStyleSheet(f"max-width: 250px")

        up = iconPushButton(self.ICON_UP, self.moveUp)
        down = iconPushButton(self.ICON_DOWN, self.moveDown)
        left = iconPushButton(self.ICON_LEFT, self.moveLeft)
        right = iconPushButton(self.ICON_RIGHT, self.moveRight)

        self.widthSlider = QSlider()
        self.widthSlider.setStyleSheet(f"max-width: 120px")
        self.widthSlider.setOrientation(Qt.Horizontal)
        self.widthSlider.setRange(1, int(self.ocr.max_width / 2))
        self.widthSlider.setSliderPosition(self.ocr.OCR_BOX[2])
        self.widthSlider.valueChanged.connect(self.widthChanged)

        self.heightSlider = QSlider()
        self.heightSlider.setStyleSheet(f"max-width: 20px; max-height: 100px")
        self.heightSlider.setOrientation(Qt.Vertical)
        self.heightSlider.setInvertedAppearance(True)
        self.heightSlider.setRange(1, int(self.ocr.max_height / 2))
        self.heightSlider.setSliderPosition(self.ocr.OCR_BOX[3])
        self.heightSlider.valueChanged.connect(self.heightChanged)

        joystickGrid = QGridLayout()
        joystickGrid.addWidget(up, 0, 1)
        joystickGrid.addWidget(left, 1, 0)
        joystickGrid.addWidget(right, 1, 2)
        joystickGrid.addWidget(down, 2, 1)

        joystick = QWidget()
        joystick.setStyleSheet(f"max-width: 150px; max-height: 100px")
        joystick.setLayout(joystickGrid)

        radioBox = QRadioButton("Box")
        radioBox.setChecked(True)
        radioBox.toggled.connect(self.radioBoxClicked)
        radioButton = QRadioButton("Button")
        radioButton.toggled.connect(self.radioButtonClicked)

        radioLayout = QVBoxLayout()
        radioLayout.addWidget(radioBox)
        radioLayout.addWidget(radioButton)

        radios = QWidget()
        radios.setLayout(radioLayout)

        group = QButtonGroup()
        group.addButton(radioBox)
        group.addButton(radioButton)

        layoutH = QHBoxLayout()
        layoutH.addWidget(self.heightSlider)
        layoutH.addWidget(joystick)
        layoutH.addWidget(radios)

        layoutV = QVBoxLayout()
        layoutV.addWidget(self.widthSlider)
        layoutV.addLayout(layoutH)

        self.setLayout(layoutV)

    def radioBoxClicked(self, enabled):
        if enabled:
            self.type = 'ocr'
            self.enableSliders(True)
    
    def radioButtonClicked(self, enabled):
        if enabled:
            self.type = 'button'
            self.enableSliders(False)

    def enableSliders(self, enabled):
        self.heightSlider.setEnabled(enabled)
        self.widthSlider.setEnabled(enabled)

    def moveUp(self):
        self.ocr.move(self.type, 0, -1 * self.STEP)

    def moveDown(self):
        self.ocr.move(self.type, 0, 1 * self.STEP)

    def moveLeft(self):
        self.ocr.move(self.type, -1 * self.STEP, 0)

    def moveRight(self):
        self.ocr.move(self.type, 1 * self.STEP, 0)

    def widthChanged(self, value):
        self.ocr.moveWidth(self.type, value)

    def heightChanged(self, value):
        self.ocr.moveHeight(self.type, value)


class Dialog(QWidget):

    ICON_REPORT = b'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'

    def __init__(self, ocr):
        super().__init__()
        self.ocr = ocr

        self.settings = QSettings('ramdroid', 'chests')
        if self.settings.contains("geometry"):
            self.restoreGeometry(self.settings.value("geometry"))
        else:
            self.setGeometry(1500, 400, 300, 500)

        if self.settings.contains("ocr/box"):
            self.ocr.OCR_BOX = self.settings.value("ocr/box")
        if self.settings.contains("button/box"):
            self.ocr.BUTTON = self.settings.value("button/box")

        if self.settings.contains("ocr/calibrated"):
            self.ocr.ocr_calibrated = self.settings.value("ocr/calibrated") == 'true'

        self.setWindowTitle("Chest counter")

        self.listWidget = QListWidget()

        self.ocrControl = OCRControl(self.ocr)

        self.buttonTest = QPushButton('Test', self)
        self.buttonTest.setStyleSheet(button_style('blue'))
        self.buttonTest.clicked.connect(self.ocr.test)
        
        checkBoCalibrate = QCheckBox(self)
        checkBoCalibrate.setText('Calibrate')
        if self.settings.contains("ocr/visible"):
            ocr_checked = self.settings.value("ocr/visible") == 'true'
            checkBoCalibrate.setChecked(ocr_checked)
            self.toggleOCR(ocr_checked)
        else:
            self.toggleOCR(False)
        checkBoCalibrate.stateChanged.connect(self.toggleOCR)

        panelLayout = QHBoxLayout()
        panelLayout.addWidget(checkBoCalibrate)
        panelLayout.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        panelLayout.addWidget(self.buttonTest)
        
        calibratePanel = QWidget()
        calibratePanel.setLayout(panelLayout)
        
        self.buttonStart = QPushButton('Start', self)
        self.buttonStart.setStyleSheet(button_style('red'))
        self.buttonStart.clicked.connect(self.ocr.start)

        buttonReport = iconPushButton(self.ICON_REPORT, self.ocr.on_report, 32, 32)

        toolbar = QHBoxLayout()
        toolbar.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        toolbar.addWidget(buttonReport)

        layout = QVBoxLayout()
        layout.addLayout(toolbar)
        layout.addWidget(self.listWidget)
        layout.addWidget(self.ocrControl)
        layout.addWidget(calibratePanel)
        layout.addWidget(self.buttonStart)
        self.setLayout(layout)

        self.on_calibrated()

    def on_calibrated(self):
        self.buttonStart.setEnabled(self.ocr.ocr_calibrated)

    def toggleOCR(self, checked):
        self.buttonTest.setVisible(checked)
        self.ocrControl.setVisible(checked)
        self.ocr.toggleOCR(checked)

    def log_entry(self, entry):
        item = QListWidgetItem(entry)
        self.listWidget.addItem(item)
        self.listWidget.scrollToItem(item)

    def closeEvent(self, event):
        self.save_settings()
        self.ocr.close()
        event.accept()

    def save_settings(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.beginGroup("ocr")
        self.settings.setValue("calibrated", self.ocr.ocr_calibrated)
        self.settings.setValue("visible", self.ocr.ocr_visible)
        self.settings.setValue("box", self.ocr.OCR_BOX)
        self.settings.endGroup()
        self.settings.beginGroup("button")
        self.settings.setValue("visible", self.ocr.button_visible)
        self.settings.setValue("box", self.ocr.BUTTON)
        self.settings.endGroup()


class OCRWindow(QMainWindow):
    
    OCR_BOX = (785, 400, 400, 380)
    BUTTON = (1340, 460, 16, 16)

    def __init__(self):
        super().__init__()

        for m in get_monitors():
            print(str(m))
            if m.is_primary:
                self.setGeometry(m.x, m.y, m.width, m.height)
                self.max_width = m.width
                self.max_height = m.height

        self.ocr = easyocr.Reader(['en', 'de'])
        self.ocr_visible = False
        self.button_visible = False
        self.ocr_calibrated = False

        self.dialog = Dialog(self)
        self.dialog.show()

        self.counter = ChestCounter(self.dialog.log_entry)
        self.total_chests = self.counter.load()

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setWindowFlags(Qt.FramelessWindowHint)

    def on_report(self):
        self.counter.report(self.total_chests)

    def move(self, type, x, y):
        if type == 'ocr':
            self.OCR_BOX = (self.OCR_BOX[0] + x, self.OCR_BOX[1] + y, self.OCR_BOX[2] + x, self.OCR_BOX[3] + y)
        else:
            self.BUTTON = (self.BUTTON[0] + x, self.BUTTON[1] + y, self.BUTTON[2], self.BUTTON[3])
        self.update()
        self.update_calibrated(False)

    def moveWidth(self, type, width):
        self.OCR_BOX = (self.OCR_BOX[0], self.OCR_BOX[1], width, self.OCR_BOX[3])
        self.update()
        self.update_calibrated(False)

    def moveHeight(self, type, height):
        self.OCR_BOX = (self.OCR_BOX[0], self.OCR_BOX[1], self.OCR_BOX[2], height)
        self.update()
        self.update_calibrated(False)

    def toggleOCR(self, checked):
        self.ocr_visible = checked
        self.update()

    def paintEvent(self, e):
        qp = QPainter()
        qp.begin(self)
        if self.ocr_visible or self.button_visible:
            qp.setPen(QPen(Qt.red, 2, Qt.SolidLine))
            qp.drawRect(self.OCR_BOX[0], self.OCR_BOX[1], self.OCR_BOX[2], self.OCR_BOX[3])
            qp.drawRect(self.BUTTON[0], self.BUTTON[1], self.BUTTON[2], self.BUTTON[3])
        qp.end()

    def test(self):
        chests = self.grab()
        result = len(chests) == 4
        self.dialog.log_entry(f'Calibration {"OK" if result else "FAILED"}: found {len(chests)} of 4 chests')
        self.dialog.activateWindow()
        self.update_calibrated(result)

    def update_calibrated(self, value):
        if not value and self.ocr_calibrated:
            self.dialog.log_entry(f'Calibration reset')
        self.ocr_calibrated = value
        self.dialog.on_calibrated()

    def start(self):
        while (True):    
            chests = self.grab()
            if len(chests) > 0:
                self.total_chests.extend(chests)
                self.next()
            else:
                break

        self.dialog.log_entry(f'Total chests: {len(self.total_chests)}')

        self.dialog.activateWindow()

        self.counter.save(self.total_chests)

    def grab(self):
        screenshot = ImageGrab.grab(bbox=(self.OCR_BOX[0], self.OCR_BOX[1], self.OCR_BOX[0] + self.OCR_BOX[2], self.OCR_BOX[1] + self.OCR_BOX[3]))

        try:
            image = numpy.array(screenshot)
            text_lines = self.ocr.readtext(image, detail=0)
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
