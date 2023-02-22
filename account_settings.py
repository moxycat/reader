import PySimpleGUI as sg
import library


def make_window():
    layout = [
        [
            sg.Column([
                [sg.Text("Username")],
                [sg.Text("Password")]
            ]),
            sg.Column([
                [sg.Input("", key="username")],
                [sg.Input("", key="password")]
            ])
        ]
    ]
    return sg.Window("Account settings", layout, finalize=True)