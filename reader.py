import PySimpleGUI as sg

def reader_make_window():
    layout = [
        [
            sg.Menu([["&Tools", ["&Save screenshot", "&Maximize window", "&Exit"]]], key="reader_menu")
        ],
        [
            [
                sg.Column([
                    [sg.Image(key="reader_page_img", enable_events=True, pad=0)]
                ], size=(800, 600), scrollable=True, key="reader_page_img_col"
                #, justification="c", vertical_alignment="c", element_justification="c"
                )
            ],
            [sg.HSeparator()],
            [            
                sg.Button("prev ch.", key="reader_go_prev_ch"),
                sg.Button("≪", key="reader_go_home"),
                sg.Text(), sg.Text(),
                sg.Button("<", key="reader_go_back"),
                sg.Text("01/??", key="reader_page_num", enable_events=True),
                sg.Button(">", key="reader_go_fwd"),
                sg.Text(), sg.Text(),
                sg.Button("≫", key="reader_go_end"),
                sg.Button("next ch.", key="reader_go_next_ch")
            ]
        ]
    ]

    wind = sg.Window("Reader", layout=layout, element_justification="c", finalize=True, resizable=True)
    wind.bind("<Shift-Right>", "reader_go_fwd")
    wind.bind("<Shift-Left>", "reader_go_back")
    wind.bind("<Right>", "reader_scroll_right")
    wind.bind("<Left>", "reader_scroll_left")
    wind.bind("<Down>", "reader_scroll_down")
    wind.bind("<Up>", "reader_scroll_up")
    wind.bind("<Configure>", "reader_resized")
    return wind
    
def jump(max_page: int):
    layout = [
        [sg.Input(key="npage", size=(10, 1))],
        [sg.Button("Jump", key="jump"), sg.Button("Cancel", key="cancel")]
    ]
    w = sg.Window("Jump to page", layout, element_justification="c", modal=True)
    val = None
    while True:
        e, v = w.read()
        if e == "cancel" or e == sg.WIN_CLOSED: break
        if e == "jump":
            val = v["npage"]
            try:
                val = int(val)
            except:
                w["npage"].update("")
                continue
            #print(type(val), type(max_page))
            if val <= max_page and val >= 1: break
    w.close()
    return val