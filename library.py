from tkinter.tix import Tree
import PySimpleGUI as sg
import sqlite3 as sql
from io import BytesIO
from PIL import Image
from datetime import datetime

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

    book_info = dict(sorted(book_info.items(), key=lambda item: datetime.strptime(item[1]["info"]["chapters"][-1]["date"], "%b-%d-%Y"), reverse=True))

def make_window():
    global conn, cur, book_info
    update_book_info()
    thumbnail_urls = [book_info[k]["info"]["cover_url"] for k in book_info.keys()]
    #print(thumbnail_urls)
    thumbnails = mangakatana.download_images(thumbnail_urls)

    treedata = sg.TreeData()
    for i, (k, v) in enumerate(book_info.items()):
        #if search_query not in v["info"]["title"]: continue
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
    
    title_max_len = max([len(book_info[k]["info"]["title"]) for k in book_info.keys()]) #+ 20
    layout = [
        [
            sg.Menu([["Window", ["Refresh", "Close"]]], key="lib_menu")
        ],
        [sg.Input(key="lib_search_query", size=(title_max_len, 1)), sg.Button("⌕", key="lib_search", bind_return_key=True)],
        [
            TreeRtClick(
                data=treedata, headings=["Title", "Progress", "Last update"], col0_heading="",
                key="lib_tree", row_height=50, num_rows=5, enable_events=False,
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

def edit_chapter_progress(url):
    #update_book_info()
    max_ch = len(book_info[url]["info"]["chapters"])
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

def key_to_id(tree, key):
    for k, v in tree.IdToKey.items():
        if v == key: return k
    return None

original = []
removed = []

def get_original(tr: TreeRtClick):
    original.clear()
    for id, url in tr.IdToKey.items():
        if url == "": continue
        ix = tr.Widget.index(id)
        original.append((ix, id))
    
def clear_search(tr: TreeRtClick):
    for ix, id in original:
        tr.Widget.move(id, "", ix)

def search(query, tr: TreeRtClick):
    removed.clear()
    for id, url in tr.IdToKey.items():
        if url == "": continue
        if query not in book_info[url]["info"]["title"].lower():
            ix = tr.Widget.index(id)
            removed.append((ix, id))
    print(removed)

    for _, id in removed:
        tr.Widget.detach(id)