from msilib import schema
import textwrap
import PySimpleGUI as sg
#import sqlite3 as sql
from io import BytesIO
from PIL import Image
from datetime import datetime
import re
import base64
import time
import json
from sqlcipher3 import dbapi2 as sql

import mangakatana, settings
from util import TreeRtClick, DEFAULT_COVER

conn: sql.Connection = None
#cur: sql.Cursor = None
book_info = {}
thumbnails = []

tables = ["books_cr", "books_cmpl", "books_idle", "books_drop", "books_ptr"]

class BookList():
    READING = 0
    COMPLETED = 1
    ON_HOLD = 2
    DROPPED = 3
    PLAN_TO_READ = 4

def init_db(password=None):
    global conn, cur
    conn = sql.connect(settings.settings["storage"]["path"], check_same_thread=False)
    if password is not None:
        conn.execute(f"PRAGMA key='{password}'")
    try:
        conn.execute(f"SELECT * FROM books LIMIT 1")
        return True
    except:
        conn.close()
        return False

books_schema = [
    (0, 'url', 'TEXT', 0, None, 1),
    (1, 'list', 'TEXT', 1, '"books_ptr"', 0),
    (2, 'title', 'TEXT', 0, None, 0),
    (3, 'alt_names', 'TEXT', 0, None, 0),
    (4, 'cover', 'BLOB', 0, None, 0),
    (5, 'author', 'TEXT', 0, None, 0),
    (6, 'genres', 'TEXT', 0, None, 0),
    (7, 'status', 'TEXT', 0, None, 0),
    (8, 'description', 'TEXT', 0, None, 0),
    (9, 'chapter', 'INTEGER', 1, '0', 0),
    (10, 'volume', 'INTEGER', 1, '0', 0),
    (11, 'score', 'INTEGER', 1, '0', 0),
    (12, 'start_date', 'INTEGER', 1, '-1', 0),
    (13, 'end_date', 'INTEGER', 1, '-1', 0),
    (14, 'last_update', 'INTEGER', 1, '-1', 0)
]
chapters_schema = [
    (0, 'book_url', 'TEXT', 0, None, 0),
    (1, 'chapter_index', 'INT', 0, None, 0),
    (2, 'chapter_url', 'TEXT', 0, None, 1),
    (3, 'title', 'TEXT', 0, None, 0),
    (4, 'date', 'INT', 0, None, 0)
]
pages_schema = [
    (0, 'chapter_url', 'TEXT', 0, None, 0),
    (1, 'page_index', 'INT', 0, None, 0),
    (2, 'data', 'BLOB', 0, None, 0)
]

def verify_schema():
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type=\"table\" ORDER BY name")
    names = cur.fetchall()
    names = [x[0] for x in names]
    if names != ["books", "chapters", "pages"]: return False
    schemas = [books_schema, chapters_schema, pages_schema]
    for i, name in enumerate(names):
        cur.execute(f"PRAGMA TABLE_INFO({name})")
        rows = cur.fetchall()
        if rows != schemas[i]: return False
    return True

def add(url, ch=0, vol=0, sd=-1, ed=-1, score=0, /, where=BookList.PLAN_TO_READ, last_update=None):
    if last_update is None: last_update = int(time.time())
    query = "INSERT INTO books (url, list, chapter, volume, score, start_date, end_date, last_update) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
    cur = conn.cursor()
    cur.execute(query, (url, tables[where], ch, vol, score, sd, ed, last_update))
    conn.commit()
    cur.close()
    update_info(url)
    refresh_book_info()

# fetch fresh information about a book
def update_info(url: str):
    info = mangakatana.get_manga_info(url)
    cover = mangakatana.fetch(info["cover_url"])
    cover = base64.b64encode(cover)
    info["cover"] = cover
    is_in_library, _ = get_book(url)
    if not is_in_library: return info
    
    query = "UPDATE books SET title=?, alt_names=?, author=?, genres=?, status=?, description=?, cover=? WHERE url=?"    
    cur = conn.cursor()
    cur.execute(query, (info["title"], json.dumps(info["alt_names"]), info["author"], json.dumps(info["genres"]), info["status"], info["description"], cover, url))
    
    # update chapters
    for chapter in info["chapters"]:
        cur.execute("INSERT OR REPLACE INTO chapters VALUES (?, ?, ?, ?, ?)", (url, chapter["index"], chapter["url"], chapter["name"], time.mktime(chapter["date"].timetuple())))
    
    conn.commit()
    cur.close()
    refresh_book_info()
    
    return info

