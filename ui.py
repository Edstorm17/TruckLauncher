import threading
from functools import partial
from tkinter import *
from tkinter import ttk, messagebox
from typing import TypedDict, Callable

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
    add_window = Toplevel(root)
    add_window.title("Add Installation")
    ttk.Label(add_window, text="Profile name:").grid(column=0, row=0, padx=5, pady=5)
    name_entry = ttk.Entry(add_window, width=20)
    name_entry.grid(column=1, row=0, padx=5, pady=5)
    tabs = ttk.Notebook(add_window)
    tabs.grid(row=1, column=0, columnspan=2, padx=5, pady=5)

    class LoaderTab(ttk.Frame):
        install_command: Callable[[], str]

    class TabField(TypedDict, total=False):
        name: str
        values: list
        selection_event: Callable[[Event, list[ttk.Combobox]], object] | None

    def add_tab(tab_name: str, fields: list[TabField], install_command: Callable[..., str]):
        tab = LoaderTab(tabs, padding=20)
        tabs.add(tab, text=tab_name)
        dropdowns: list[ttk.Combobox] = []
        for i in range(len(fields)):
            field = fields[i]
            ttk.Label(tab, text=field.get("name", "")).grid(column=0, row=i, padx=5, pady=5)
            values = field.get("values", [])
            field_dropdown = ttk.Combobox(tab, values=values)
            field_dropdown.grid(column=1, row=i, padx=5, pady=5)
            dropdowns.append(field_dropdown)
            if len(values) > 0:
                field_dropdown.current(0)
            if field.get("selection_event") is not None:
                field_dropdown.bind("<<ComboboxSelected>>", partial(lambda f, d, e: f.get("selection_event")(e, d), field, dropdowns))
        tab.install_command = lambda: install_command(*[d.get() for d in dropdowns])

    forge_versions = util.get_forge_versions()

    def update_forge_loaders_dropdown(_, dropdowns: list[ttk.Combobox]):
        dropdowns[1]['values'] = util.sort_versions(forge_versions.get(dropdowns[0].get(), []))
        if len(dropdowns[1]['values']) > 0:
            dropdowns[1].current(0)

    # noinspection PyTypeChecker
    add_tab("Vanilla", [{"name": "Minecraft Version", "values": [v["id"] for v in util.get_vanilla_versions_list()]}], installer.install_vanilla_json)
    forge_versions_list = util.sort_versions(list(forge_versions))
    # noinspection PyTypeChecker
    add_tab("Forge", [
        {"name": "Minecraft Version", "values": forge_versions_list, "selection_event": update_forge_loaders_dropdown},
        {"name": "Forge Version", "values": util.sort_versions(forge_versions.get(forge_versions_list[0], []))}
    ], installer.install_forge_json)
    # noinspection PyTypeChecker
    add_tab("Fabric", [
        {"name": "Minecraft Version", "values": [v["version"] for v in util.get_fabric_versions_list()]},
        {"name": "Loader Version", "values": [v["version"] for v in util.get_fabric_loader_list()]}
    ], installer.install_fabric_json)

    def handle_install_button_click():
        profile_name = name_entry.get()
        if not profile_name.strip():
            show_error_message("Please enter a valid profile name")
            return

        active_tab: LoaderTab = tabs.nametowidget(tabs.select())
        version_id = active_tab.install_command()
        if not util.add_launch_profile(profile_name, version_id):
            show_error_message("Profile with same name already exists")

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