import textwrap
import PySimpleGUI as sg
from io import BytesIO
from PIL import Image
from datetime import datetime
import re
import hashlib
import time
import json
import config
if config.enable_sqlcipher:
    from sqlcipher3 import dbapi2 as sql
else:
    import sqlite3 as sql
from concurrent.futures import ThreadPoolExecutor

import mangakatana, settings
from util import TreeRtClick, tables, OrderBy, BookList

conn: sql.Connection = None
book_info = {}
thumbnails = []
current_order = OrderBy.UPLOAD

deletes = 0

username: str = None
password: str = None

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
    (1, 'list', 'TEXT', 0, None, 0),
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
    (0, 'chapter_url', 'TEXT', 0, None, 1),
    (1, 'page_index', 'INT', 0, None, 2),
    (2, 'data', 'BLOB', 0, None, 0)
]

opened_chapters_schema = [
    (0, 'book_url', 'TEXT', 0, None, 0),
    (1, 'chapter_url', 'TEXT', 0, None, 1),
    (2, 'autodownload', 'INT', 0, None, 0),
    (3, 'page_index', 'INT', 0, None, 0)
] # add page saving, you'll need to redact the *_opened functions to accomodate and then use set_page on reader obj

def sha384(s: str) -> str:
    return hashlib.sha384(s.encode("utf-8")).hexdigest()

def login(u: str, p: str):
    global username, password
    digest = sha384(p)
    cur = conn.cursor()
    rows = cur.execute("SELECT * FROM users WHERE username=? AND password=?", (u, digest))
    result = len(rows.fetchall()) > 0
    cur.close()
    if result: username = u
    return result

def register(u: str, p: str):
    global username
    digest = sha384(p)
    cur = conn.cursor()
    # check if user already exists
    rows = cur.execute("SELECT * FROM users WHERE username=?", (u,))
    if len(rows.fetchall()) > 0: return False
    cur.execute("INSERT INTO users VALUES (?, ?)", (u, digest))
    conn.commit()
    cur.close()
    username = u
    return True

def update_user(old_username: str, old_password: str, new_username: str | None=None, new_password: str | None=None):
    pass

def verify_schema():
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    names = cur.fetchall()
    names = [x[0] for x in names]
    print(names)
    if names != ["books", "chapters", "opened_chapters", "pages"]: return False
    schemas = [books_schema, chapters_schema, opened_chapters_schema, pages_schema]
    for i, name in enumerate(names):
        cur.execute(f"PRAGMA TABLE_INFO({name})")
        rows = cur.fetchall()
        print(rows)
        if rows != schemas[i]: return False
        print("yay")
    return True

def add(url, ch=0, vol=0, sd=-1, ed=-1, score=0, /, where=BookList.PLAN_TO_READ, last_update=None):
    if last_update is None: last_update = int(time.time())
    query = "INSERT INTO user_books (user, book_url, list, chapter, volume, score, start_date, end_date, last_update) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
    cur = conn.cursor()
    cur.execute(query, (username, url, where, ch, vol, score, sd, ed, last_update))
    cur.execute("INSERT OR IGNORE INTO books (url) VALUES (?)", (url,))
    conn.commit()
    cur.close()
    update_info(url)
    #refresh_book_info()

# fetch fresh information about a book
def update_info(url: str):
    info = mangakatana.get_manga_info(url)
    cover = mangakatana.fetch(info["cover_url"])
    info["cover"] = cover
    if get_book_userinfo(url) is None: return info
    
    query = "UPDATE books SET title=?, alt_names=?, cover=?, status=?, description=? WHERE url=?"    
    cur = conn.cursor()
    cur.execute(query, (info["title"], json.dumps(info["alt_names"]), cover, info["status"], info["description"], url))
    
    # now add author and genres
    cur.execute("INSERT OR IGNORE INTO authors VALUES (?)", (info["author"],))
    cur.execute("INSERT OR IGNORE INTO book_author VALUES (?, ?)", (url, info["author"]))

    cur.executemany("INSERT OR IGNORE INTO genres VALUES (?)", [(genre,) for genre in info["genres"]])
    cur.executemany("INSERT OR IGNORE INTO book_genre VALUES (?, ?)", [(url, genre) for genre in info["genres"]])

    # update chapters
    for chapter in info["chapters"]:
        cur.execute("INSERT OR REPLACE INTO chapters VALUES (?, ?, ?, ?, ?)", (chapter["url"], url, chapter["index"], chapter["name"], time.mktime(chapter["date"].timetuple())))
    
    conn.commit()
    cur.close()
    #refresh_book_info()
    
    return info

