import textwrap
import PySimpleGUI as sg
import sqlite3 as sql
from io import BytesIO
from PIL import Image
from datetime import datetime
import requests

import mangakatana, settings

conn = None
cur = None
book_info = {}

# no enums in python ;w;

class BookStatus():
    READING = 1
    COMPLETED = 2
    ON_HOLD = 3
    DROPPED = 4
    PLAN_TO_READ = 5

# modded Tree class where right clicking on an element selects it before opening the right click menu
class TreeRtClick(sg.Tree):
    def _RightClickMenuCallback(self, event):
        tree = self.Widget
        item = tree.identify_row(event.y)
        tree.selection_set(item)
        super()._RightClickMenuCallback(event)

def init_db():
    global conn, cur
    conn = sql.connect(settings.settings["storage"]["path"], check_same_thread=False)
    cur = conn.cursor()
    return (conn, cur)

def add(url, ch=0, p=0):
    global conn, cur
    cur.execute("INSERT INTO reading_list VALUES(?, ?, ?);", (url, ch, p))
    conn.commit()

def add(url, ch=0, vol=0, sd="unknown", ed="unknown", score="0", /, list=BookStatus.PLAN_TO_READ):
    query = "INSERT INTO {} VALUES(?, ?, ?, ?, ?, ?);"
    if list == BookStatus.READING: query.format("books_cr")
    elif list == BookStatus.COMPLETED: query.format("books_cpml")
    elif list == BookStatus.ON_HOLD: query.format("books_idle")
    elif list == BookStatus.DROPPED: query.format("books_drop")
    elif list == BookStatus.PLAN_TO_READ: query.format("books_ptr")
    cur.execute(query, (url, ch, vol, sd, ed, score))
    conn.commit()

def update(url, ch, p):
    global conn, cur
    cur.execute("UPDATE reading_list SET chapter = ?, page = ? WHERE url = ?", (ch, p, url))
    conn.commit()

def delete(url):
    global conn, cur
    cur.execute("DELETE FROM reading_list WHERE url = ?", (url, ))
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

    book_info = dict(sorted(book_info.items(), key=lambda item: item[1]["info"]["chapters"][-1]["date"], reverse=True))

def make_window():
    global conn, cur, book_info
    update_book_info()
    thumbnail_urls = [book_info[k]["info"]["cover_url"] for k in book_info.keys()]
    #print(thumbnail_urls)
    try:
        requests.get(thumbnail_urls[0])
        itworks = True
    except:
        thumbnails = [None] * len(thumbnail_urls)
        itworks = False
    
    if itworks: thumbnails = mangakatana.download_images(thumbnail_urls)

    treedata = sg.TreeData()
    for i, (k, v) in enumerate(book_info.items()):
        #if search_query not in v["info"]["title"]: continue
        if thumbnails[i] is not None:
            buf = BytesIO(thumbnails[i])
            im = Image.open(buf)
        else:
            im = Image.open("default_cover.png")
        outbuf = BytesIO()
        
        im.thumbnail((30, 30), resample=Image.BICUBIC)
        im.save(outbuf, "png")
        treedata.insert("", k,
            "",
            [
                textwrap.shorten(v["info"]["title"], width=50, placeholder="..."),
                "{}/{}".format(
                    str(int(v["ch"]) + 1).zfill(2),
                    str(len(v["info"]["chapters"])).zfill(2) if v["info"]["status"] == "Completed" else "[" + str(len(v["info"]["chapters"])).zfill(2) + "]"
                ), datetime.strftime(v["info"]["chapters"][-1]["date"], "%b-%d-%Y")],
            outbuf.getvalue(),
            )
    title_max_len = 50
    tab_cr = [
        [
            TreeRtClick(
                data=treedata, headings=["Title", "Progress", "Last update"], col0_heading="Image",
                key="lib_tree", row_height=30, num_rows=5, enable_events=False,
                max_col_width=title_max_len, justification="l",
                right_click_menu=["", ["Edit chapter", "Remove from list", "Move to", ["Completed", "Idle", "Dropped", "Plan to read"]]]
            )
        ]
    ]
    tab_ptr = [
        [
            TreeRtClick(
                data=treedata, headings=["Title", "Progress", "Last update"], col0_heading="",
                key="lib_tree", row_height=30, num_rows=5, enable_events=False,
                max_col_width=title_max_len, justification="l",
                right_click_menu=["", ["Edit chapter", "Remove from list", "Move to", ["Reading", "Completed", "Idle", "Dropped"]]]
            )
        ]
    ]
    tab_cmpl = []
    tab_drop = []
    tab_idle = []

    #title_max_len = max([len(book_info[k]["info"]["title"]) for k in book_info.keys()]) // 2 #+ 20
    
    layout = [
        [
            sg.Menu([["Window", ["Refresh", "Close"]]], key="lib_menu")
        ],
        [
            sg.Column(
                [
                    [sg.Input(key="lib_search_query", size=(title_max_len, 1)), sg.Button("⌕", key="lib_search", bind_return_key=True)]
                ], element_justification="l", vertical_alignment="l", justification="l")
        ],
        [
            TreeRtClick(
                data=treedata, headings=["Title", "Progress", "Last update"], col0_heading="",
                key="lib_tree", row_height=30, num_rows=5, enable_events=False,
                max_col_width=title_max_len, justification="l",
                right_click_menu=["", ["Edit chapter", "Remove from list", "Move to", ["A", "B"]]]
            )
        ],
        [sg.Text("Note the number of chapters here will likely differ to the official count.")]
    ]
    return layout

def start_reading():
    layout = [
        [sg.Text("Would you like to add this book to your reading list?")],
        [sg.Button("Yes", key="reading_start_yes"), sg.Button("No", key="reading_start_no")]
    ]
    w = sg.Window("", layout, modal=True, finalize=True, disable_minimize=True, disable_close=True, element_justification="c")
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