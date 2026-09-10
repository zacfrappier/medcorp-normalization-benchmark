# MedCorp Legacy Database Normalization and Benchmarking

## Purpose

This repository contains the implementation and research artifacts for a COMP 440 database assignment. The project reverse-engineers a heavily denormalized MedCorp legacy hospital dataset, derives a relational design normalized to Boyce-Codd Normal Form (BCNF), and measures the practical trade-offs introduced by decomposition.

The project combines relational-database theory with reproducible Python experiments. It will document the functional dependencies and normalization decisions, define the resulting ERD and relational schema, compare legacy and normalized query behavior, generate benchmark visuals, and support an IEEE/ACM-style research paper prepared in Overleaf.

## Important Dataset Context

The files previously uploaded as “CSV split files” are actually PDFs exported from the original source file. They should not be interpreted as clean, independent CSV datasets.

The original MedCorp dataset is one ordered legacy dump. The apparent odd/even split files are only portions of that ordered dump, not separate relations or independently modeled tables. Their ordering, repeated values, blank fields, and page/export artifacts must be preserved and interpreted carefully during reconstruction. Any CSV files generated later should be treated as derived working copies and validated against the original ordered source.

## Project Goals

1. Reconstruct the legacy relation from the exported source material.
2. Identify attributes, candidate keys, functional dependencies, and update/insert/delete anomalies.
3. Decompose the legacy relation into a lossless, dependency-aware BCNF design.
4. Produce an ERD and a documented relational schema with primary and foreign keys.
5. Implement reproducible Python benchmarks comparing the legacy and normalized designs.
6. Visualize storage, row counts, query latency, and join-cost trade-offs.
7. Prepare the final research paper and supporting tables/figures in Overleaf.

## Planned Repository Structure

```text
medcorp-bcnf-benchmark/
├── README.md
├── data/
│   ├── original/          # Original exported PDFs / source material
│   ├── reconstructed/     # Reconstructed ordered legacy data
│   └── generated/         # Derived benchmark data and database files
├── docs/
│   ├── erd/               # ERD source and exported diagram
│   ├── schema/            # Relational schema and assumptions
│   └── normalization/     # FDs, keys, decomposition, and BCNF proof
├── src/
│   ├── reconstruction/    # Source reconstruction and validation
│   ├── normalization/     # Schema creation and normalization logic
│   ├── benchmarks/        # Legacy/normalized benchmark experiments
│   ├── analysis/          # Future database-analysis scripts
│   └── visualization/     # Results figures and plotting scripts
├── results/
│   ├── tables/
│   └── figures/
├── paper/
│   ├── overleaf/          # LaTeX source, bibliography, and figures
│   └── submission/        # Final PDF and supplementary material
└── requirements.txt
```

## Reproducibility Notes

The reconstruction stage should run before normalization or benchmarking. Scripts should record their assumptions, input paths, row counts, rejected or ambiguous records, and output locations. Benchmark results should include the Python version, database engine, dataset scale, query definitions, repetition count, and whether indexes are enabled.

## Analysis Scripts

This section is intentionally reserved for the database-analysis scripts that will be added later.

### How to Run

<!-- Add commands here once the analysis scripts are implemented. -->
from src\analysis
python .\inspect_legacy_schema.py ..\..\data\original\medcorp_legacy_dump.pdf
### Script Overview

<!-- Add each script name, purpose, inputs, and outputs here. -->

## Benchmark Method

The benchmark will compare equivalent operations over the reconstructed legacy relation and the normalized BCNF relations. Planned measurements include query execution time, join count, row counts, storage size, and the effect of indexes. Each experiment should be repeated multiple times and summarized using median and spread, rather than relying on a single timing.

## Paper

The paper will discuss Codd’s relational model, the MedCorp reconstruction assumptions, functional dependencies, BCNF decomposition, implementation methodology, benchmark results, limitations, and the normalization-versus-performance trade-off. The `paper/overleaf/` directory will contain the source used to build the final submission.

## Status

Repository initialization and project documentation are in progress. Schema, ERD, normalization proof, benchmark implementation, visualizations, and the Overleaf manuscript will be added incrementally as the legacy dump is reconstructed and validated.
