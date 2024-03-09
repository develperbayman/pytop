import tkinter as tk
from tkinter import ttk, Menu, Scale, IntVar
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import psutil
import threading
import time

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
            processes.append(ProcessInfo(proc.info['pid'], proc.info['name'], proc.info['cpu_percent'],
                                         proc.info['memory_percent']))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title('pytop')

        # Variables
        self.update_speed_var = IntVar()
        self.update_speed_var.set(1)  # Default update speed is 1 second

        self.init_ui()

    def init_ui(self):
        # Dark theme
        self.root.configure(bg='#1C1C1C')

        # Menu Bar
        menu_bar = Menu(self.root)
        self.root.config(menu=menu_bar)

        options_menu = Menu(menu_bar, tearoff=0)
        options_menu.add_command(label="Update Speed", command=self.show_update_speed_dialog)
        menu_bar.add_cascade(label="Options", menu=options_menu)

        # Running Processes Label
        title_label = tk.Label(self.root, text='Running Processes', font=('Helvetica', 16), bg='#1C1C1C', fg='white')
        title_label.pack(pady=10)

        # Frame for Process List
        list_frame = tk.Frame(self.root, bg='#1C1C1C')
        list_frame.pack(expand=True, fill='both', padx=10)

        # Process List with Scrollbar
        self.process_list = tk.Listbox(list_frame, font=('Courier', 12), bg='#1C1C1C', fg='white', selectbackground='blue')
        self.process_list.pack(side='left', fill='both', expand=True)

        scrollbar = tk.Scrollbar(list_frame, command=self.process_list.yview)
        scrollbar.pack(side='right', fill='y')
        self.process_list.config(yscrollcommand=scrollbar.set)

        # Resizable Separator
        separator1 = ttk.Separator(self.root, orient='horizontal')
        separator1.pack(fill='x', pady=10)

        # CPU and Memory Plots
        self.fig, (self.cpu_ax, self.mem_ax) = plt.subplots(2, 1, figsize=(5, 6), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(expand=True, fill='both', padx=10)

        # Data collection thread
        self.update_thread = threading.Thread(target=self.update_data)
        self.update_thread.start()

        # Timer for GUI updates
        self.root.after(1000, self.update_plots)

        # Context Menu
        self.context_menu = Menu(self.process_list, tearoff=0)
        self.context_menu.add_command(label="Kill Process", command=self.kill_process)
        self.process_list.bind("<Button-3>", self.show_context_menu)

    def update_data(self):
        while True:
            update_processes()
            time.sleep(1)  # Update every 1 second

    def update_plots(self):
        cpu_data = [proc.cpu for proc in processes]
        mem_data = [proc.mem for proc in processes]

        # Update CPU and Memory Plots with a little space between them
        self.cpu_ax.clear()
        self.cpu_ax.plot(cpu_data, 'r-')
        self.cpu_ax.set_title('CPU Usage')
        self.cpu_ax.set_xlabel('Time')
        self.cpu_ax.set_ylabel('Usage (%)')

        self.mem_ax.clear()
        self.mem_ax.plot(mem_data, 'b-')
        self.mem_ax.set_title('Memory Usage')
        self.mem_ax.set_xlabel('Time')
        self.mem_ax.set_ylabel('Usage (%)')

        # Adjust layout to add space between the plots
        self.fig.subplots_adjust(hspace=0.5)

        self.canvas.draw()

        # Update Process List
        self.process_list.delete(0, 'end')
        for proc in processes:
            self.process_list.insert('end', f'{proc.pid} - {proc.name} - CPU: {proc.cpu}% - Memory: {proc.mem}%')

        # Schedule the next update
        self.root.after(1000, self.update_plots)

    def show_context_menu(self, event):
        self.context_menu.post(event.x_root, event.y_root)

    def kill_process(self):
        selected_index = self.process_list.curselection()
        if selected_index:
            selected_proc = processes[selected_index[0]]
            # Implement the process killing logic here
            print(f"Killing process with PID {selected_proc.pid}")

    def show_update_speed_dialog(self):
        update_speed_dialog = tk.Toplevel(self.root)
        update_speed_dialog.title("Update Speed")

        scale_label = tk.Label(update_speed_dialog, text="Select Update Speed (seconds):", pady=10, bg='#1C1C1C', fg='white')
        scale_label.pack()

        update_speed_scale = Scale(update_speed_dialog, from_=1, to=10, orient=tk.HORIZONTAL, variable=self.update_speed_var,
                                   bg='#1C1C1C', fg='white', sliderlength=15, length=200)
        update_speed_scale.set(self.update_speed_var.get())
        update_speed_scale.pack(pady=10)

        ok_button = tk.Button(update_speed_dialog, text="OK", command=self.apply_update_speed)
        ok_button.pack(pady=10)

    def apply_update_speed(self):
        new_speed = self.update_speed_var.get()
        print(f"Update speed changed to {new_speed} seconds")
        # Update the sleep duration in the data collection thread
        self.update_thread.join()
        self.update_thread = threading.Thread(target=self.update_data)
        self.update_thread.start()

if __name__ == '__main__':
    processes = []  # Initialize the global processes list

    root = tk.Tk()
    app = MainApp(root)
    root.mainloop()
