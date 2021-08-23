from enum import Enum, auto


class Type(Enum):
    CV_OK = auto()
    VACANCY_OK = auto()
    TAGS_OK = auto()
    INVALID = auto()
    NO_TAGS = auto()
    OVERLAPPED_TAGS = auto()
    NOT_ENGLISH_PLATFORM = auto()
    NOT_RUSSIAN_VACANCY = auto()

