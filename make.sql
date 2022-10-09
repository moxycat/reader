CREATE TABLE books_cr (
    url text primary key,
    
    chapter integer not null default 0,
    volume integer not null default 0,
    
    start_date text not null default "unknown",
    end_date text not null default "unknown",
    score text not null default "0",
    last_update text not null default "unknown"
);

CREATE TABLE books_cmpl (
    url text primary key,
    
    chapter integer not null default 0,
    volume integer not null default 0,
    
    start_date text not null default "unknown",
    end_date text not null default "unknown",
    score text not null default "0",
    last_update text not null default "unknown"
);

CREATE TABLE books_idle (
    url text primary key,
    
    chapter integer not null default 0,
    volume integer not null default 0,
    
    start_date text not null default "unknown",
    end_date text not null default "unknown",
    score text not null default "0",
    last_update text not null default "unknown"
);

CREATE TABLE books_drop (
    url text primary key,
    
    chapter integer not null default 0,
    volume integer not null default 0,
    
    start_date text not null default "unknown",
    end_date text not null default "unknown",
    score text not null default "0",
    last_update text not null default "unknown"
);

CREATE TABLE books_ptr (
    url text primary key,
    
    chapter integer not null default 0,
    volume integer not null default 0,
    
    start_date text not null default "unknown",
    end_date text not null default "unknown",
    score text not null default "0",
    last_update text not null default "unknown"
);

CREATE TABLE history (
    id int primary key,
    ts date,
    
)