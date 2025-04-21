import pytest
from bibformat import tools
import sys
from pathlib import Path
import re

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.mark.parametrize(
    "input_str, expected",
    [
        ("Doe, Jane and Smith, John", "Jane Doe and John Smith"),
        ("Doe, Jane", "Jane Doe"),
        ("Jane Doe and John Smith", "Jane Doe and John Smith"),
        ("Doe, Jane and John Smith", "Jane Doe and John Smith"),
        ("Doe, Jane\nand\nSmith, John", "Jane Doe and John Smith"),
    ],
)
def test_reformat_authors(input_str, expected):
    assert tools.reformat_authors(input_str) == expected


def reformat_single_entry(entry_text: str):
    fields_to_remove = ["issn", "abstract", "paid", "priced", "local-url", "pmcid"]
    entry_text = re.sub(r"(@\w+)\s*{", r"\1{", entry_text)
    key_match = re.match(r"(@\w+{([^,\n]+)),?", entry_text, flags=re.DOTALL)
    assert key_match is not None

    key_line = key_match.group(1)
    rest = entry_text[key_match.end() :].strip()

    # Remove trailing } if on its own line
    if rest.endswith("}"):
        lines = rest.splitlines()
        if lines[-1].strip() == "}":
            rest = "\n".join(lines[:-1]).rstrip()

    # Strip unwanted fields
    for field in fields_to_remove:
        rest = re.sub(rf",?\s*{field}\s*=\s*{{.*?}}\s*", "", rest, flags=re.DOTALL)

    fields = tools.split_bib_fields(rest)
    formatted_fields = []
    for field in fields:
        if not field.strip():
            continue
        if field.strip().startswith("author"):
            author_field = re.match(r"author\s*=\s*{(.*)}", field.strip(), re.DOTALL)
            if author_field:
                new_author = tools.reformat_authors(author_field.group(1))
                formatted_fields.append(f",\tauthor = {{{new_author}}}")
                continue
        formatted_fields.append(f",\t{field.strip()}")

    if formatted_fields:
        formatted_fields[-1] += ","

    formatted_entry = f"{key_line}\n" + "\n".join(formatted_fields) + "\n}"

    # ✅ Validation happens here, after formatting
    print("\n=== Output Entry ===")
    print(formatted_entry)
    print("\n=== Lines ===")
    for line in formatted_entry.splitlines():
        print(repr(line))
        assert line.startswith(",\t") or line.startswith("@") or line == "}"

    return formatted_entry


def test_bachman_entry_reformatting():
    original_entry = """@article{Bachman-etal-2017,
year = {2017},
title = {{Mesoscale and Submesoscale Effects on Mixed Layer Depth in the Southern Ocean}},
author = {Bachman, S. D. and Taylor, J. R. and Adams, K. A. and Hosegood, P. J.},
journal = {Journal of Physical Oceanography},
issn = {0022-3670},
doi = {10.1175/jpo-d-17-0034.1},
abstract = {{...}},
pages = {2173--2188},
number = {9},
volume = {47},
local-url = {file://somepath.pdf}
}"""

    output = reformat_single_entry(original_entry)

    # Sanity check: full entry balanced
    assert_braces_balanced(output, context="full entry")

    # Basic structural checks
    assert output.startswith("@article{Bachman-etal-2017")
    assert output.endswith("}")

    # Unwanted fields removed
    assert "issn" not in output
    assert "abstract" not in output
    assert "local-url" not in output

    # Author reformatted
    assert (
        "author = {S. D. Bachman and J. R. Taylor and K. A. Adams and P. J. Hosegood}"
        in output
    )

    # Properly formatted commas and indentation
    lines = output.splitlines()
    assert all(
        line.startswith(",\t") or line.startswith("@") or line == "}" for line in lines
    )

    # ✅ Global brace match check
    open_braces = output.count("{")
    close_braces = output.count("}")
    assert (
        open_braces == close_braces
    ), f"Mismatched braces: open={{ {open_braces} }}, close={{ {close_braces} }}"

    # ✅ Optional: Check per field
    for line in output.splitlines():
        if "=" in line:
            opens = line.count("{")
            closes = line.count("}")
            assert opens == closes, f"Brace mismatch in line: {line}"


def test_split_bib_fields_balanced_braces():
    entry_body = """
year = {2017},
title = {{Nested, with commas, inside}},
doi = {10.1175/jpo-d-17-0034.1}},
pages = {2173--2188},
number = {9},
volume = {47}
""".strip()

    result = tools.split_bib_fields(entry_body)

    assert len(result) == 6
    assert result[0].startswith("year = {2017}")
    assert result[1].startswith("title = {{Nested")
    assert result[2].startswith("doi = {10.1175")
    assert result[3].startswith("pages = {2173")
    assert result[4] == "number = {9}"
    assert result[5] == "volume = {47}"

    # Check no fields are missing or corrupted
    for field in result:
        assert "=" in field
        assert field.count("{") == field.count(
            "}"
        ), f"Unmatched braces in field: {field}"


def assert_braces_balanced(text: str, context: str = ""):
    """
    Assert that the number of opening and closing braces in `text` is equal.

    Parameters
    ----------
    text : str
        The string to check for brace balance.
    context : str, optional
        Extra context to include in error message (e.g., entry key or field).
    """
    open_braces = text.count("{")
    close_braces = text.count("}")
    assert open_braces == close_braces, (
        f"Brace mismatch{f' in {context}' if context else ''}: "
        f"open={{ {open_braces} }}, close={{ {close_braces} }}\n{text}"
    )