# update user's data about a book
def update_userdata(url, ch=None, vol=None, sd=None, ed=None, score=None, last_update=None):
    if last_update is None: last_update = int(time.time())
    args = [(ch, "chapter"), (vol, "volume"), (sd, "start_date"), (ed, "end_date"), (score, "score"), (last_update, "last_update")]
    vals = []
    for arg in args:
        if arg[0] is not None: vals.append(arg[1] + "=?")
    query = "UPDATE user_books SET " + ",".join(vals) + " WHERE book_url=? AND user=?"
    tup = tuple(filter(lambda x: x is not None, [x[0] for x in args] + [url, username]))
    print(query, tup)
    cur = conn.cursor()
    cur.execute(query, tup)
    conn.commit()
    cur.close()
    refresh_book_info()

def delete(url: str):
    global deletes
    cur = conn.cursor()

    # check how many users have this book in their libraries,
    # if > 1 delete the book only from user_books table
    # for the user that requested the deletion.
    cur.execute("SELECT user FROM user_books WHERE book_url=?", (url,))
    remove_everywhere = len(cur.fetchall()) == 1
    if not remove_everywhere:
        cur.execute("DELETE FROM user_books WHERE book_url=? AND user=?", (url, username))
        conn.commit()
        cur.close()
        deletes += 1
        return

    cur.execute("DELETE FROM user_books WHERE book_url=?", (url,))
    cur.execute("DELETE FROM books WHERE url=?", (url,))
    cur.execute("DELETE FROM book_author WHERE book_url=?", (url,))
    cur.execute("DELETE FROM book_genre WHERE book_url=?", (url,))
    conn.commit()
    cur.execute("SELECT * FROM chapters WHERE book_url=?", (url,))
    rows = cur.fetchall()
    for row in rows:
        chapter_url = row[2]
        cur.execute("DELETE FROM pages WHERE chapter_url=?", (chapter_url,))

    cur.execute("DELETE FROM chapters WHERE book_url=?", (url,))
    conn.commit()
    cur.close()
    deletes += 1
    refresh_book_info()

def move(url: str, /, dest: BookList):
    cur = conn.cursor()
    cur.execute("UPDATE user_books SET list=? WHERE book_url=? AND user=?", (dest, url, username))
    conn.commit()
    cur.close()
    refresh_book_info()

def cleanup_and_close():
    if deletes == 0:
        conn.close()
        return
    conn.execute("VACUUM")
    conn.close()
# deprecate to use get_book_userinfo
def get_book(url: str) -> tuple[bool, None | list]:
    cur = conn.cursor()
    query = "SELECT * FROM books WHERE url=?"
    cur.execute(query, (url,))
    rows = cur.fetchall()
    cur.close()
    if len(rows) > 1 or len(rows) == 0: return (False, None)
    return (True, rows[0])

def get_book_userinfo(url: str):
    #refresh_book_info()
    cur = conn.cursor()
    cur.execute("SELECT * FROM user_books WHERE book_url=? AND user=?", (url, username))
    rows = cur.fetchall()
    if len(rows) == 0: return None
    row = rows[0]
    return {
        "list": row[2],
        "ch": row[3],
        "vol": row[4],
        "score": row[5],
        "start_date": row[6],
        "end_date": row[7],
        "last_update": row[8]
    }


