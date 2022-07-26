CREATE TABLE reading_list (
    url text primary key,
    chapter integer,
    page integer
);

CREATE TABLE favourites (
    url text,
    foreign key(url) references reading_list(url)
)