import PySimpleGUI as sg
import sqlite3 as sql
from io import BytesIO
from PIL import Image

import mangakatana

conn = None
cur = None
book_info = {}

# modded Tree class where right clicking on an element selects it before opening the right click menu
class TreeRtClick(sg.Tree):
    def _RightClickMenuCallback(self, event):
        tree = self.Widget
        item = tree.identify_row(event.y)
        tree.selection_set(item)
        super()._RightClickMenuCallback(event)

def init_db():
    global conn, cur
    conn = sql.connect("a.db", check_same_thread=False)
    cur = conn.cursor()
    return (conn, cur)

def add(url, ch=0, p=0):
    global conn, cur
    cur.execute("INSERT INTO reading_list VALUES(?, ?, ?);", (url, ch, p))
    conn.commit()

def update(url, ch, p):
    global conn, cur
    cur.execute("UPDATE reading_list SET chapter = ?, page = ? WHERE url = ?", (ch, p, url))
    conn.commit()

def is_in_lib(url):
    global conn, cur
    cur.execute("SELECT * FROM reading_list WHERE url=?", (url,))
    rows = cur.fetchall()
    return (len(rows) > 0, rows[0] if len(rows) > 0 else None)

def update_book_info():
    global conn, cur, book_info
    cur.execute("SELECT * FROM reading_list;")
    rows = cur.fetchall()
    book_info.clear()
    for row in rows:
        info = mangakatana.get_manga_info(row[0])
        book_info.setdefault(row[0], {"ch": row[1], "p": row[2], "info": info})

def make_window_layout():
    global conn, cur, book_info
    #init_db()
    update_book_info()
    thumbnail_urls = [book_info[k]["info"]["cover_url"] for k in book_info.keys()]
    print(thumbnail_urls)
    thumbnails = mangakatana.download_images(thumbnail_urls)

    treedata = sg.TreeData()
    for i, (k, v) in enumerate(book_info.items()):
        buf = BytesIO(thumbnails[i])
        outbuf = BytesIO()
        im = Image.open(buf)
        im.thumbnail((50, 50), resample=Image.BICUBIC)
        im.save(outbuf, "png")
        treedata.insert("", k,
            "",
            [v["info"]["title"], "{}/{}".format(str(int(v["ch"]) + 1).zfill(2), "??" if v["info"]["status"] == "Ongoing" else str(len(v["info"]["chapters"])).zfill(2)), v["info"]["chapters"][-1]["date"]],
            outbuf.getvalue()
            )
        buf.close()
        outbuf.close()
    
    title_max_len = max([len(book_info[k]["info"]["title"]) for k in book_info.keys()]) + 20
    col0_width = 50
    layout = [
        [
            sg.Menu([["Window", ["Refresh", "Close"]]], key="lib_menu")
        ],
        [
            TreeRtClick(
                data=treedata, headings=["Title", "Progress", "Last update"], col0_heading="",
                key="lib_tree", row_height=50, num_rows=5, enable_events=True,
                max_col_width=title_max_len, justification="l",
                right_click_menu=["", ["Edit chapter", "Remove from list"]]
            )
        ]
    ]
    
    return layout

def start_reading(title):
    layout = [
        [sg.Text("Would you like to add {} to your reading list?".format(title))],
        [sg.Button("Yes", key="reading_start_yes"), sg.Button("No", key="reading_start_no")]
    ]
    w = sg.Window("", layout, modal=True, finalize=True, disable_minimize=True, disable_close=True)
    ans = False
    e, v = w.read()
    if e == "reading_start_yes": ans = True
    w.close()
    return ans

def edit_chapter_progress(url, max_ch):
    #init_db()
    update_book_info()
    layout = [
        [sg.Button("-", key="lib_edit_minus"), sg.Input(int(book_info[url]["ch"]) + 1, key="lib_edit_progress_chapter", size=(len(str(max_ch)), 1)), sg.Text("/", pad=0), sg.Input(max_ch, disabled=True, background_color="white", size=(len(str(max_ch)), 1)), sg.Button("+", key="lib_edit_plus")],
        [sg.Button("Save", key="lib_edit_save"), sg.Button("Cancel", key="lib_edit_cancel")]
    ]
    w = sg.Window("Edit", layout, finalize=True, modal=True, disable_minimize=True, element_justification="c")
    while True:
        e, v = w.read()
        print(e)
        if e == "lib_edit_cancel" or e == sg.WIN_CLOSED:
            break
        if e == "lib_edit_plus":
            val = v["lib_edit_progress_chapter"]
            try:
                val = int(val)
            except:
                w["lib_edit_progress_chapter"].update("")
                continue
            if val + 1 <= int(max_ch): w["lib_edit_progress_chapter"].update(val + 1)
        
        if e == "lib_edit_minus":
            val = v["lib_edit_progress_chapter"]
            try:
                val = int(val)
            except:
                w["lib_edit_progress_chapter"].update("")
                continue
            if val - 1 >= 1: w["lib_edit_progress_chapter"].update(val - 1)

        if e == "lib_edit_save":
            val = v["lib_edit_progress_chapter"]
            try:
                val = int(val)
            except:
                w["lib_edit_progress_chapter"].update("")
                continue
            if val > 0 and val <= int(max_ch):
                update(url, val - 1, 0)
            break
    w.close()