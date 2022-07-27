import PySimpleGUI as sg
import sqlite3 as sql
from io import BytesIO
from PIL import Image
import time

import mangakatana

def init_db():
    conn = sql.connect("a.db")
    cur = conn.cursor()
    return (conn, cur)

def add(url, ch=0, p=0):
    conn, cur = init_db()
    cur.execute("INSERT INTO reading_list VALUES(?, ?, ?);", (url, ch, p))
    conn.commit()

def update(url, ch, p):
    conn, cur = init_db()
    cur.execute("UPDATE reading_list SET chapter = ?, page = ? WHERE url = ?", (ch, p, url))
    conn.commit()

def is_in_lib(url):
    conn, cur = init_db()
    cur.execute("SELECT * FROM reading_list WHERE url=?", (url,))
    rows = cur.fetchall()
    return (len(rows) > 0, rows[0] if len(rows) > 0 else None)

def make_window_layout():
    _, cur = init_db()
    cur.execute("SELECT * FROM reading_list;")
    rows = cur.fetchall()
    thumbnail_urls = []
    layout = []
    infos = []

    treedata = sg.TreeData()
    
    rowdict = {}

    for row in rows:
        info = mangakatana.get_manga_info(row[0])
        thumbnail_urls.append(info["cover_url"])
        infos.append(info)
        rowdict.setdefault(row, info)

    thumbnails = mangakatana.download_images(thumbnail_urls)

    [i for i, x in enumerate(rows)].sort()

    for i, row in enumerate(rows):
        buf = BytesIO(thumbnails[i])
        outbuf = BytesIO()
        im = Image.open(buf)
        im.thumbnail((50, 50), resample=Image.BICUBIC)
        im.save(outbuf, "png")
        treedata.insert("", i,
            "",
            [infos[i]["title"], "{}/{}".format(str(int(row[1]) + 1).zfill(2), "??" if infos[i]["status"] == "Ongoing" else str(len(infos[i]["chapters"])).zfill(2)), infos[i]["chapters"][-1]["date"]],
            outbuf.getvalue()
            )
        buf.close()
        outbuf.close()
    title_max_len = max([len(a["title"]) for a in infos]) + 20
    col0_width = 50
    layout = [
        [
            sg.Menu([["Library", ["Search"]]], key="lib_menu")
        ],
        [
            sg.Tree(
                data=treedata, headings=["Title", "Progress", "Last update"], col0_heading="",
                key="lib_tree", row_height=50, num_rows=5, enable_events=True,
                max_col_width=title_max_len, justification="l"
            )
        ]
    ]
    
    return layout

def start_reading(title):
    layout = [
        [sg.Text("Would you like to add {} to your reading list?".format(title))],
        [sg.Button("Yes", key="reading_start_yes"), sg.Button("No", key="reading_start_no")]
    ]
    return sg.Window("", layout, modal=True, finalize=True, disable_minimize=True, disable_close=True)