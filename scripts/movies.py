"""
수집 대상 영화 목록.

영화를 추가/제거할 때 이 파일만 수정한다. 수집 로직(ingest_data.py)은 건드리지 않는다.
"""

from constants import MovieConfig

MOVIES: list[MovieConfig] = [
    {
        "id": "299534",
        "title": "Avengers: Endgame",
        "series": "marvel",
        "filename": "avengers_endgame",
        "wiki": "Avengers: Endgame",
    },
    {
        "id": "284054",
        "title": "Black Panther",
        "series": "marvel",
        "filename": "black_panther",
        "wiki": "Black Panther (film)",
    },
    {
        "id": "634649",
        "title": "Spider-Man: No Way Home",
        "series": "marvel",
        "filename": "spider_man_no_way_home",
        "wiki": "Spider-Man: No Way Home",
    },
    {
        "id": "284053",
        "title": "Thor: Ragnarok",
        "series": "marvel",
        "filename": "thor_ragnarok",
        "wiki": "Thor: Ragnarok",
    },
    {
        "id": "1022789",
        "title": "Inside Out 2",
        "series": "pixar",
        "filename": "inside_out_2",
        "wiki": "Inside Out 2",
    },
    {
        "id": "508442",
        "title": "Soul",
        "series": "pixar",
        "filename": "soul",
        "wiki": "Soul (2020 film)",
    },
    {
        "id": "354912",
        "title": "Coco",
        "series": "pixar",
        "filename": "coco",
        "wiki": "Coco (2017 film)",
    },
]
