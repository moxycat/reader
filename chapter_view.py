import PySimpleGUI as sg

def make_window():
    layout = [
        [
            sg.Column([
                [sg.Listbox([], key="details_chapters", size=(90, 15), enable_events=True, bind_return_key=True, change_submits=True)]
            ], key="details_chapters_col", justification="c", vertical_alignment="c")
        ],
    ]
    return sg.Window("", layout, element_justification="c", finalize=True, modal=True, disable_minimize=True)