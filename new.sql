create table books (
    url text primary key,
    list text not null default "books_ptr",

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
    foreign key (chapter_url) references chapters(chapter_url) on delete cascade on update cascade
);