# update user's data about a book
def update_userdata(url, ch=None, vol=None, sd=None, ed=None, score=None, last_update=None):
    if last_update is None: last_update = int(time.time())
    args = [(ch, "chapter"), (vol, "volume"), (sd, "start_date"), (ed, "end_date"), (score, "score"), (last_update, "last_update")]
    vals = []
    for arg in args:
        if arg[0] is not None: vals.append(arg[1] + "=?")
    query = "UPDATE books SET " + ",".join(vals) + f" WHERE url='{url}'"
    tup = tuple(filter(lambda x: x is not None, [x[0] for x in args]))
    print(query, tup)
    cur = conn.cursor()
    cur.execute(query, tup)
    conn.commit()
    cur.close()
    refresh_book_info()

def delete(url: str):
    cur = conn.cursor()
    cur.execute("DELETE FROM books WHERE url=?", (url,))
    cur.execute("SELECT * FROM chapters WHERE book_url=?", (url,))
    rows = cur.fetchall()
    for row in rows:
        chapter_url = row[2]
        cur.execute("DELETE FROM pages WHERE chapter_url=?", (chapter_url,))

    cur.execute("DELETE FROM chapters WHERE book_url=?", (url,))
    conn.commit()
    cur.close()
    refresh_book_info()

def move(url: str, /, dest: BookList):
    cur = conn.cursor()
    cur.execute("UPDATE books SET list=? WHERE url=?", (tables[dest], url))
    conn.commit()
    cur.close()
    refresh_book_info()

def get_book(url: str) -> tuple[bool, None | list]:
    cur = conn.cursor()
    query = "SELECT * FROM books WHERE url=?"
    cur.execute(query, (url,))
    rows = cur.fetchall()
    cur.close()
    if len(rows) > 1 or len(rows) == 0: return (False, None)
    return (True, rows[0])

def get_book_info(url: str):
    refresh_book_info()
    cur = conn.cursor()
    cur.execute("SELECT * FROM books WHERE url=?", (url,))
    rows = cur.fetchall()
    if rows == []: return {}
    row = rows[0]
    chapters = []

    cur.execute("SELECT * FROM chapters WHERE book_url=? ORDER BY chapter_index ASC", (url,))
    chapter_rows = cur.fetchall()
    for chapter_row in chapter_rows:
        chapters.append({"index": chapter_row[1], "name": chapter_row[3], "url": chapter_row[2], "date": datetime.fromtimestamp(chapter_row[4])})

    return {
        "url": row[0],
        "cover_url": "",
        "cover": row[4],
        "title": row[2],
        "alt_names": json.loads(row[3]),
        "author": row[5],
        "genres": json.loads(row[6]),
        "status": row[7],
        "description": row[8],
        "chapters": chapters
        }

def set_pages(chapter_url: str, session):
    cur = conn.cursor()
    image_urls = mangakatana.get_manga_chapter_images(chapter_url, session)
    images = mangakatana.download_images(image_urls)

    for image in images:
        im = Image.open(BytesIO(image))
        try:
            im.verify()
            im.close()
        except:
            im.close()
            return False

    for i, image in enumerate(images):
        cur.execute("INSERT INTO pages VALUES (?, ?, ?)", (chapter_url, i, image))
    conn.commit()
    cur.close()
    return chapter_url

def get_pages(chapter_url: str) -> list[bytes]:
    cur = conn.cursor()
    query = "SELECT * FROM pages WHERE chapter_url=? ORDER BY page_index ASC"
    cur.execute(query, (chapter_url,))
    rows = cur.fetchall()
    cur.close()
    images: list[bytes] = []
    for row in rows:
        images.append(row[2])
    return images

def delete_pages(chapter_url: str):
    cur = conn.cursor()
    query = "DELETE FROM pages WHERE chapter_url=?"
    cur.execute(query, (chapter_url,))
    conn.commit()

def get_downloaded_chapters():
    cur = conn.cursor()
    query = "SELECT DISTINCT chapter_url FROM pages"
    cur.execute(query)
    rows = cur.fetchall()
    cur.close()
    return [row[0] for row in rows]

