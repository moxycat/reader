import textwrap
import PySimpleGUI as sg
import sqlite3 as sql
from io import BytesIO
from PIL import Image
from datetime import datetime
import requests
import re

import mangakatana, settings

conn = None
cur = None
book_info = {}
thumbnails = []
td_rows = []

tables = ["books_cr", "books_cmpl", "books_idle", "books_drop", "books_ptr"]

class BookStatus():
    READING = 0
    COMPLETED = 1
    ON_HOLD = 2
    DROPPED = 3
    PLAN_TO_READ = 4

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

def add(url, ch=0, vol=0, sd="unknown", ed="unknown", score="0", /, where=BookStatus.PLAN_TO_READ, last_update=None):
    if last_update is None:
        last_update = datetime.strftime(datetime.now(), "%b-%d-%Y %H:%M:%S")
    query = "INSERT INTO {} VALUES(?, ?, ?, ?, ?, ?, ?);".format(tables[where])
    print(query)
    cur.execute(query, (url, ch, vol, sd, ed, score, last_update))
    conn.commit()

def update(url, ch=None, vol=None, sd=None, ed=None, score=None, last_update=None):
    if last_update is None:
        last_update = datetime.strftime(datetime.now(), "%b-%d-%Y %H:%M:%S")
    _, _, ix = is_in_lib(url)
    table = tables[ix]
    query = "UPDATE {} SET ".format(table)
    args = [(ch, "chapter"), (vol, "volume"), (sd, "start_date"), (ed, "end_date"), (score, "score"), (last_update, "last_update")]
    for arg in args:
        if arg[0] is not None: query += arg[1] + "=?,"
    if query[-1] == ",": query = query.removesuffix(",")
    query += " WHERE url = \"{}\";".format(url)
    print(query)
    tup = tuple(filter(lambda x: x is not None, [x[0] for x in args]))
    cur.execute(query, tup)
    conn.commit()

def delete(url, /, where=None):
    if where is None:
        _, _, ix = is_in_lib(url)
    else: ix = where
    query = "DELETE FROM {} WHERE url = ?".format(tables[ix])
    print(query)
    cur.execute(query, (url, ))
    conn.commit()

def move(url, /, src, dest):
    if src == dest: return
    query = "SELECT * FROM {} WHERE url = ?".format(tables[src])
    print(query)
    cur.execute(query, (url,))
    rows = cur.fetchall()
    print(rows)
    if len(rows) > 1: return
    row = rows[0]
    add(row[0], row[1], row[2], row[3], row[4], row[5], where=dest)
    delete(row[0], where=src)

def is_in_lib(url):
    query = "SELECT * FROM {} WHERE url=?"
    for i, _ in enumerate(tables):
        cur.execute(query.format(tables[i]), (url,))
        rows = cur.fetchall()
        if len(rows) > 0: return (True, rows[0], i)
    return (False, None, None)

def update_book_info():
    global book_info
    book_info.clear()
    
    for x in tables:
        cur.execute("SELECT * FROM {};".format(x))
        rows = cur.fetchall()
        for row in rows:
            info = mangakatana.get_manga_info(row[0])
            book_info.setdefault(row[0], {"ch": row[1], "vol": row[2], "start_date": row[3], "end_date": row[4], "score": row[5], "info": info, "last_update": row[6], "list": x})

    book_info = dict(sorted(book_info.items(), key=lambda item: item[1]["info"]["chapters"][-1]["date"], reverse=True))

def download_thumbnails():
    global thumbnails
    thumbnail_urls = [book_info[k]["info"]["cover_url"] for k in book_info.keys()]
    try:
        requests.get(thumbnail_urls[0])
        itworks = True
    except:
        thumbnails = [None] * len(thumbnail_urls)
        itworks = False
    
    if itworks: thumbnails = mangakatana.download_images(thumbnail_urls)

def make_treedata(refresh=False):
    global thumbnails
    update_book_info()
    td = sg.TreeData()
    tds = [sg.TreeData(), sg.TreeData(), sg.TreeData(), sg.TreeData(), sg.TreeData()]

    if not refresh: download_thumbnails()

    for i, (k, v) in enumerate(book_info.items()):
        if thumbnails[i] is not None:
            buf = BytesIO(thumbnails[i])
            im = Image.open(buf)
        else:
            im = Image.open("default_cover.png")
        outbuf = BytesIO()
        
        im.thumbnail((30, 30), resample=Image.BICUBIC)
        im.save(outbuf, "png")
        ix = tables.index(v["list"])
        
        tds[ix].insert("", k,
            "",
            [
                # name
                textwrap.shorten(v["info"]["title"], width=50, placeholder="..."),
                #score
                v["score"],
                # chapter
                "{}/{}".format(
                    str(int(v["ch"]) + 1).zfill(2),
                    str(len(v["info"]["chapters"])).zfill(2) if v["info"]["status"] == "Completed" else "[" + str(len(v["info"]["chapters"])).zfill(2) + "]"
                ),
                # volumes read
                v["vol"],
                
                str((datetime.now() - v["info"]["chapters"][-1]["date"]).days) + " days ago"  
            ],
            # thumbnail
            outbuf.getvalue(),
            )
    
    return tds