def get_book_info(url: str):
    #refresh_book_info()
    cur = conn.cursor()
    cur.execute("SELECT * FROM books WHERE url=?", (url,))
    rows = cur.fetchall()
    if rows == []:
        if not settings.settings["general"]["offline"]: return mangakatana.get_manga_info(url)
        else: return {}
    row = rows[0]
    chapters = []

    status = row[4]
    if status == 1: status = "Completed"
    elif status == 2: status = "Ongoing"
    else: status = "Other"

    info = {
        "url": row[0],
        "cover_url": "",
        "cover": row[3],
        "title": row[1],
        "alt_names": json.loads(row[2]),
        "status": status,
        "description": row[5]}
    
    print(info.keys())

    cur.execute("SELECT * FROM chapters WHERE book_url=? ORDER BY chapter_index ASC", (url,))
    chapter_rows = cur.fetchall()
    for chapter_row in chapter_rows:
        chapters.append({"index": chapter_row[2], "name": chapter_row[3], "url": chapter_row[0], "date": datetime.fromtimestamp(chapter_row[4])})

    info["chapters"] = chapters

    cur.execute("SELECT author FROM book_author WHERE book_url=?", (url,))
    authors = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT genre from book_genre WHERE book_url=?", (url,))
    genres = [r[0] for r in cur.fetchall()]

    info["author"] = authors
    info["genres"] = genres

    return info

def set_pages(chapter_url: str, session, images=None):
    cur = conn.cursor()
    if images is None:
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

def setas_opened(book_url, chapter_url, autodownload:bool=False):
    print(book_url, chapter_url, autodownload)
    cur = conn.cursor()
    cur.execute("SELECT * FROM opened_chapters WHERE chapter_url=? AND user=?", (chapter_url, username))
    if len(cur.fetchall()) > 0:
        cur.close()
        return
    cur.execute("INSERT INTO opened_chapters VALUES(?, ?, ?, 0)", (username, chapter_url, int(autodownload)))
    cur.close()
    conn.commit()

def unsetas_opened(chapter_url):
    print(chapter_url)
    cur = conn.cursor()
    cur.execute("SELECT autodownload FROM opened_chapters WHERE chapter_url=? AND user=?", (chapter_url, username))
    row = cur.fetchone()
    autodownload = bool(row[0])
    cur.execute("DELETE FROM opened_chapters WHERE chapter_url=? AND user=?", (chapter_url, username))
    cur.close()
    conn.commit()
    if autodownload:
        delete_pages(chapter_url)

def get_opened(only_chapters=False):
    cur = conn.cursor()
    cur.execute("SELECT chapter_url, page FROM opened_chapters WHERE user=?", (username,))
    rows = cur.fetchall()
    chapter_urls = [row[0] for row in rows]
    pages = [row[1] for row in rows]
    if only_chapters: return chapter_urls
    book_urls = []
    for chapter_url in chapter_urls:
        cur.execute("SELECT book_url FROM chapters WHERE chapter_url=?", (chapter_url,))
        rows = cur.fetchall()
        book_urls.extend([row[0] for row in rows])
    #print(book_urls, chapter_urls)
    return list(zip(book_urls, chapter_urls, pages))

def save_opened(chapter_url):
    cur = conn.cursor()
    cur.execute("UPDATE opened_chapters SET autodownload=0 WHERE chapter_url=? AND user=?", (chapter_url, username))
    cur.close()
    conn.commit()

def save_current_pages(readers):
    cur = conn.cursor()
    xs = [(r.page_index, r.book_info["chapters"][r.chapter_index]["url"], username) for r in readers]
    cur.executemany("UPDATE opened_chapters SET page=? WHERE chapter_url=? AND user=?", xs)
    cur.close()
    conn.commit()

