from select import select
import PySimpleGUI as sg

def RightClickMenuCallback(event, element):
    widget = element.Widget
    current = widget.curselection()
    if current:
        widget.selection_clear(current[0])
    index = widget.nearest(event.y)
    widget.selection_set(index)
    element.TKRightClickMenu.tk_popup(event.x_root, event.y_root, 0)
    element.TKRightClickMenu.grab_release()

def make_window():
    layout = [
        [sg.Listbox([], key="details_chapters", size=(90, 15), enable_events=True, bind_return_key=True, change_submits=True, right_click_menu=["", ["!Mark as read", "---", "!Download", "!Delete"]], select_mode=sg.LISTBOX_SELECT_MODE_EXTENDED)]
    ]
    w = sg.Window("", layout, element_justification="c", finalize=True, modal=True, disable_minimize=True)
    w["details_chapters"].Widget.bind("<Button-3>", lambda event, element=w["details_chapters"]: RightClickMenuCallback(event, element))
    return w