def make_window():
    global thumbnails
    update_book_info()
    
    tds = make_treedata()

    title_max_len = 50

    tab_cr_layout = [
        [
            TreeRtClick(
                data=tds[0], headings=["Title", "Score", "Chapters", "Volumes", "Last update"], col0_heading="",
                key="lib_tree_cr", row_height=30, num_rows=5, enable_events=False,
                max_col_width=title_max_len, justification="l",
                right_click_menu=["", ["Show in search", "View chapters", "Edit", "Remove", "Move to", ["Completed", "On-hold", "Dropped", "Plan to read"]]],
                expand_x=True
            )
        ]
    ]
    tab_cmpl_layout = [
        [
            TreeRtClick(
                data=tds[1], headings=["Title", "Score", "Chapters", "Volumes", "Last update"], col0_heading="",
                key="lib_tree_cmpl", row_height=30, num_rows=5, enable_events=False,
                max_col_width=title_max_len, justification="l",
                right_click_menu=["", ["Show in search", "View chapters", "Edit", "Remove", "Move to", ["Reading", "On-hold", "Dropped", "Plan to read"]]],
                expand_x=True
            )
        ]
    ]
    tab_idle_layout = [
        [
            TreeRtClick(
                data=tds[2], headings=["Title", "Score", "Chapters", "Volumes", "Last update"], col0_heading="",
                key="lib_tree_idle", row_height=30, num_rows=5, enable_events=False,
                max_col_width=title_max_len, justification="l",
                right_click_menu=["", ["Show in search", "View chapters", "Edit", "Remove", "Move to", ["Reading", "Completed", "Dropped", "Plan to read"]]],
                expand_x=True            
            )
        ]
    ]
    tab_drop_layout = [
        [
            TreeRtClick(
                data=tds[3], headings=["Title", "Score", "Chapters", "Volumes", "Last update"], col0_heading="",
                key="lib_tree_drop", row_height=30, num_rows=5, enable_events=False,
                max_col_width=title_max_len, justification="l",
                right_click_menu=["", ["Show in search", "View chapters", "Edit", "Remove", "Move to", ["Reading", "Completed", "On-hold", "Plan to read"]]],
                expand_x=True
            )
        ]
    ]
    tab_ptr_layout = [
        [
            TreeRtClick(
                data=tds[4], headings=["Title", "Score", "Chapters", "Volumes", "Last update"], col0_heading="",
                key="lib_tree_ptr", row_height=30, num_rows=5, enable_events=True,
                max_col_width=title_max_len, justification="l",
                right_click_menu=["", ["Show in search", "View chapters", "Edit", "Remove", "Move to", ["Reading", "Completed", "On-hold", "Dropped"]]],
                expand_x=True
            )
        ]
    ]

    layout = [
        [
            sg.Menu([["Window", ["Refresh", "Close"]]], key="lib_menu")
        ],
        [
            sg.Input(key="lib_search_query", expand_x=True), sg.Button("⌕", key="lib_search", bind_return_key=True)
        ],
        [
            sg.TabGroup([
                [
                    sg.Tab("Reading", tab_cr_layout, key="tab_reading"),
                    sg.Tab("Completed", tab_cmpl_layout, key="tab_completed"),
                    sg.Tab("On-hold", tab_idle_layout, key="tab_onhold"),
                    sg.Tab("Dropped", tab_drop_layout, key="tab_dropped"),
                    sg.Tab("Plan to read", tab_ptr_layout, key="tab_ptr")
                ]
            ], tab_location="topleft", enable_events=True, key="tab_group")
        ]
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
    max_ch = len(book_info[url]["info"]["chapters"])
    layout = [
        [
            sg.Column([
                [sg.Text("Chapters read")],
                [sg.Text("Volumes read")],
                [sg.Text("Score")],
                [sg.Text("Start date")],
                [sg.Text("End date")]
            ]),
            sg.Column([
                [sg.Button("-", key="lib_edit_minus"), sg.Input(int(book_info[url]["ch"]) + 1, key="lib_edit_progress_chapter", size=(len(str(max_ch)), 1)), sg.Text("/", pad=0), sg.Input(max_ch, disabled=True, background_color="white", size=(len(str(max_ch)), 1)), sg.Button("+", key="lib_edit_plus")],
                [sg.Input(book_info[url]["vol"], key="lib_edit_progress_volume", size=(5, 1))],
                [sg.Combo(["-"] + [x for x in range(1, 11)], book_info[url]["score"] if book_info[url]["score"] != "0" else "-", key="lib_edit_score", size=(3, 1))],
                [sg.Input("unknown", readonly=True, key="lib_edit_start_date", size=(11, 1), disabled_readonly_background_color="white"), sg.Button("Today", key="lib_edit_sd_today"), sg.Button("Pick", key="lib_edit_sd_pick")],
                [sg.Input("unknown", readonly=True, key="lib_edit_end_date", size=(11, 1), disabled_readonly_background_color="white"), sg.Button("Today", key="lib_edit_ed_today"), sg.Button("Pick", key="lib_edit_ed_pick")]
            ])
        ],
        [sg.Button("Save", key="lib_edit_save"), sg.Button("Cancel", key="lib_edit_cancel")]
    ]
    w = sg.Window("Edit", layout, finalize=True, modal=True, disable_minimize=True, element_justification="l")
    print(book_info[url]["start_date"])
    if book_info[url]["start_date"] != "unknown":
        w["lib_edit_start_date"].update(datetime.strftime(datetime.strptime(book_info[url]["start_date"], "%Y-%m-%d"), "%b-%d-%Y"))
    if book_info[url]["end_date"] != "unknown":
        w["lib_edit_end_date"].update(datetime.strftime(datetime.strptime(book_info[url]["end_date"], "%Y-%m-%d"), "%b-%d-%Y"))

    while True:
        e, v = w.read()
        print(e)
        if e == "lib_edit_cancel" or e == sg.WIN_CLOSED:
            w.close()
            return False
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

        if e == "lib_edit_sd_today":
            today = datetime.today()
            w["lib_edit_start_date"].update(datetime.strftime(today, "%b-%d-%Y"))
        
        if e == "lib_edit_sd_pick":
            m, d, y = sg.popup_get_date(no_titlebar=True, keep_on_top=True, close_when_chosen=True)
            date = datetime(y, m, d)
            w["lib_edit_start_date"].update(datetime.strftime(date, "%b-%d-%Y"))
        
        if e == "lib_edit_ed_today":
            today = datetime.today()
            w["lib_edit_end_date"].update(datetime.strftime(today, "%b-%d-%Y"))

        if e == "lib_edit_ed_pick":
            m, d, y = sg.popup_get_date(no_titlebar=True, keep_on_top=True, close_when_chosen=True)
            date = datetime(y, m, d)
            w["lib_edit_end_date"].update(datetime.strftime(date, "%b-%d-%Y"))

        if e == "lib_edit_save":
            ch = v["lib_edit_progress_chapter"]
            try:
                ch = int(ch)
            except:
                w["lib_edit_progress_chapter"].update(book_info[url]["ch"])
                continue
            if ch > 0 and ch <= int(max_ch):
                update(url, ch=ch - 1)
            
            vol = v["lib_edit_progress_volume"]
            try:
                vol = int(vol)
                if vol < 0: raise Exception
            except:
                w["lib_edit_progress_volume"].update(book_info[url]["vol"])
                continue
            if vol >= 0: update(url, vol=vol)

            score = v["lib_edit_score"]
            if score == "-": update(url, score=0)
            else: update(url, score=int(score))

            if v["lib_edit_start_date"] != "unknown":
                update(url, sd=datetime.strftime(datetime.strptime(v["lib_edit_start_date"], "%b-%d-%Y"), "%Y-%m-%d"))
            if v["lib_edit_end_date"] != "unknown":
                update(url, ed=datetime.strftime(datetime.strptime(v["lib_edit_end_date"], "%b-%d-%Y"), "%Y-%m-%d"))            
            
            break

    update_book_info()
    w.close()
    return True

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
    print(original)
    for ix, id in original[::-1]:
        tr.Widget.move(id, "", ix)

def search(query, tr: TreeRtClick):
    removed.clear()
    for id, url in tr.IdToKey.items():
        if url == "": continue
        #if query not in book_info[url]["info"]["title"].lower():
        if re.match(query, book_info[url]["info"]["title"].lower()) is not None:
            ix = tr.Widget.index(id)
            removed.append((ix, id))
    print(removed)

    for _, id in removed:
        tr.Widget.detach(id)