# full refresh means all book info will be fetched from server first otherwise it'll just be read as-is from the database
def refresh_book_info(full=False, order_by=OrderBy.UPLOAD):
    global book_info, current_order
    book_info.clear()
    cur = conn.cursor()
    query = "SELECT * FROM user_books WHERE user=?"
    cur.execute(query, (username,))
    rows = cur.fetchall()
    if full:
        urls = [row[1] for row in rows]
        with ThreadPoolExecutor() as pool:
            pool.map(update_info, urls)
        refresh_book_info(full=False)
        cur.close()
        return
    for row in rows:
        url = row[1]
        
        info = get_book_info(url)
        print(info.keys())
        book_info.setdefault(url, {"ch": row[3], "vol": row[4], "score": row[5], "start_date": row[6], "end_date": row[7], "last_update": row[8], "info": info, "list": row[2]})
    cur.close()

    match order_by:
        case OrderBy.UPLOAD:
            book_info = dict(sorted(book_info.items(), key=lambda item: item[1]["info"]["chapters"][-1]["date"]))
        case OrderBy.UPDATE:
            book_info = dict(sorted(book_info.items(), key=lambda item: item[1]["last_update"], reverse=True))
        case OrderBy.TITLE:
            book_info = dict(sorted(book_info.items(), key=lambda item: item[1]["info"]["title"]))
        case OrderBy.SCORE:
            book_info = dict(sorted(book_info.items(), key=lambda item: item[1]["score"], reverse=True))
        case OrderBy.CHAPTERS:
            book_info = dict(sorted(book_info.items(), key=lambda item: item[1]["ch"], reverse=True))
        case OrderBy.VOLUMES:
            book_info = dict(sorted(book_info.items(), key=lambda item: item[1]["vol"], reverse=True))
    
    if order_by == current_order:
        book_info = dict(reversed(book_info.items()))
    current_order = order_by

from datetime import timedelta

def time_ago_formatter(diff: timedelta):
    if diff.days > 0:
        return "%s day%s ago" % (diff.days, "s" if diff.days > 1 else "")
    else: return "<1 day ago"

def make_treedata(order_by=OrderBy.UPLOAD):
    global thumbnails
    refresh_book_info(order_by=order_by)
    tds = [sg.TreeData(), sg.TreeData(), sg.TreeData(), sg.TreeData(), sg.TreeData()]

    for i, (k, v) in enumerate(book_info.items()):
        outbuf = BytesIO()
        #print(v)
        im = Image.open(BytesIO(v["info"]["cover"]))
        im.thumbnail((30, 30), resample=Image.BICUBIC)
        im.save(outbuf, "png")
        ix = v["list"] - 1
        
        tds[ix].insert("", k,
            "",
            [
                # name
                textwrap.shorten(v["info"]["title"], width=50, placeholder="..."),
                #score
                v["score"],
                # chapter
                "{}/{}".format(
                    #str(int(v["ch"]) + 1).zfill(2),
                    str(mangakatana.find_chapter_ordinal([item["url"] for item in v["info"]["chapters"]], int(v["ch"]))).zfill(2),
                    str(mangakatana.find_chapter_ordinal([item["url"] for item in v["info"]["chapters"]], len(v["info"]["chapters"]) - 1)).zfill(2) if v["info"]["status"] == "Completed" else "[%s]" % str(mangakatana.find_chapter_ordinal([item["url"] for item in v["info"]["chapters"]], len(v["info"]["chapters"]) - 1)).zfill(2)
                ),
                # volumes read
                v["vol"],
                
                time_ago_formatter(datetime.now() - v["info"]["chapters"][-1]["date"])
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
            sg.Menu([["Library", ["&Refresh", ("!" if settings.settings["general"]["offline"] else "") + "&Check for updates", "&Sort by", ["&Title::title", "&Score::score", "&Chapters::chapters", "&Volumes::volumes", "Latest up&load::upload", "Last up&date::update"]]]], key="lib_menu")
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
    #if not settings.settings["general"]["offline"]: update_info(url)
    refresh_book_info()
    #book_info = get_book_info(url)
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
        try:
            if re.match(query, book_info[url]["info"]["title"], re.IGNORECASE) is None:
                ix = tr.Widget.index(id)
                removed.append((ix, id))
        except:
            return
    print(removed)

    for _, id in removed:
        tr.Widget.detach(id)