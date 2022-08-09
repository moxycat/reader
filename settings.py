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
                    [sg.Text("Window height")]
                ]), sg.Column([
                    [sg.Input(key="settings_reader_width", default_text=settings["reader"]["w"], size=(4, 1))],
                    [sg.Input(key="settings_reader_height", default_text=settings["reader"]["h"], size=(4, 1))]
                ])],
                [sg.Checkbox("Auto-update chapter progress", default=True, key="settings_reader_autoupdate")]
            ])
        ],
        [
            sg.Frame("Server", [
                [sg.Text("Image source"), sg.Combo(["1", "2", "3"], settings["server"]["source"], key="settings_server_source", readonly=True, background_color="white")]
            ])
        ],
        [
            sg.Frame("MAL Sync", [
                [sg.Text("Status: disabled"), sg.Button("Authorize account", key="settings_mal_auth", disabled=True)]
            ])
        ],
        [sg.Button("Save settings", key="settings_save", tooltip="New settings are applied on restart"), sg.Button("Cancel", key="settings_cancel")]
    ]

    wind = sg.Window("Settings", layout, disable_minimize=True, modal=True, finalize=True)
    wind.TKroot.resizable(0, 0)
    return wind
