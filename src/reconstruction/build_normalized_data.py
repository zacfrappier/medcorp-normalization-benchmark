#!/usr/bin/env python3
"""Reconstruct normalized MedCorp data from the ordered legacy CSV.

The source CSV contains one row per appointment-treatment occurrence. This
script preserves source order, assigns a generated AppointmentID to each
unique appointment, and writes the BCNF-oriented entity files.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import OrderedDict
from pathlib import Path


REQUIRED_COLUMNS = {
    "Patient_ID",
    "Patient_Name",
    "Patient_DOB",
    "Patient_Blood_Type",
    "Appointment_Date",
    "Doctor_ID",
    "Doctor_Name",
    "Doctor_Specialty",
    "Doctor_Phone",
    "Ward_ID",
    "Ward_Location",
    "Treatment_Code",
    "Treatment_Description",
    "Treatment_Cost",
}


def clean(value: str | None) -> str:
    return (value or "").strip()


def read_legacy_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError("The source CSV does not contain headers.")

        headers = {header.strip() for header in reader.fieldnames}
        missing = REQUIRED_COLUMNS - headers

        if missing:
            raise ValueError(
                "The source CSV is missing columns: "
                + ", ".join(sorted(missing))
            )

        rows = []
        for line_number, row in enumerate(reader, start=2):
            cleaned_row = {
                header.strip(): clean(value)
                for header, value in row.items()
                if header is not None
            }

            missing_values = [
                column
                for column in REQUIRED_COLUMNS
                if not cleaned_row.get(column)
            ]

            if missing_values:
                raise ValueError(
                    f"Row {line_number} has missing values in: "
                    + ", ".join(sorted(missing_values))
                )

            rows.append(cleaned_row)

    return rows


def add_consistent_entity(
    entities: OrderedDict,
    key: str,
    record: dict[str, str],
    entity_name: str,
) -> None:
    """Add an entity once and reject contradictory repeated attributes."""
    if key not in entities:
        entities[key] = record
        return

    existing = entities[key]
    if existing != record:
        differences = [
            field
            for field in record
            if existing.get(field) != record.get(field)
        ]
        raise ValueError(
            f"Contradictory {entity_name} data for {key}: "
            + ", ".join(differences)
        )


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def reconstruct(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    patients = OrderedDict()
    doctors = OrderedDict()
    wards = OrderedDict()
    treatments = OrderedDict()
    appointments = OrderedDict()
    appointment_treatments = []
    seen_appointment_treatments = set()

    for row in rows:
        patient_id = row["Patient_ID"]
        doctor_id = row["Doctor_ID"]
        ward_id = row["Ward_ID"]
        treatment_code = row["Treatment_Code"]

        appointment_key = (
            patient_id,
            row["Appointment_Date"],
            doctor_id,
            ward_id,
        )

        if appointment_key not in appointments:
            appointment_id = f"A{len(appointments) + 1:06d}"
            appointments[appointment_key] = {
                "Appointment_ID": appointment_id,
                "Patient_ID": patient_id,
                "Doctor_ID": doctor_id,
                "Ward_ID": ward_id,
                "Appointment_Date": row["Appointment_Date"],
            }
        else:
            appointment_id = appointments[appointment_key]["Appointment_ID"]

        add_consistent_entity(
            patients,
            patient_id,
            {
                "Patient_ID": patient_id,
                "Patient_Name": row["Patient_Name"],
                "Patient_DOB": row["Patient_DOB"],
                "Patient_Blood_Type": row["Patient_Blood_Type"],
            },
            "patient",
        )

        add_consistent_entity(
            doctors,
            doctor_id,
            {
                "Doctor_ID": doctor_id,
                "Doctor_Name": row["Doctor_Name"],
                "Doctor_Specialty": row["Doctor_Specialty"],
                "Doctor_Phone": row["Doctor_Phone"],
            },
            "doctor",
        )

        add_consistent_entity(
            wards,
            ward_id,
            {
                "Ward_ID": ward_id,
                "Ward_Location": row["Ward_Location"],
            },
            "ward",
        )

        add_consistent_entity(
            treatments,
            treatment_code,
            {
                "Treatment_Code": treatment_code,
                "Treatment_Description": row["Treatment_Description"],
                "Treatment_Cost": row["Treatment_Cost"],
            },
            "treatment",
        )

        bridge_key = (appointment_id, treatment_code)
        if bridge_key in seen_appointment_treatments:
            raise ValueError(
                "Duplicate appointment-treatment pair detected: "
                f"{appointment_id}, {treatment_code}"
            )

        seen_appointment_treatments.add(bridge_key)
        appointment_treatments.append(
            {
                "Appointment_ID": appointment_id,
                "Treatment_Code": treatment_code,
            }
        )

    return {
        "Patient": list(patients.values()),
        "Doctor": list(doctors.values()),
        "Ward": list(wards.values()),
        "Treatment": list(treatments.values()),
        "Appointment": list(appointments.values()),
        "AppointmentTreatment": appointment_treatments,
    }


def write_outputs(output_dir: Path, normalized: dict[str, list[dict[str, str]]]) -> None:
    schemas = {
        "Patient": [
            "Patient_ID",
            "Patient_Name",
            "Patient_DOB",
            "Patient_Blood_Type",
        ],
        "Doctor": [
            "Doctor_ID",
            "Doctor_Name",
            "Doctor_Specialty",
            "Doctor_Phone",
        ],
        "Ward": ["Ward_ID", "Ward_Location"],
        "Treatment": [
            "Treatment_Code",
            "Treatment_Description",
            "Treatment_Cost",
        ],
        "Appointment": [
            "Appointment_ID",
            "Patient_ID",
            "Doctor_ID",
            "Ward_ID",
            "Appointment_Date",
        ],
        "AppointmentTreatment": [
            "Appointment_ID",
            "Treatment_Code",
        ],
    }

    output_dir.mkdir(parents=True, exist_ok=True)

    for entity_name, fieldnames in schemas.items():
        write_csv(
            output_dir / f"{entity_name}.csv",
            fieldnames,
            normalized[entity_name],
        )

    manifest = {
        "description": "Normalized MedCorp data reconstructed from the ordered legacy dump.",
        "counts": {
            entity_name: len(entity_rows)
            for entity_name, entity_rows in normalized.items()
        },
        "appointment_natural_key": [
            "Patient_ID",
            "Appointment_Date",
            "Doctor_ID",
            "Ward_ID",
        ],
        "generated_key": "Appointment_ID",
    }

    with (output_dir / "reconstruction_manifest.json").open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(manifest, file, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reconstruct normalized MedCorp entity files."
    )
    parser.add_argument(
        "source_csv",
        type=Path,
        help="Path to medcorp_legacy_dump.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/generated/normalized"),
        help="Directory for normalized CSV files",
    )
    args = parser.parse_args()

    if not args.source_csv.exists():
        parser.error(f"Source file not found: {args.source_csv}")

    try:
        print(f"Reading source: {args.source_csv}", flush=True)
        legacy_rows = read_legacy_csv(args.source_csv)
        print(f"Read {len(legacy_rows):,} legacy rows", flush=True)

        normalized = reconstruct(legacy_rows)
        write_outputs(args.output_dir, normalized)

        print("\nNormalized output counts:", flush=True)
        for entity_name, entity_rows in normalized.items():
            print(f"  {entity_name}: {len(entity_rows):,}", flush=True)

        print(f"\nWrote files to: {args.output_dir}", flush=True)

    except (OSError, csv.Error, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
