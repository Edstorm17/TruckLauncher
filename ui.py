import threading
from tkinter import *
from tkinter import ttk, messagebox

import config
import installer
import launcher
import util

root = None
dropdown: ttk.Combobox | None = None

def begin():
    global root
    global dropdown

    def handle_play_button():
        profile = util.get_launch_profile_by_name(selected_profile.get())
        if profile is None:
            messagebox.showerror(title="Error", message="Launch profile not found")
            return
        threading.Thread(target=install_and_launch, args=[profile]).start()

    root = Tk()
    root.title(config.LAUNCHER_NAME)
    frm = ttk.Frame(root, padding=20)
    frm.grid()
    ttk.Label(frm, text="TruckLauncher").grid(column=0, row=0, columnspan=2)
    selected_profile = StringVar()
    dropdown = ttk.Combobox(frm, textvariable=selected_profile)
    dropdown.grid(column=0, row=1, padx=5, pady=5)
    refresh_dropdown_values()
    ttk.Button(frm, text="Play", command=handle_play_button).grid(column=0, row=2, padx=5, pady=5, columnspan=2)
    ttk.Button(frm, text="Quit", command=root.destroy).grid(column=0, row=3, padx=5, pady=5, columnspan=2)
    ttk.Button(frm, text="Add", command=create_add_window).grid(column=1, row=1, padx=5, pady=5)
    root.mainloop()

def refresh_dropdown_values():
    if dropdown:
        dropdown['values'] = [v['profile_name'] for v in sorted(util.get_launch_profiles(), key=lambda v: v['last_use_time'], reverse=True)]
        if len(dropdown['values']) > 0:
            dropdown.current(0)

def create_add_window():
    vanilla_versions = util.get_vanilla_versions_list()
    forge_versions = util.get_forge_versions()
    fabric_versions = util.get_fabric_versions_list()
    fabric_loaders = util.get_fabric_loader_list()

    add_window = Toplevel(root)
    add_window.title("Add Installation")
    ttk.Label(add_window, text="Profile name:").grid(column=0, row=0, padx=5, pady=5)
    name_entry = ttk.Entry(add_window, width=20)
    name_entry.grid(column=1, row=0, padx=5, pady=5)
    tabs = ttk.Notebook(add_window)
    tab_vanilla = ttk.Frame(tabs, padding=20, name="vanilla")
    tab_forge = ttk.Frame(tabs, padding=20, name="forge")
    tab_fabric = ttk.Frame(tabs, padding=20, name="fabric")
    tabs.add(tab_vanilla, text="Vanilla")
    tabs.add(tab_forge, text="Forge")
    tabs.add(tab_fabric, text="Fabric")
    tabs.grid(row=1, column=0, columnspan=2, padx=5, pady=5)

    ttk.Label(tab_vanilla, text="Minecraft Version").grid(column=0, row=0, padx=5, pady=5)
    vanilla_selected_version = StringVar()
    vanilla_versions_dropdown = ttk.Combobox(tab_vanilla, textvariable=vanilla_selected_version)
    vanilla_versions_dropdown['values'] = [v["id"] for v in vanilla_versions]
    vanilla_versions_dropdown.grid(column=1, row=0, padx=5, pady=5)
    vanilla_versions_dropdown.current(0)

    def update_forge_loaders_dropdown(_):
        forge_loaders_dropdown['values'] = util.sort_versions(forge_versions.get(forge_selected_version.get(), []))
        if len(forge_loaders_dropdown['values']) > 0:
            forge_loaders_dropdown.current(0)

    ttk.Label(tab_forge, text="Minecraft Version").grid(column=0, row=0, padx=5, pady=5)
    forge_selected_version = StringVar()
    forge_versions_dropdown = ttk.Combobox(tab_forge, textvariable=forge_selected_version)
    forge_versions_dropdown['values'] = util.sort_versions(list(forge_versions))
    forge_versions_dropdown.grid(column=1, row=0, padx=5, pady=5)
    forge_versions_dropdown.current(0)
    forge_versions_dropdown.bind("<<ComboboxSelected>>", update_forge_loaders_dropdown)
    ttk.Label(tab_forge, text="Loader Version").grid(column=0, row=1, padx=5, pady=5)
    forge_selected_loader = StringVar()
    forge_loaders_dropdown = ttk.Combobox(tab_forge, textvariable=forge_selected_loader)
    update_forge_loaders_dropdown(None)
    forge_loaders_dropdown.grid(column=1, row=1, padx=5, pady=5)
    forge_loaders_dropdown.current(0)

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

    def handle_install_button_click():
        nonlocal tab_vanilla
        nonlocal tab_fabric

        profile_name = name_entry.get()
        if not profile_name.strip():
            show_error_message("Please enter a valid profile name")
            return

        def handle_install_callback(version_id: str):
            if not util.add_launch_profile(profile_name, version_id):
                show_error_message("Profile with same name already exists")

        if tabs.select() == str(tab_vanilla):
            install_command = lambda: handle_install_callback(installer.install_vanilla_json(vanilla_selected_version.get()))
        elif tabs.select() == str(tab_fabric):
            install_command = lambda: handle_install_callback(installer.install_fabric_json(fabric_selected_version.get(), fabric_selected_loader.get()))
        elif tabs.select() == str(tab_forge):
            install_command = lambda: handle_install_callback(installer.install_forge_json(forge_selected_version.get(), forge_selected_loader.get()))
        else:
            raise Exception("Invalid mod loader")

        install_command()
        add_window.destroy()
        refresh_dropdown_values()
        show_success_message("Installed successfully")

    ttk.Button(add_window, text="Install", command=handle_install_button_click).grid(row=2, column=0, columnspan=2, padx=5, pady=5)
    add_window.mainloop()

def show_success_message(message: str):
    messagebox.showinfo("Success", message)

def show_error_message(message: str):
    messagebox.showerror("Error", message)

def install_and_launch(profile: dict):
    if config.USERNAME is None or config.UUID is None or config.TOKEN is None:
        return
    installer.install(profile["version_id"])
    launcher.launch(profile, config.USERNAME, config.UUID, config.TOKEN)