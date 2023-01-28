import PySimpleGUI as sg
import library


def make_window():
    layout = [
        [sg.Text("New username:"), sg.Input("")],
        [sg.Text("Password:"), sg.Input("", password_char="*")]
    ]
    return sg.Window("Account settings", layout, finalize=True)