from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

@dataclass
class MangaChapter:
    name: str
    url: str
    release_date: datetime

@dataclass
class MangaBook:
    url: str
    title: str
    authors: list[str]
    alt_names: list[str]
    genres: list[str]
    status: str
    description: str
    cover_url: str
    chapters: list[MangaChapter]

class MangaWebsite(ABC):
    @abstractmethod
    def get_book_info(book_url: str) -> MangaBook:
        """Gets detailed info about a book by it's url"""
        ...
    
    @abstractmethod
    def get_chapter_images(chapter: MangaChapter) -> list[str]:
        """Gets the image links comprising the passed chapter."""
        ...
    
    @abstractmethod
    def get_titles() -> list[tuple[str, str]]:
        """Returns list of (title, url) tuples for every book in the catalogue."""
        ...