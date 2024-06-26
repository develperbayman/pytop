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
    def __init__(self, pid, name, cpu, mem, gpu_mem):
        self.pid = pid
        self.name = name
        self.cpu = cpu
        self.mem = mem
        self.gpu_mem = gpu_mem

def update_processes():
    global processes
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
        try:
            pinfo = proc.info
            pid = pinfo['pid']
            name = pinfo['name']
            cpu = pinfo['cpu_percent']
            mem = pinfo['memory_info'].rss / (1024 * 1024)  # Memory usage in MB
            gpu_mem = get_gpu_memory_usage(pid)  # Get GPU memory usage for each process
            processes.append(ProcessInfo(pid, name, cpu, mem, gpu_mem))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

def get_gpu_memory_usage(pid):
    try:
        process = psutil.Process(pid)
        for conn in process.connections():
            if conn.type == psutil.CONN_NONE and conn.status == psutil.CONN_NONE:
                return conn.raddr.port  # Just a placeholder value for GPU memory usage, you should replace this
    except psutil.NoSuchProcess:
        pass
    return 0  # If GPU memory usage cannot be determined, return 0

def get_total_gpu_memory_usage():
    total_gpu_mem = 0
    for proc in processes:
        total_gpu_mem += proc.gpu_mem
    return total_gpu_mem

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle('pytop')
        self.update_speed = 1  # Default update speed is 1 second
        self.grouping_criteria = 'None'
        self.filter_keyword = ''
        self.init_ui()
        self.cpu_data = [[] for _ in range(psutil.cpu_count(logical=True))]
        self.gpu_data = []
        self.net_sent_data = []
        self.net_recv_data = []
        self.prev_net_io = psutil.net_io_counters()

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

        # GPU Usage
        self.gpu_plot = PlotWidget(self)
        self.gpu_plot.setBackground('#1C1C1C')
        self.gpu_plot.setYRange(0, 100)
        self.gpu_plot.getPlotItem().hideAxis('left')
        self.gpu_plot.getPlotItem().hideAxis('bottom')
        gpu_label = QLabel('GPU Usage', self)
        gpu_label.setFont(QFont('Helvetica', 12))
        gpu_label.setAlignment(Qt.AlignCenter)
        self.grid_layout.addWidget(gpu_label, cpu_count * 2, 0)
        self.grid_layout.addWidget(self.gpu_plot, cpu_count * 2 + 1, 0, 1, 2)

        # Network I/O
        self.net_sent_plot = PlotWidget(self)
        self.net_sent_plot.setBackground('#1C1C1C')
        self.net_sent_plot.setYRange(0, 100)
        self.net_sent_plot.getPlotItem().hideAxis('left')
        self.net_sent_plot.getPlotItem().hideAxis('bottom')
        net_sent_label = QLabel('Network Sent (KB/s)', self)
        net_sent_label.setFont(QFont('Helvetica', 12))
        net_sent_label.setAlignment(Qt.AlignCenter)

        self.net_recv_plot = PlotWidget(self)
        self.net_recv_plot.setBackground('#1C1C1C')
        self.net_recv_plot.setYRange(0, 100)
        self.net_recv_plot.getPlotItem().hideAxis('left')
        self.net_recv_plot.getPlotItem().hideAxis('bottom')
        net_recv_label = QLabel('Network Received (KB/s)', self)
        net_recv_label.setFont(QFont('Helvetica', 12))
        net_recv_label.setAlignment(Qt.AlignCenter)

        self.grid_layout.addWidget(net_sent_label, cpu_count * 2 + 2, 0)
        self.grid_layout.addWidget(self.net_sent_plot, cpu_count * 2 + 3, 0, 1, 2)
        self.grid_layout.addWidget(net_recv_label, cpu_count * 2 + 4, 0)
        self.grid_layout.addWidget(self.net_recv_plot, cpu_count * 2 + 5, 0, 1, 2)

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
            if len(self.gpu_data) >= 50:  # Keep only the latest 50 data points
                self.gpu_data.pop(0)
            self.gpu_data.append(get_total_gpu_memory_usage())  # Update GPU usage data

            net_io = psutil.net_io_counters()
            net_sent = (net_io.bytes_sent - self.prev_net_io.bytes_sent) / 1024  # Convert to KB
            net_recv = (net_io.bytes_recv - self.prev_net_io.bytes_recv) / 1024  # Convert to KB
            self.prev_net_io = net_io

            if len(self.net_sent_data) >= 50:
                self.net_sent_data.pop(0)
            if len(self.net_recv_data) >= 50:
                self.net_recv_data.pop(0)
            self.net_sent_data.append(net_sent)
            self.net_recv_data.append(net_recv)

            time.sleep(self.update_speed)  # Update every update_speed seconds

    def update_ui(self):
        # Update CPU Plots and Labels
        for i, (plot, percent_label) in enumerate(zip(self.cpu_plots, self.cpu_percent_labels)):
            if self.cpu_data[i]:
                plot.clear()
                plot.plot(self.cpu_data[i], pen=pg.mkPen('r', width=2), fillLevel=0, brush='r')
                percent_label.setText(f'{self.cpu_data[i][-1]:.1f}%')

        # Update GPU Plot
        if self.gpu_data:
            self.gpu_plot.clear()
            self.gpu_plot.plot(self.gpu_data, pen=pg.mkPen('g', width=2), fillLevel=0, brush='g')

        # Update Network Plots
        if self.net_sent_data:
            self.net_sent_plot.clear()
            self.net_sent_plot.plot(self.net_sent_data, pen=pg.mkPen('b', width=2), fillLevel=0, brush='b')
        if self.net_recv_data:
            self.net_recv_plot.clear()
            self.net_recv_plot.plot(self.net_recv_data, pen=pg.mkPen('c', width=2), fillLevel=0, brush='c')

        # Update Process List
        filtered_processes = self.filter_processes(processes)
        self.process_list.clear()
        for proc in filtered_processes:
            self.process_list.addItem(f'{proc.pid} - {proc.name} - CPU: {proc.cpu}% - Memory: {proc.mem:.2f} MB')

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
            selected_pid = int(selected_item.text().split(' - ')[0])
            try:
                proc = psutil.Process(selected_pid)
                proc.kill()
                print(f"Killed process with PID {selected_pid}")
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
