"""Usernames of new Google passengers: the email's local part under the username rules."""

import re
from itertools import islice

import pytest

from taxi_service.modules.users.schemas import USERNAME_PATTERN
from taxi_service.modules.users.service import google_username, username_candidates


@pytest.mark.parametrize(
    ("email", "username"),
    [
        ("Alice.Smith@gmail.com", "alice_smith"),
        ("ivan.petrov+taxi@mail.kz", "ivan_petrov_taxi"),
        ("o'brien..jr@example.com", "o_brien_jr"),
        ("__x__@example.com", "x_user"),
        ("a@example.com", "a_user"),
        ("Жанна@mail.kz", "user"),
        ("user_01@example.com", "user_01"),
        (f"{'b' * 40}@example.com", "b" * 32),
    ],
)
def test_username_comes_from_the_local_part(email: str, username: str) -> None:
    assert google_username(email) == username
    assert re.fullmatch(USERNAME_PATTERN, username)


def test_candidates_add_numbered_suffixes_within_the_length_limit() -> None:
    assert list(islice(username_candidates("alice"), 3)) == ["alice", "alice_2", "alice_3"]
    long = "a" * 32
    assert list(islice(username_candidates(long), 2)) == [long, f"{'a' * 30}_2"]
    assert all(re.fullmatch(USERNAME_PATTERN, name) for name in username_candidates(long))