# full refresh means all book info will be fetched from server first otherwise it'll just be read as-is from the database
def refresh_book_info(full=False):
    global book_info
    book_info.clear()
    cur = conn.cursor()
    query = "SELECT * FROM books"
    cur.execute(query)
    rows = cur.fetchall()
    if full:
        for row in rows:
            update_info(row[0])
        refresh_book_info(False)
        cur.close()
        return
    for row in rows:
        url = row[0]
        # get chapters
        cur.execute("SELECT * FROM chapters WHERE book_url=? ORDER BY chapter_index ASC", (url,))
        chapter_rows = cur.fetchall()
        chapters = []
        for i, chapter_row in enumerate(chapter_rows):
            chapters.append({"index": i, "name": chapter_row[3], "url": chapter_row[2], "date": datetime.utcfromtimestamp(chapter_row[4])})
        #chapters.reverse()
        info = {
            "url": url,
            "title": row[2],
            "alt_names": row[3],
            "cover": row[4],
            "author": row[5],
            "genres": row[6],
            "status": row[7],
            "description": row[8],
            "chapters": chapters
        }
        book_info.setdefault(url, {"ch": row[9], "vol": row[10], "score": row[11], "start_date": row[12], "end_date": row[13], "last_update": row[14], "info": info, "list": row[1]})
    
    book_info = dict(sorted(book_info.items(), key=lambda item: item[1]["info"]["chapters"][-1]["date"], reverse=True))
    cur.close()

