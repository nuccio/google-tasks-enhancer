"""Tripwire: the tracked files of the repository are written in English.

The check looks for two signals in every tracked text file: accented Italian
vowels and a short list of distinctive Italian words. It is not proof that a
file is English, only a guard against the obvious cases; review stays the
main guard.

Short words that are also English or code are deliberately not in the list
(``le`` as in ``le=500``, ``per`` as in "per page", ``non`` as in "non-null",
``media`` as in ``@media``, ``con``, ``come``): they gave false matches.
"""

import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Files that are Italian on purpose. One line each, with the reason.
EXCEPTIONS = {
    # The Italian dictionary of the UI translation layer.
    "frontend/src/i18n/it.ts",
    # This file holds the word list.
    "backend/tests/test_repository_language.py",
}

# Files that are still Italian and wait for their translation.
# The docs step of #56 empties this set; the final PR must have it empty.
NOT_TRANSLATED_YET = frozenset({
    "README.md",
})

# Files that are not text worth checking.
SKIPPED_FILES = {
    "frontend/package-lock.json",
}

ACCENTED_VOWELS = "àèéìòùÀÈÉÌÒÙ"

ITALIAN_WORDS = [
    "della",
    "delle",
    "dello",
    "degli",
    "questo",
    "questa",
    "questi",
    "queste",
    "perché",
    "utente",
    "utenti",
    "sincronizzazione",
    "sincronizza",
    "nessun",
    "nessuna",
    "anche",
    "quando",
    "aggiorna",
    "aggiornato",
    "viene",
    "vengono",
    "ogni",
    "esempio",
    "configurazione",
    "tutti",
    "tutte",
    "dei",
    "nel",
    "dati",
    "il",
    "gli",
    "sono",
    "nostro",
    "tuoi",
    "recupera",
    "errore",
    "funzione",
    "valore",
    "messaggio",
]

ACCENT_RE = re.compile(f"[{ACCENTED_VOWELS}]")
WORD_RE = re.compile(
    r"(?<!\w)(" + "|".join(re.escape(w) for w in ITALIAN_WORDS) + r")(?!\w)",
    re.IGNORECASE,
)


def find_italian(text: str) -> list[tuple[int, str]]:
    """Return (line number, matched word or character) for every signal."""
    text = unicodedata.normalize("NFC", text)
    found = []
    for number, line in enumerate(text.splitlines(), start=1):
        for match in ACCENT_RE.finditer(line):
            found.append((number, match.group(0)))
        for match in WORD_RE.finditer(line):
            found.append((number, match.group(0)))
    return found


def check_text(name: str, text: str) -> list[str]:
    """Return one report line per match, naming file, line and what was found."""
    return [f"{name}:{number}: {what!r}" for number, what in find_italian(text)]


def read_text(path: Path) -> str | None:
    """Return the file as text, or None for a binary file."""
    data = path.read_bytes()
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def tracked_files() -> list[str]:
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip("not a git checkout")
    return [p for p in result.stdout.decode("utf-8").split("\0") if p]


def test_tracked_files_have_no_italian():
    skipped = set(EXCEPTIONS) | set(NOT_TRANSLATED_YET) | set(SKIPPED_FILES)
    problems = []
    for name in tracked_files():
        if name in skipped:
            continue
        path = REPO_ROOT / name
        if not path.is_file():
            continue
        text = read_text(path)
        if text is None:
            continue
        problems.extend(check_text(name, text))
    assert not problems, "Italian text found:\n" + "\n".join(problems)


# Self-checks: in-memory strings only, never the repository.


def test_finds_an_italian_sentence():
    assert check_text("a.txt", "Questo è un esempio della sincronizzazione")


def test_finds_an_accented_vowel():
    assert find_italian("città") == [(1, "à")]


def test_finds_a_decomposed_accent():
    # "a" followed by a combining grave accent, normalised to "à" before matching
    assert find_italian("citta\u0300") == [(1, "à")]


def test_finds_an_upper_case_accented_vowel():
    assert find_italian("CITTÀ") == [(1, "À")]


def test_binary_file_is_skipped(tmp_path):
    with_nul = tmp_path / "a.bin"
    with_nul.write_bytes(b"citt\xc3\xa0\x00")
    not_utf8 = tmp_path / "b.bin"
    not_utf8.write_bytes(b"\xff\xfe questo")
    text_file = tmp_path / "c.txt"
    text_file.write_text("questo", encoding="utf-8")
    assert read_text(with_nul) is None
    assert read_text(not_utf8) is None
    assert read_text(text_file) == "questo"


@pytest.mark.parametrize(
    "line",
    [
        "@media (max-width: 600px) {",
        "limit: int = Query(50, le=500)",
        "Show 50 tasks per page",
        "Returns a non-null value",
        "Arrows: ▲ ▼ ‹",
        "The user logs in and the sync runs when needed.",
    ],
)
def test_english_text_is_not_flagged(line):
    assert check_text("a.txt", line) == []


def test_report_names_file_and_line():
    report = check_text("src/app.py", "# fine\n# questo no\n")
    assert report == ["src/app.py:2: 'questo'"]


def test_word_match_is_whole_word_and_ignores_case():
    assert find_italian("QUESTO") == [(1, "QUESTO")]
    assert find_italian("questions") == []
