import PySimpleGUI as sg
import library

def do():
    layout = [
        [sg.Text("Authenticate to access encrypted library.")],
        [sg.Text("Password"), sg.Input(password_char="*", focus=True, key="password", size=(30, 1))],
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
    w.close()
    return result

def login():
    layout = [
        [sg.Text("Username"), sg.Input(focus=True, key="username", size=(30, 1))],
        [sg.Text("Password"), sg.Input(password_char="*", key="password", size=(30, 1))],
        [sg.Text("", key="status", text_color="red")],
        [sg.Button("Login", bind_return_key=True, key="login"), sg.Button("Register", key="register")]
    ]
    wind = sg.Window("Login", layout)
    result = False
    while True:
        e, v = wind.read()
        if e == "login":
            username = v["username"]
            password = v["password"]
            if not library.login(username, password):
                wind["status"].update("Wrong credentials!")
                wind["password"].update("")
                continue
            result = True
            break
        if e == "register":
            username = v["username"]
            password = v["password"]
            if not library.register(username, password):
                wind["status"].update("An account with that name already exists!")
                wind["username"].update("")
                wind["password"].update("")
                continue
            result = True
            break
        if e == None: break
    
    wind.close()
    return result