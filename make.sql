create table books (
    url text primary key,
    list text,

    title text,
    alt_names text,
    cover blob,
    author text,
    genres text,
    status text,
    description text,

    chapter integer not null default 0,
    volume integer not null default 0,
    score integer not null default 0,
    start_date integer not null default -1,
    end_date integer not null default -1,
    last_update integer not null default -1
);

create table chapters (
    book_url text,

    chapter_index int,
    chapter_url text primary key,
    title text,
    date int,

    foreign key (book_url) references books(url) on delete cascade on update cascade
);

create table pages (
    chapter_url text,
    page_index int,
    data blob,
    primary key (chapter_url, page_index),
    foreign key (chapter_url) references chapters(chapter_url) on delete cascade on update cascade
);

create table opened_chapters (
    book_url text,
    chapter_url text primary key,
    autodownload int,
    page_index int,
    foreign key (chapter_url) references chapters(chapter_url) on delete cascade on update cascade,
    foreign key (book_url) REFERENCES books(url) on delete cascade on update cascade
);