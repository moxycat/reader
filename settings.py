import PySimpleGUI as sg
import json

settings = {}

def read_settings():
    global settings
    with open("settings.json", "r") as f:
        settings = json.loads(f.read())

def make_window():
    global settings
    read_settings()
    layout = [
        [sg.Frame("UI", [
            [sg.Text("Theme"), sg.Combo(["Light", "Dark"], default_value=settings["ui"]["theme"], key="settings_ui_theme", readonly=True, background_color="white")]
        ]
        )],
        [
            sg.Frame("Reader", [
                [sg.Column([
                    [sg.Text("Window width")],
                    [sg.Text("Window height")],
                    [sg.Text("Blue light filter intensity", tooltip="Set to 0 to disable")]
                ]), sg.Column([
                    [sg.Input(key="settings_reader_width", default_text=settings["reader"]["w"], size=(4, 1))],
                    [sg.Input(key="settings_reader_height", default_text=settings["reader"]["h"], size=(4, 1))],
                    [sg.Input(key="settings_bluefilter_perc", default_text=settings["reader"]["filter"], size=(3, 1)), sg.Text("%", pad=0)],
                ])]
            ])
        ],
        [
            sg.Frame("Server", [
                [sg.Text("Image source"), sg.Combo(["1", "2", "3"], settings["server"]["source"], key="settings_server_source", readonly=True, background_color="white")]
            ])
        ],
        [
            sg.Frame("Storage", [
                [sg.Text("Path to database"), sg.Input(key="settings_storage_db_path", default_text=settings["storage"]["path"], size=(20, 1)), sg.FileBrowse("📁", file_types=(("SQLite3 file", "*.* *"),))],
                [sg.Button("Create new"), sg.Button("Delete contents", tooltip="This will delete all user data from the currently selected database file!")],
                [sg.Checkbox("Refresh book info on start", key="settings_storage_refresh", default=settings["storage"]["refresh"])]
            ])
        ],
        [sg.Button("Save settings", key="settings_save", tooltip="New settings are applied on restart"), sg.Button("Cancel", key="settings_cancel")]
    ]

    wind = sg.Window("Settings", layout, disable_minimize=True, modal=True, finalize=True)
    wind.TKroot.resizable(0, 0)
    return wind