def make_treedata():
    global thumbnails
    refresh_book_info()
    tds = [sg.TreeData(), sg.TreeData(), sg.TreeData(), sg.TreeData(), sg.TreeData()]

    for i, (k, v) in enumerate(book_info.items()):
        outbuf = BytesIO()
        im = Image.open(BytesIO(base64.b64decode(v["info"]["cover"])))
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
    tds = make_treedata()
    title_max_len = 65

    tab_cr_layout = [
        [
            TreeRtClick(
                data=tds[0], headings=["Title", "Score", "Current chapter", "Volumes read", "Lastest upload"], col0_heading="",
                key="lib_tree_cr", row_height=30, num_rows=10, enable_events=False,
                max_col_width=title_max_len, justification="l",
                right_click_menu=["", ["More info", "View chapters", "Edit", "Remove", "Move to", ["Completed", "On-hold", "Dropped", "Plan to read"]]],
                expand_x=True
            )
        ]
    ]
    tab_cmpl_layout = [
        [
            TreeRtClick(
                data=tds[1], headings=["Title", "Score", "Current chapter", "Volumes read", "Lastest upload"], col0_heading="",
                key="lib_tree_cmpl", row_height=30, num_rows=10, enable_events=False,
                max_col_width=title_max_len, justification="l",
                right_click_menu=["", ["More info", "View chapters", "Edit", "Remove", "Move to", ["Reading", "On-hold", "Dropped", "Plan to read"]]],
                expand_x=True
            )
        ]
    ]
    tab_idle_layout = [
        [
            TreeRtClick(
                data=tds[2], headings=["Title", "Score", "Current chapter", "Volumes read", "Lastest upload"], col0_heading="",
                key="lib_tree_idle", row_height=30, num_rows=10, enable_events=False,
                max_col_width=title_max_len, justification="l",
                right_click_menu=["", ["More info", "View chapters", "Edit", "Remove", "Move to", ["Reading", "Completed", "Dropped", "Plan to read"]]],
                expand_x=True            
            )
        ]
    ]
    tab_drop_layout = [
        [
            TreeRtClick(
                data=tds[3], headings=["Title", "Score", "Current chapter", "Volumes read", "Lastest upload"], col0_heading="",
                key="lib_tree_drop", row_height=30, num_rows=10, enable_events=False,
                max_col_width=title_max_len, justification="l",
                right_click_menu=["", ["More info", "View chapters", "Edit", "Remove", "Move to", ["Reading", "Completed", "On-hold", "Plan to read"]]],
                expand_x=True
            )
        ]
    ]
    tab_ptr_layout = [
        [
            TreeRtClick(
                data=tds[4], headings=["Title", "Score", "Current chapter", "Volumes read", "Lastest upload"], col0_heading="",
                key="lib_tree_ptr", row_height=30, num_rows=10, enable_events=True,
                max_col_width=title_max_len, justification="l",
                right_click_menu=["", ["More info", "View chapters", "Edit", "Remove", "Move to", ["Reading", "Completed", "On-hold", "Dropped"]]],
                expand_x=True
            )
        ]
    ]

    layout = [
        [
            sg.Menu([["Library", ["Refresh local database", "Sort by", ["Title", "Score", "Chapters", "Volumes", "Latest upload", "Last update"]]]], key="lib_menu")
        ],
        [
            sg.Input(key="lib_search_query", expand_x=True), sg.Button("⌕", key="lib_search", bind_return_key=True)
        ],
        #[sg.Text("Order by"), sg.Combo(["Title", "Score", "Chapters", "Volumes", "Latest upload"])],
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
    if not settings.settings["general"]["offline"]:
        update_info(url)
    refresh_book_info()
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
                [sg.Combo(["-"] + [x for x in range(1, 11)], book_info[url]["score"] if book_info[url]["score"] != "0" else "-", key="lib_edit_score", size=(3, 1), readonly=True, background_color="white")],
                [sg.Input("unknown", readonly=True, key="lib_edit_start_date", size=(11, 1), disabled_readonly_background_color="white"), sg.Button("Today", key="lib_edit_sd_today"), sg.Button("Pick", key="lib_edit_sd_pick")],
                [sg.Input("unknown", readonly=True, key="lib_edit_end_date", size=(11, 1), disabled_readonly_background_color="white"), sg.Button("Today", key="lib_edit_ed_today"), sg.Button("Pick", key="lib_edit_ed_pick")]
            ])
        ],
        [sg.Button("Save", key="lib_edit_save"), sg.Button("Cancel", key="lib_edit_cancel")]
    ]
    w = sg.Window("Edit", layout, finalize=True, modal=True, disable_minimize=True, element_justification="l")
    print(book_info[url]["start_date"])
    if book_info[url]["start_date"] != -1:
        w["lib_edit_start_date"].update(datetime.strftime(datetime.fromtimestamp(book_info[url]["start_date"]), "%b-%d-%Y"))
    if book_info[url]["end_date"] != -1:
        w["lib_edit_end_date"].update(datetime.strftime(datetime.fromtimestamp(book_info[url]["end_date"]), "%b-%d-%Y"))

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
            ret = sg.popup_get_date(no_titlebar=False, keep_on_top=True, close_when_chosen=True)
            if ret == None: continue
            else: m, d, y = ret
            date = datetime(y, m, d)
            w["lib_edit_start_date"].update(datetime.strftime(date, "%b-%d-%Y"))
        
        if e == "lib_edit_ed_today":
            today = datetime.today()
            w["lib_edit_end_date"].update(datetime.strftime(today, "%b-%d-%Y"))

        if e == "lib_edit_ed_pick":
            ret = sg.popup_get_date(no_titlebar=False, keep_on_top=True, close_when_chosen=True)
            if ret == None: continue
            else: m, d, y = ret
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
                update_userdata(url, ch=ch - 1)
            
            vol = v["lib_edit_progress_volume"]
            try:
                vol = int(vol)
                if vol < 0: raise Exception
            except:
                w["lib_edit_progress_volume"].update(book_info[url]["vol"])
                continue
            if vol >= 0: update_userdata(url, vol=vol)

            score = v["lib_edit_score"]
            if score == "-": update_userdata(url, score=0)
            else: update_userdata(url, score=int(score))

            if v["lib_edit_start_date"] != "unknown":
                update_userdata(url, sd=int(time.mktime(datetime.strptime(v["lib_edit_start_date"], "%b-%d-%Y").timetuple())))
            if v["lib_edit_end_date"] != "unknown":
                update_userdata(url, ed=int(time.mktime(datetime.strptime(v["lib_edit_end_date"], "%b-%d-%Y").timetuple())))
            break

    refresh_book_info()
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
        if re.match(query, book_info[url]["info"]["title"], re.IGNORECASE) is None:
            ix = tr.Widget.index(id)
            removed.append((ix, id))
    print(removed)

    for _, id in removed:
        tr.Widget.detach(id)