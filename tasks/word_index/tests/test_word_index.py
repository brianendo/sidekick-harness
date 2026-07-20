import time

from word_index import WordIndex


def test_basic_positions():
    idx = WordIndex("the cat sat on the mat")
    assert idx.positions("the") == [0, 4]
    assert idx.positions("cat") == [1]
    assert idx.positions("mat") == [5]


def test_absent_word():
    idx = WordIndex("hello world")
    assert idx.positions("nope") == []
    assert idx.count("nope") == 0
    assert idx.first("nope") is None


def test_case_insensitive():
    idx = WordIndex("The THE the")
    assert idx.positions("the") == [0, 1, 2]
    assert idx.positions("THE") == [0, 1, 2]
    assert idx.count("The") == 3


def test_punctuation_separates_tokens():
    idx = WordIndex("hello, world! hello... world?")
    assert idx.positions("hello") == [0, 2]
    assert idx.positions("world") == [1, 3]


def test_apostrophes_inside_tokens():
    idx = WordIndex("don't stop, don't")
    assert idx.positions("don't") == [0, 2]
    assert idx.positions("don") == []


def test_digits_in_tokens():
    idx = WordIndex("route 66 is route66")
    assert idx.positions("66") == [1]
    assert idx.positions("route66") == [3]


def test_count_and_first():
    idx = WordIndex("a b a c a")
    assert idx.count("a") == 3
    assert idx.first("a") == 0
    assert idx.first("c") == 3


def test_positions_returns_copy():
    idx = WordIndex("x y x")
    got = idx.positions("x")
    got.append(999)
    assert idx.positions("x") == [0, 2]


def test_empty_text():
    idx = WordIndex("")
    assert idx.positions("anything") == []


def test_o1_queries():
    # big text, many queries — rescanning per query would take minutes
    text = " ".join(f"word{i % 1000}" for i in range(200_000))
    idx = WordIndex(text)
    start = time.perf_counter()
    for i in range(20_000):
        idx.count(f"word{i % 1000}")
        idx.first(f"word{i % 1000}")
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, f"40k queries took {elapsed:.1f}s — queries are not O(1)"
