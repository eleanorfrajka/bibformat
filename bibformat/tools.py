import re
from pathlib import Path


def reformat_authors(authors_raw: str) -> str:
    """
    Convert 'Lastname, Firstname and Lastname, Firstname' into 'Firstname Lastname and Firstname Lastname'
    and ensure the result is a single line.
    """
    authors_raw = authors_raw.replace("\n", " ")
    authors = authors_raw.split(" and ")
    reformatted = [
        " ".join(name.split(", ")[::-1]).strip() if ", " in name else name.strip()
        for name in authors
    ]
    return " and ".join(reformatted)

def split_bib_fields(entry_body: str) -> list[str]:
    """
    Split BibTeX fields at top-level commas only, respecting nested braces.
    """
    fields = []
    current = []
    brace_level = 0
    i = 0
    length = len(entry_body)

    while i < length:
        char = entry_body[i]
        current.append(char)

        if char == '{':
            brace_level += 1
        elif char == '}':
            # Only decrease brace level if inside one
            if brace_level > 0:
                brace_level -= 1

        # Top-level comma: split only if not inside a field
        if char == ',' and brace_level == 0:
            field = "".join(current[:-1]).strip()
            if field:
                # Auto-trim unmatched closing braces
                open_count = field.count("{")
                close_count = field.count("}")
                if close_count > open_count:
                    # Trim extra closing braces from the end only
                    diff = close_count - open_count
                    for _ in range(diff):
                        if field.endswith("}"):
                            field = field[:-1].rstrip()
                fields.append(field)
            current = []

        i += 1

    # Final field
    final_field = "".join(current).strip()
    if final_field:
        fields.append(final_field)

    return fields


def reformat_bib_file(input_file, output_file=None):
    """
    Reformat a .bib file:
    - Removes fields: issn, abstract, paid, priced, local-url, pmcid
    - Formats each field on a new line, starting with ",\t"
    - Ensures author names are 'Firstname Lastname' on a single line
    - Ensures the closing brace is on its own line
    - Sorts entries by cite key
    """
    fields_to_remove = ["issn", "abstract", "paid", "priced", "local-url", "pmcid", "keywords"]
    bib_text = Path(input_file).read_text()

    def reformat_entry(entry):
        # Strip unwanted fields
        for field in fields_to_remove:
            entry = re.sub(rf",?\s*{field}\s*=\s*{{.*?}}\s*", "", entry, flags=re.DOTALL)

        # Normalize entry header
        entry = re.sub(r"(@\w+)\s*{", r"\1{", entry)
        key_match = re.match(r"(@\w+{([^,\n]+)),?", entry, flags=re.DOTALL)
        if not key_match:
            return None, entry.strip()

        key_line = key_match.group(1)
        cite_key = key_match.group(2).strip().replace("\n", " ")
        # Fix for stuff after doi
        rest = entry[key_match.end():].strip()

        # Remove trailing closing brace if it's on its own line
        if rest.endswith("}"):
            lines = rest.splitlines()
            if lines[-1].strip() == "}":
                rest = "\n".join(lines[:-1]).rstrip()
        fields = split_bib_fields(rest)

        formatted_fields = []
        for field in fields:
            if not field:
                continue
            if field.strip().startswith("author"):
                author_field = re.match(r"author\s*=\s*{(.*)}", field.strip(), re.DOTALL)
                if author_field:
                    new_author = reformat_authors(author_field.group(1))
                    formatted_fields.append(f",\tauthor = {{{new_author}}}")
                    continue
            formatted_fields.append(f",\t{field.strip()}")

        formatted_entry = f"{key_line}\n" + "\n".join(formatted_fields)
        # Fix unmatched braces if needed
        open_braces = formatted_entry.count("{")
        close_braces = formatted_entry.count("}")

        if close_braces < open_braces:
            formatted_entry += "\n}"
        elif close_braces > open_braces:
            # Strip excess closing braces
            while formatted_entry.endswith("}"):
                formatted_entry = formatted_entry[:-1].rstrip()


        assert formatted_entry.count("{") == formatted_entry.count("}"), \
            f"Unmatched braces in:\n{formatted_entry}"
        return cite_key, formatted_entry

    entries = re.split(r"\n(?=@\w+{)", bib_text)
    reformatted = [reformat_entry(entry) for entry in entries if entry.strip()]
    sorted_entries = sorted((e for e in reformatted if e[0]), key=lambda x: x[0].lower())
    result_text = "\n\n".join(entry for _, entry in sorted_entries)

    if not output_file:
        output_file = Path(input_file).with_name(Path(input_file).stem + "_reformatted.bib")
    Path(output_file).write_text(result_text)

    print(f"Reformatted and sorted .bib saved to: {output_file}")


# Optional CLI entry point:
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python reformat_bib.py <input_file.bib>")
    else:
        reformat_bib_file(sys.argv[1])
