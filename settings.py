from email.policy import default
import PySimpleGUI as sg
import json

__settings = {}

def read_settings():
    global __settings
    with open("settings.json", "r") as f:
        __settings = json.loads(f.read())

def make_window():
    global __settings
    read_settings()
    layout = [
        [sg.Frame("UI", [
            [sg.Text("Theme"), sg.Combo(["Light", "Dark"], default_value="Light" if __settings["ui"]["theme"] == "light" else "Dark", key="settings_ui_theme", readonly=True, background_color="white")]
        ]
        )],
        [
            sg.Frame("Reader", [
                [sg.Column([
                    [sg.Text("Window width")],
                    [sg.Text("Window height")]
                ]), sg.Column([
                    [sg.Input(key="settings_reader_width", default_text=__settings["reader"]["w"], size=(4, 1))],
                    [sg.Input(key="settings_reader_height", default_text=__settings["reader"]["h"], size=(4, 1))]
                ])],
                [sg.Checkbox("Auto-update chapter progress", default=True, key="settings_reader_autoupdate")]
            ])
        ],
        [
            sg.Frame("Server", [
                [sg.Text("Image source"), sg.Combo(["mangakatana.com"], __settings["server"]["source"], key="settings_server_source", readonly=True, background_color="white")]
            ])
        ],
        [sg.Button("Save settings", key="settings_save"), sg.Button("Cancel", key="settings_cancel")]
    ]

    wind = sg.Window("Settings", layout, disable_minimize=True, modal=True, finalize=True)
    wind.TKroot.resizable(0, 0)
    return wind