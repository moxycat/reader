create table authors (
    name text primary key
);

create table book_author (
    book_url text,
    author text,
    primary key (book_url, author),
    foreign key (book_url) references books(url),
    foreign key (author) references authors(name) on delete cascade
);

create table genres (
    name text primary key
);

create table book_genre (
    book_url text,
    genre text,
    primary key (book_url, genre),
    foreign key (book_url) references books(url),
    foreign key (genre) references genres(name) on delete cascade
);

create table books (
    url text primary key,

    title text,
    alt_names text,
    cover blob,
    status int,
    description text
);

create table chapters (
    chapter_url text primary key,
    book_url text,
    chapter_index int,
    title text,
    date int,

    foreign key (book_url) references books(url)
);

create table pages (
    chapter_url text,
    page_index int,
    data blob,
    primary key (chapter_url, page_index),
    foreign key (chapter_url) references chapters(chapter_url)
);

create table opened_chapters (
    user text,
    chapter_url text,
    autodownload int,
    page int,
    primary key (user, chapter_url),
    foreign key (user) references users(username),
    foreign key (chapter_url) references chapters(chapter_url)
);

create table history (
    user text,
    book_url text,
    chapter_url text,
    time int,
    primary key (user, book_url, chapter_url, time),
    foreign key (user) references users(username),
    foreign key (book_url) references books(url),
    foreign key (chapter_url) references chapters(chapter_url)
);

create table users (
    username text primary key,
    password text
);

create table user_books (
    user text,
    book_url text,
    list int,
    
    chapter int not null default 0,
    volume int not null default 0,
    score int not null default 0,
    start_date int not null default -1,
    end_date int not null default -1,
    last_update int not null default -1,
    
    primary key (user, book_url),
    foreign key (user) references users(user),
    foreign key (book_url) references books(url)
);

/*insert into lists values (1, "books_cr"), (2, "books_cmpl"), (3, "books_idle"), (4, "books_drop"), (5, "books_ptr");
insert into statuses values (1, "Completed"), (2, "Ongoing"), (3, "Other");*/