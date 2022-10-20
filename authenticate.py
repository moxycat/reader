import PySimpleGUI as sg
import library

def do():
    layout = [
        [sg.Text("Authenticate to access encrypted library.")],
        [sg.Text("Password"), sg.Input(password_char="*", focus=True, key="password")],
        [sg.Text("", key="status", text_color="red")],
        [sg.Button("Submit", bind_return_key=True, key="submit"), sg.Button("Exit", key="exit")]
    ]
    w = sg.Window("Authenticate", layout)
    result = False
    while True:
        e, v = w.read()
        if e == "submit":
            if library.init_db(v["password"]):
                result = True
                break
            else: 
                w["status"].update("Wrong password!")
                w["password"].update("")
        if e == None or e == "exit":
            break
    return result