#!/usr/bin/env python3
"""Profile a MedCorp legacy CSV or PDF before ERD and normalization work."""

from __future__ import annotations

import argparse
import csv
import itertools
import re
from collections import Counter
from pathlib import Path


MISSING = {"", "null", "none", "n/a", "na", "-", "unknown"}

def test_composite_key(
    rows: list[dict[str, str]],
    columns: tuple[str, ...],
) -> None:
    """Test whether a group of columns uniquely identifies each row."""

    combinations = [
        tuple(row[column] for column in columns)
        for row in rows
    ]

    counts = Counter(combinations)
    duplicate_groups = [
        key for key, count in counts.items()
        if count > 1
    ]

    print("\nCOMPOSITE KEY TEST")
    print("-" * 60)
    print(f"Columns tested: {', '.join(columns)}")
    print(f"Total rows: {len(rows):,}")
    print(f"Unique combinations: {len(counts):,}")
    print(f"Duplicate combinations: {len(duplicate_groups):,}")

    if not duplicate_groups:
        print("RESULT: This combination is unique in the dataset.")
    else:
        largest_duplicate = max(
            counts[key] for key in duplicate_groups
        )
        print(
            "RESULT: This combination is NOT unique."
        )
        print(
            f"Largest duplicate group: {largest_duplicate} rows"
        )

def normalize(value: str) -> str:
    return value.strip().lower()


def is_missing(value: str) -> bool:
    return normalize(value) in MISSING


def infer_type(values: list[str]) -> str:
    observed = [v.strip() for v in values if not is_missing(v)]

    if not observed:
        return "empty"

    integer_pattern = re.compile(r"^[+-]?\d+$")
    decimal_pattern = re.compile(r"^[+-]?(?:\d+\.\d*|\.\d+)$")
    date_pattern = re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}")

    if all(integer_pattern.match(v) for v in observed):
        return "integer"

    if all(
        integer_pattern.match(v) or decimal_pattern.match(v)
        for v in observed
    ):
        return "numeric"

    if all(date_pattern.match(v) for v in observed):
        return "date-like"

    if all(v.lower() in {"true", "false", "yes", "no"} for v in observed):
        return "boolean-like"

    return "text"


def display(value: str, limit: int = 40) -> str:
    value = value.replace("\n", " ").strip()

    if len(value) <= limit:
        return value

    return value[: limit - 3] + "..."


def load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Load a normal CSV file."""

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError("The CSV does not contain a header row.")

        original_headers = reader.fieldnames
        fieldnames = [header.strip() for header in original_headers]

        rows = []

        for row in reader:
            cleaned_row = {}

            for clean_header, original_header in zip(
                fieldnames, original_headers
            ):
                cleaned_row[clean_header] = (
                    row.get(original_header) or ""
                ).strip()

            rows.append(cleaned_row)

    return fieldnames, rows


def load_pdf(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Extract tables from the ordered MedCorp PDF dump."""

    try:
        import pdfplumber
    except ImportError as error:
        raise ValueError(
            "Install pdfplumber with: "
            "python -m pip install pdfplumber"
        ) from error

    extracted_rows = []

    print(f"Opening PDF: {path}", flush=True)

    with pdfplumber.open(path) as pdf:
        total_pages = len(pdf.pages)
        print(f"Total pages: {total_pages}", flush=True)

        for page_number, page in enumerate(pdf.pages, start=1):
            print(
                f"Processing page {page_number}/{total_pages}...",
                flush=True
            )

            tables = page.extract_tables()

            if not tables:
                print(
                    f"  No table detected on page {page_number}",
                    flush=True
                )
                continue

            print(
                f"  Found {len(tables)} table(s) on page {page_number}",
                flush=True
            )

            for table_number, table in enumerate(tables, start=1):
                print(
                    f"  Reading table {table_number}: "
                    f"{len(table)} rows",
                    flush=True
                )

                for raw_row in table:
                    cleaned_row = [
                        (cell or "").strip()
                        for cell in raw_row
                    ]

                    if any(cleaned_row):
                        extracted_rows.append(cleaned_row)

    print(
        f"Total extracted rows: {len(extracted_rows)}",
        flush=True
    )

    if len(extracted_rows) < 2:
        raise ValueError(
            "No usable table was detected in the PDF. "
            "The PDF may be scanned or may require text-based "
            "reconstruction instead of table extraction."
        )

    fieldnames = [
        header.strip()
        for header in extracted_rows[0]
    ]

    rows = []

    for raw_row in extracted_rows[1:]:
        cleaned_row = [
            cell.strip()
            for cell in raw_row
        ]

        if cleaned_row == fieldnames:
            continue

        if len(cleaned_row) < len(fieldnames):
            cleaned_row += [""] * (
                len(fieldnames) - len(cleaned_row)
            )

        if len(cleaned_row) > len(fieldnames):
            cleaned_row = cleaned_row[:len(fieldnames)]

        rows.append(dict(zip(fieldnames, cleaned_row)))

    return fieldnames, rows


