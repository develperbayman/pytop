import sys
import psutil
import threading
import time
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QListWidget, QVBoxLayout, QWidget, QAction, QMenu, QSlider, QDialog, QPushButton, QHBoxLayout, QGridLayout, QComboBox, QLineEdit
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt, QTimer
import pyqtgraph as pg
from pyqtgraph import PlotWidget
from qt_material import apply_stylesheet

class ProcessInfo:
    def __init__(self, pid, name, cpu, mem):
        self.pid = pid
        self.name = name
        self.cpu = cpu
        self.mem = mem

def update_processes():
    global processes
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            processes.append(ProcessInfo(proc.info['pid'], proc.info['name'], proc.info['cpu_percent'], proc.info['memory_percent']))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle('pytop')
        self.update_speed = 1  # Default update speed is 1 second
        self.grouping_criteria = 'None'
        self.filter_keyword = ''
        self.init_ui()
        self.cpu_data = [[] for _ in range(psutil.cpu_count(logical=True))]

    def init_ui(self):
        # Apply material dark theme
        apply_stylesheet(app, theme='dark_blue.xml')

        # Menu Bar
        menu_bar = self.menuBar()
        options_menu = menu_bar.addMenu('Options')

        update_speed_action = QAction('Update Speed', self)
        update_speed_action.triggered.connect(self.show_update_speed_dialog)
        options_menu.addAction(update_speed_action)

        # Running Processes Label
        title_label = QLabel('Running Processes', self)
        title_label.setFont(QFont('Helvetica', 16))
        title_label.setAlignment(Qt.AlignCenter)

        # Grouping Combo Box
        self.grouping_combo = QComboBox(self)
        self.grouping_combo.addItems(['None', 'CPU Usage', 'RAM Usage'])
        self.grouping_combo.currentTextChanged.connect(self.update_grouping_criteria)

        # Search Box
        self.search_box = QLineEdit(self)
        self.search_box.setPlaceholderText('Filter by keyword')
        self.search_box.textChanged.connect(self.update_filter_keyword)

        # Process List
        self.process_list = QListWidget(self)
        self.process_list.setFont(QFont('Courier', 12))
        self.process_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.process_list.customContextMenuRequested.connect(self.show_context_menu)

        # CPU Usage per Core
        self.cpu_plots = []
        self.cpu_labels = []
        self.cpu_percent_labels = []
        cpu_count = psutil.cpu_count(logical=True)
        self.grid_layout = QGridLayout()
        for i in range(cpu_count):
            percent_label = QLabel(f'0%', self)
            percent_label.setFont(QFont('Helvetica', 12))
            percent_label.setAlignment(Qt.AlignCenter)
            self.cpu_percent_labels.append(percent_label)

            label = QLabel(f'CPU Core {i + 1}', self)
            label.setFont(QFont('Helvetica', 12))
            label.setAlignment(Qt.AlignCenter)
            self.cpu_labels.append(label)

            plot = PlotWidget(self)
            plot.setBackground('#1C1C1C')
            plot.setYRange(0, 100)
            plot.getPlotItem().hideAxis('left')
            plot.getPlotItem().hideAxis('bottom')
            self.cpu_plots.append(plot)

            self.grid_layout.addWidget(label, i * 2, 0)
            self.grid_layout.addWidget(percent_label, i * 2, 1)
            self.grid_layout.addWidget(plot, i * 2 + 1, 0, 1, 2)

        # Layouts
        self.layout = QVBoxLayout()
        self.layout.addWidget(title_label)
        self.layout.addWidget(self.grouping_combo)
        self.layout.addWidget(self.search_box)
        self.layout.addWidget(self.process_list)

        self.plot_layout = QVBoxLayout()
        self.plot_layout.addLayout(self.grid_layout)

        central_widget = QWidget(self)
        self.main_layout = QHBoxLayout(central_widget)
        self.main_layout.addLayout(self.layout)
        self.main_layout.addLayout(self.plot_layout)
        self.setCentralWidget(central_widget)

        # Data collection thread
        self.update_thread = threading.Thread(target=self.update_data)
        self.update_thread.start()

        # Timer for GUI updates
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_ui)
        self.update_timer.start(self.update_speed * 1000)  # Update every 1 second

    def update_data(self):
        while True:
            update_processes()
            cpu_percentages = psutil.cpu_percent(percpu=True)
            for i, percentage in enumerate(cpu_percentages):
                if len(self.cpu_data[i]) >= 50:  # Keep only the latest 50 data points
                    self.cpu_data[i].pop(0)
                self.cpu_data[i].append(percentage)
            time.sleep(self.update_speed)  # Update every update_speed seconds

    def update_ui(self):
        # Update CPU Plots and Labels
        for i, (plot, percent_label) in enumerate(zip(self.cpu_plots, self.cpu_percent_labels)):
            plot.clear()
            plot.plot(self.cpu_data[i], pen=pg.mkPen('r', width=2), fillLevel=0, brush='r')
            percent_label.setText(f'{self.cpu_data[i][-1]:.1f}%')

        # Update Process List
        filtered_processes = self.filter_processes(processes)
        self.process_list.clear()
        for proc in filtered_processes:
            self.process_list.addItem(f'{proc.pid} - {proc.name} - CPU: {proc.cpu}% - Memory: {proc.mem}%')

    def filter_processes(self, processes):
        filtered_processes = processes

        if self.filter_keyword:
            filtered_processes = [proc for proc in filtered_processes if self.filter_keyword.lower() in proc.name.lower()]

        if self.grouping_criteria == 'CPU Usage':
            filtered_processes.sort(key=lambda p: p.cpu, reverse=True)
        elif self.grouping_criteria == 'RAM Usage':
            filtered_processes.sort(key=lambda p: p.mem, reverse=True)

        return filtered_processes

    def update_grouping_criteria(self, text):
        self.grouping_criteria = text
        self.update_ui()

    def update_filter_keyword(self, text):
        self.filter_keyword = text
        self.update_ui()

    def show_context_menu(self, pos):
        context_menu = QMenu(self)
        context_menu.addAction('Kill Process', self.kill_process)
        context_menu.exec_(self.process_list.mapToGlobal(pos))

    def kill_process(self):
        selected_item = self.process_list.currentItem()
        if selected_item:
            selected_index = self.process_list.indexFromItem(selected_item).row()
            selected_proc = processes[selected_index]
            try:
                proc = psutil.Process(selected_proc.pid)
                proc.kill()
                print(f"Killed process with PID {selected_proc.pid}")
            except Exception as e:
                print(f"Failed to kill process: {e}")

    def show_update_speed_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Update Speed')

        layout = QVBoxLayout(dialog)

        slider = QSlider(Qt.Horizontal, dialog)
        slider.setRange(1, 10)
        slider.setValue(self.update_speed)
        slider.setTickInterval(1)
        slider.setTickPosition(QSlider.TicksBelow)
        layout.addWidget(slider)

        button_layout = QHBoxLayout()
        ok_button = QPushButton('OK', dialog)
        cancel_button = QPushButton('Cancel', dialog)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

        ok_button.clicked.connect(lambda: self.set_update_speed(slider.value(), dialog))
        cancel_button.clicked.connect(dialog.reject)

        dialog.setLayout(layout)
        dialog.exec_()

    def set_update_speed(self, value, dialog):
        self.update_speed = value
        self.update_timer.setInterval(self.update_speed * 1000)
        dialog.accept()

if __name__ == '__main__':
    processes = []  # Initialize the global processes list
    app = QApplication(sys.argv)
    main_app = MainApp()
    main_app.show()
    sys.exit(app.exec_())
