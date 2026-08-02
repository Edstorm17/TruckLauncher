import threading
from tkinter import *
from tkinter import ttk, messagebox

import config
import installer
import launcher
import util

root = None
dropdown = None

def begin():
    global root
    global dropdown
    root = Tk()
    root.title(config.LAUNCHER_NAME)
    frm = ttk.Frame(root, padding=20)
    frm.grid()
    ttk.Label(frm, text="TruckLauncher").grid(column=0, row=0, columnspan=2)
    selected_version = StringVar()
    dropdown = ttk.Combobox(frm, textvariable=selected_version)
    dropdown.grid(column=0, row=1, padx=5, pady=5)
    refresh_dropdown_values()
    dropdown.current(0)
    ttk.Button(frm, text="Play", command=lambda: handle_play_button(selected_version.get())).grid(column=0, row=2, padx=5, pady=5, columnspan=2)
    ttk.Button(frm, text="Quit", command=root.destroy).grid(column=0, row=3, padx=5, pady=5, columnspan=2)
    ttk.Button(frm, text="Add", command=create_add_window).grid(column=1, row=1, padx=5, pady=5)
    root.mainloop()

def refresh_dropdown_values():
    if dropdown:
        dropdown['values'] = [v['id'] for v in sorted(util.get_installed_versions(util.get_minecraft_path()), key=lambda v: v['release_time'], reverse=True)]

def handle_play_button(current_version: str):
    threading.Thread(target=install_and_launch, args=[current_version]).start()

def create_add_window():
    vanilla_versions = util.get_vanilla_versions_list()
    fabric_versions = util.get_fabric_versions_list()
    fabric_loaders = util.get_fabric_loader_list()

    add_window = Toplevel(root)
    add_window.title("Add Installation")
    tabs = ttk.Notebook(add_window)
    tab_vanilla = ttk.Frame(tabs, padding=20)
    tab_fabric = ttk.Frame(tabs, padding=20)
    tabs.add(tab_vanilla, text="Vanilla")
    tabs.add(tab_fabric, text="Fabric")
    tabs.pack(expand=True, fill="both")

    ttk.Label(tab_vanilla, text="Minecraft Version").grid(column=0, row=0, padx=5, pady=5)
    vanilla_selected_version = StringVar()
    vanilla_versions_dropdown = ttk.Combobox(tab_vanilla, textvariable=vanilla_selected_version)
    vanilla_versions_dropdown['values'] = [v["id"] for v in vanilla_versions]
    vanilla_versions_dropdown.grid(column=1, row=0, padx=5, pady=5)
    vanilla_versions_dropdown.current(0)
    ttk.Button(tab_vanilla, text="Install", command=lambda: handle_install_button_click(lambda: installer.install_vanilla_json(vanilla_selected_version.get()), add_window)).grid(column=0, row=1, padx=5, pady=5, columnspan=2)

    ttk.Label(tab_fabric, text="Minecraft Version").grid(column=0, row=0, padx=5, pady=5)
    fabric_selected_version = StringVar()
    fabric_versions_dropdown = ttk.Combobox(tab_fabric, textvariable=fabric_selected_version)
    fabric_versions_dropdown['values'] = [v["version"] for v in fabric_versions]
    fabric_versions_dropdown.grid(row=0, column=1, padx=5, pady=5)
    fabric_versions_dropdown.current(0)
    ttk.Label(tab_fabric, text="Loader Version").grid(column=0, row=1, padx=5, pady=5)
    fabric_selected_loader = StringVar()
    fabric_loaders_dropdown = ttk.Combobox(tab_fabric, textvariable=fabric_selected_loader)
    fabric_loaders_dropdown['values'] = [v["version"] for v in fabric_loaders]
    fabric_loaders_dropdown.grid(row=1, column=1, padx=5, pady=5)
    fabric_loaders_dropdown.current(0)
    (ttk.Button(tab_fabric, text="Install",
               command=lambda: handle_install_button_click(lambda: installer.install_fabric_json(fabric_selected_version.get(), fabric_selected_loader.get()), add_window))
     .grid(column=0, row=2, padx=5, pady=5, columnspan=2))

    add_window.mainloop()

def handle_install_button_click(command, frame):
    command()
    frame.destroy()
    refresh_dropdown_values()
    messagebox.showinfo("Success", "Installed successfully")

def install_and_launch(version: str):
    if config.USERNAME is None or config.UUID is None or config.TOKEN is None:
        return
    installer.install(version)
    launcher.launch(version, config.USERNAME, config.UUID, config.TOKEN)