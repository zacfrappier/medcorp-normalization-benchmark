#!/usr/bin/env python3
"""Benchmark flat MedCorp records against normalized Python structures.

Measurements:
1. Approximate deep memory footprint.
2. Doctor-phone mutation time.
3. Reconstruction/read latency for records involving 1,000 patients.

This benchmark measures Python in-memory structures, not a SQL database.
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Callable


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def deep_size(value: Any, seen: set[int] | None = None) -> int:
    """Approximate recursive memory size of nested Python objects."""
    if seen is None:
        seen = set()

    object_id = id(value)
    if object_id in seen:
        return 0
    seen.add(object_id)

    size = sys.getsizeof(value)

    if isinstance(value, dict):
        size += sum(deep_size(key, seen) + deep_size(item, seen)
                    for key, item in value.items())
    elif isinstance(value, (list, tuple, set, frozenset)):
        size += sum(deep_size(item, seen) for item in value)

    return size


def megabytes(byte_count: int) -> float:
    return byte_count / (1024 * 1024)


def build_normalized_structure(
    patient_rows: list[dict[str, str]],
    doctor_rows: list[dict[str, str]],
    ward_rows: list[dict[str, str]],
    treatment_rows: list[dict[str, str]],
    appointment_rows: list[dict[str, str]],
    bridge_rows: list[dict[str, str]],
) -> dict[str, Any]:
    patients = {
        row["Patient_ID"]: row for row in patient_rows
    }
    doctors = {
        row["Doctor_ID"]: row for row in doctor_rows
    }
    wards = {
        row["Ward_ID"]: row for row in ward_rows
    }
    treatments = {
        row["Treatment_Code"]: row for row in treatment_rows
    }
    appointments = {
        row["Appointment_ID"]: row for row in appointment_rows
    }

    appointments_by_patient: dict[str, list[str]] = {}
    for appointment in appointment_rows:
        appointments_by_patient.setdefault(
            appointment["Patient_ID"], []
        ).append(appointment["Appointment_ID"])

    treatments_by_appointment: dict[str, list[str]] = {}
    for bridge in bridge_rows:
        treatments_by_appointment.setdefault(
            bridge["Appointment_ID"], []
        ).append(bridge["Treatment_Code"])

    return {
        "patients": patients,
        "doctors": doctors,
        "wards": wards,
        "treatments": treatments,
        "appointments": appointments,
        "appointment_treatments": bridge_rows,
        "appointments_by_patient": appointments_by_patient,
        "treatments_by_appointment": treatments_by_appointment,
    }


def time_repeated(
    operation: Callable[[], None],
    repetitions: int,
) -> list[float]:
    measurements = []

    for _ in range(repetitions):
        start = time.perf_counter_ns()
        operation()
        end = time.perf_counter_ns()
        measurements.append((end - start) / 1_000_000)

    return measurements


def median_and_mean(values: list[float]) -> tuple[float, float]:
    return statistics.median(values), statistics.mean(values)


def benchmark_mutation(
    flat_rows: list[dict[str, str]],
    normalized: dict[str, Any],
    doctor_id: str,
    repetitions: int,
) -> dict[str, float]:
    new_phone = "BENCHMARK-PHONE"
    original_flat_phones = {
        id(row): row["Doctor_Phone"]
        for row in flat_rows
        if row["Doctor_ID"] == doctor_id
    }
    original_normalized_phone = normalized["doctors"][doctor_id]["Doctor_Phone"]

    def mutate_flat() -> None:
        for row in flat_rows:
            if row["Doctor_ID"] == doctor_id:
                row["Doctor_Phone"] = new_phone

    def mutate_normalized() -> None:
        normalized["doctors"][doctor_id]["Doctor_Phone"] = new_phone

    flat_times = time_repeated(mutate_flat, repetitions)
    normalized_times = time_repeated(mutate_normalized, repetitions)

    for row in flat_rows:
        if id(row) in original_flat_phones:
            row["Doctor_Phone"] = original_flat_phones[id(row)]
    normalized["doctors"][doctor_id]["Doctor_Phone"] = original_normalized_phone

    flat_median, flat_mean = median_and_mean(flat_times)
    normalized_median, normalized_mean = median_and_mean(normalized_times)

    return {
        "flat_median_ms": flat_median,
        "flat_mean_ms": flat_mean,
        "normalized_median_ms": normalized_median,
        "normalized_mean_ms": normalized_mean,
    }


def benchmark_read(
    flat_rows: list[dict[str, str]],
    normalized: dict[str, Any],
    patient_ids: list[str],
    repetitions: int,
) -> dict[str, float | int]:
    selected_patients = set(patient_ids)

    def read_flat() -> None:
        records = [
            row for row in flat_rows
            if row["Patient_ID"] in selected_patients
        ]
        if not records:
            raise RuntimeError("Flat read returned no records.")

    def read_normalized() -> None:
        records = []
        for patient_id in patient_ids:
            patient = normalized["patients"].get(patient_id)
            if patient is None:
                continue

            for appointment_id in normalized["appointments_by_patient"].get(
                patient_id, []
            ):
                appointment = normalized["appointments"][appointment_id]
                doctor = normalized["doctors"][appointment["Doctor_ID"]]
                ward = normalized["wards"][appointment["Ward_ID"]]

                for treatment_code in normalized[
                    "treatments_by_appointment"
                ].get(appointment_id, []):
                    treatment = normalized["treatments"][treatment_code]
                    records.append(
                        (patient, appointment, doctor, ward, treatment)
                    )

        if not records:
            raise RuntimeError("Normalized read returned no records.")

    flat_times = time_repeated(read_flat, repetitions)
    normalized_times = time_repeated(read_normalized, repetitions)

    flat_median, flat_mean = median_and_mean(flat_times)
    normalized_median, normalized_mean = median_and_mean(normalized_times)

    return {
        "patient_count": len(patient_ids),
        "flat_median_ms": flat_median,
        "flat_mean_ms": flat_mean,
        "normalized_median_ms": normalized_median,
        "normalized_mean_ms": normalized_mean,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark flat and normalized MedCorp structures."
    )
    parser.add_argument("legacy_csv", type=Path)
    parser.add_argument("normalized_dir", type=Path)
    parser.add_argument("--doctor-id", default="D004")
    parser.add_argument("--patients", type=int, default=1000)
    parser.add_argument("--repetitions", type=int, default=30)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/tables/benchmark_results.json"),
    )
    args = parser.parse_args()

    required_files = [
        args.legacy_csv,
        args.normalized_dir / "Patient.csv",
        args.normalized_dir / "Doctor.csv",
        args.normalized_dir / "Ward.csv",
        args.normalized_dir / "Treatment.csv",
        args.normalized_dir / "Appointment.csv",
        args.normalized_dir / "AppointmentTreatment.csv",
    ]

    missing = [str(path) for path in required_files if not path.exists()]
    if missing:
        parser.error("Missing input files: " + ", ".join(missing))

    print("Loading flat legacy records...", flush=True)
    flat_rows = read_csv(args.legacy_csv)

    print("Loading normalized records...", flush=True)
    patient_rows = read_csv(args.normalized_dir / "Patient.csv")
    doctor_rows = read_csv(args.normalized_dir / "Doctor.csv")
    ward_rows = read_csv(args.normalized_dir / "Ward.csv")
    treatment_rows = read_csv(args.normalized_dir / "Treatment.csv")
    appointment_rows = read_csv(args.normalized_dir / "Appointment.csv")
    bridge_rows = read_csv(args.normalized_dir / "AppointmentTreatment.csv")

    normalized = build_normalized_structure(
        patient_rows,
        doctor_rows,
        ward_rows,
        treatment_rows,
        appointment_rows,
        bridge_rows,
    )

    if args.doctor_id not in normalized["doctors"]:
        parser.error(f"Doctor ID not found: {args.doctor_id}")

    patient_ids = list(normalized["patients"].keys())[:args.patients]
    if not patient_ids:
        parser.error("No patients available for the read benchmark.")

    print("Measuring memory...", flush=True)
    flat_memory_mb = megabytes(deep_size(flat_rows))
    normalized_memory_mb = megabytes(deep_size(normalized))

    gc.disable()
    print("Measuring doctor mutation...", flush=True)
    mutation = benchmark_mutation(
        flat_rows,
        normalized,
        args.doctor_id,
        args.repetitions,
    )

    print("Measuring 1,000-patient read/reconstruction...", flush=True)
    read = benchmark_read(
        flat_rows,
        normalized,
        patient_ids,
        args.repetitions,
    )
    gc.enable()

    result = {
        "dataset": {
            "flat_rows": len(flat_rows),
            "patients_read": len(patient_ids),
            "repetitions": args.repetitions,
            "doctor_id": args.doctor_id,
        },
        "memory_mb": {
            "flat": flat_memory_mb,
            "normalized": normalized_memory_mb,
        },
        "mutation_ms": mutation,
        "read_latency_ms": read,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as file:
        json.dump(result, file, indent=2)

    table_output = args.output.with_suffix(".csv")
    with table_output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["metric", "flat_legacy", "normalized", "unit"],
        )
        writer.writeheader()
        writer.writerows(
            [
                {
                    "metric": "Memory footprint",
                    "flat_legacy": result["memory_mb"]["flat"],
                    "normalized": result["memory_mb"]["normalized"],
                    "unit": "MB",
                },
                {
                    "metric": "Doctor phone mutation median",
                    "flat_legacy": result["mutation_ms"]["flat_median_ms"],
                    "normalized": result["mutation_ms"]["normalized_median_ms"],
                    "unit": "ms",
                },
                {
                    "metric": "1,000-patient read median",
                    "flat_legacy": result["read_latency_ms"]["flat_median_ms"],
                    "normalized": result["read_latency_ms"]["normalized_median_ms"],
                    "unit": "ms",
                },
            ]
        )

    print(json.dumps(result, indent=2))
    print(f"\nSaved benchmark results to: {args.output}")
    print(f"Saved benchmark table to: {table_output}")


if __name__ == "__main__":
    main()