def load_source(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Select the correct loader based on the file extension."""

    if path.suffix.lower() == ".csv":
        return load_csv(path)

    if path.suffix.lower() == ".pdf":
        return load_pdf(path)

    raise ValueError(
        "Unsupported file type. Provide a .csv or .pdf file."
    )


def fd_holds(
    rows: list[dict[str, str]],
    determinant: str,
    dependent: str,
) -> tuple[bool, int]:
    """Test whether determinant -> dependent appears to hold."""

    observed = {}
    violations = 0

    for row in rows:
        left_value = row[determinant]
        right_value = row[dependent]

        if is_missing(left_value) or is_missing(right_value):
            continue

        if (
            left_value in observed
            and observed[left_value] != right_value
        ):
            violations += 1
        else:
            observed[left_value] = right_value

    return violations == 0, violations


def likely_key(
    column: str,
    rows: list[dict[str, str]],
) -> bool:
    """Check whether one column behaves like a candidate key."""

    values = [row[column] for row in rows]

    return (
        bool(values)
        and all(not is_missing(value) for value in values)
        and len(set(values)) == len(values)
    )


def print_report(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, str]],
    top: int,
) -> None:
    print(f"FILE: {path}")
    print(f"ROWS: {len(rows):,}")
    print(f"COLUMNS: {len(fieldnames)}")

    complete_rows = {
        tuple(row[column] for column in fieldnames)
        for row in rows
    }

    duplicate_rows = len(rows) - len(complete_rows)

    print(f"DUPLICATE COMPLETE ROWS: {duplicate_rows:,}")

    print("\nCOLUMN PROFILE")
    print("-" * 90)
    print(
        f"{'Column':30} "
        f"{'Type':14} "
        f"{'Missing':>8} "
        f"{'Unique':>8}  "
        f"Examples"
    )
    print("-" * 90)

    for column in fieldnames:
        values = [row[column] for row in rows]
        nonmissing_values = [
            value
            for value in values
            if not is_missing(value)
        ]

        examples = ", ".join(
            display(value)
            for value, count in Counter(
                nonmissing_values
            ).most_common(top)
        )

        print(
            f"{column[:30]:30} "
            f"{infer_type(values):14} "
            f"{sum(is_missing(value) for value in values):8,} "
            f"{len(set(nonmissing_values)):8,}  "
            f"{examples}"
        )

    print("\nSINGLE-COLUMN CANDIDATE KEYS")

    candidates = [
        column
        for column in fieldnames
        if likely_key(column, rows)
    ]

    print(
        ", ".join(candidates)
        if candidates
        else "None detected"
    )

    appointment_key = (
    "Patient_ID",
    "Appointment_Date",
    "Doctor_ID",
    "Ward_ID",
)

    test_composite_key(rows, appointment_key)

    appointment_treatment_key = (
    "Patient_ID",
    "Appointment_Date",
    "Doctor_ID",
    "Ward_ID",
    "Treatment_Code",
)

    test_composite_key(rows, appointment_treatment_key)

    print("\nLIKELY FUNCTIONAL DEPENDENCIES")
    print(
        "These are candidates only. Confirm them using "
        "domain meaning and the dataset."
    )

    fd_candidates = []

    for determinant, dependent in itertools.permutations(
        fieldnames,
        2,
    ):
        holds, violations = fd_holds(
            rows,
            determinant,
            dependent,
        )

        determinant_values = {
            row[determinant]
            for row in rows
            if not is_missing(row[determinant])
        }

        if holds and len(determinant_values) < len(rows):
            fd_candidates.append(
                (
                    determinant,
                    dependent,
                    len(determinant_values),
                    violations,
                )
            )

    for determinant, dependent, count, violations in sorted(
        fd_candidates
    ):
        print(
            f"{determinant} -> {dependent} "
            f"({count:,} determinant values; "
            f"{violations} violations)"
        )

    print("\nSAMPLE ROWS")

    for row in rows[:3]:
        print(
            {
                column: display(row[column], 60)
                for column in fieldnames
            }
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Profile a MedCorp legacy CSV or exported PDF."
        )
    )

    parser.add_argument(
        "source_path",
        type=Path,
        help="Path to the MedCorp CSV or PDF",
    )

    parser.add_argument(
        "--top",
        type=int,
        default=3,
        help="Number of common examples shown per column",
    )

    args = parser.parse_args()

    if not args.source_path.exists():
        parser.error(
            f"File not found: {args.source_path}"
        )

    if args.top < 1:
        parser.error("--top must be at least 1")

    try:
        fieldnames, rows = load_source(args.source_path)

        print_report(
            args.source_path,
            fieldnames,
            rows,
            args.top,
        )

    except (
        OSError,
        UnicodeError,
        csv.Error,
        ValueError,
    ) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()