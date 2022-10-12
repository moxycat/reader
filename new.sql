create table books (
    url text primary key,
    list text not null default "books_ptr",

    title text,
    alt_title text,
    cover_url text,
    author text,
    genres text,
    status text,
    description text,

    chapter integer not null default 0,
    volume integer not null default 0,
    start_date text not null default "unknown",
    end_date text not null default "unknown",
    score text not null default "0",
    last_update text not null default "unknown"
);

create table chapters (
    book_url text,

    chapter_index int,
    chapter_url text primary key,
    title text,
    date text,

    foreign key (book_url) references books(url)
);

create table pages (
    chapter_url text,
    page_index int,
    data blob,
    foreign key (chapter_url) references chapters(chapter_url) on delete cascade
);