import PySimpleGUI as sg
import library


def make_window():
    layout = [
        [
            sg.Column([
                [sg.Text("Old password")],
                [sg.Text("New password")]
            ]),
            sg.Column([
                [sg.Input("", key="acs_old_password", size=(30, 1), password_char="*")],
                [sg.Input("", key="acs_new_password", size=(30, 1), password_char="*")]
            ])
        ],
        [
            sg.Button("Save", key="acs_save"), sg.Button("Delete account", button_color="red", key="acs_delete")
        ]
    ]
    return sg.Window("Account settings", layout, finalize=True)