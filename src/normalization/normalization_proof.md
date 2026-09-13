# MedCorp Normalization Proof

## 1. Legacy relation and row grain

Let the original flat-file relation be:

```text
MEDCORP(
    Patient_ID,
    Patient_Name,
    Patient_DOB,
    Patient_Blood_Type,
    Appointment_Date,
    Doctor_ID,
    Doctor_Name,
    Doctor_Specialty,
    Doctor_Phone,
    Ward_ID,
    Ward_Location,
    Treatment_Code,
    Treatment_Description,
    Treatment_Cost
)
```

The reconstructed data contains 100,000 rows. Each row represents one treatment occurrence associated with a patient appointment, not necessarily one distinct appointment. The analysis found 99,999 unique combinations of:

```text
(Patient_ID, Appointment_Date, Doctor_ID, Ward_ID)
```

Adding `Treatment_Code` produced 100,000 unique combinations. Therefore, the natural key for a legacy treatment-occurrence row is:

```text
K = (Patient_ID, Appointment_Date, Doctor_ID, Ward_ID, Treatment_Code)
```

`Appointment_ID` was not present in the legacy file. It is a generated surrogate key assigned to each unique appointment grouping:

```text
(Patient_ID, Appointment_Date, Doctor_ID, Ward_ID)
```

The surrogate key is an implementation improvement, not a discovered attribute from the source data.

## 2. Functional dependencies

The following functional dependencies were supported by the reconstructed dataset and domain interpretation:

```text
Patient_ID     -> Patient_Name, Patient_DOB, Patient_Blood_Type
Doctor_ID      -> Doctor_Name, Doctor_Specialty, Doctor_Phone
Ward_ID        -> Ward_Location
Treatment_Code -> Treatment_Description, Treatment_Cost
```

The complete legacy key determines every attribute:

```text
K -> all attributes in MEDCORP
```

The observed dependency `Treatment_Cost -> Treatment_Code` was not used as a business rule. Although it held in this generated dataset, treatment cost should not be assumed to uniquely identify a treatment in a real hospital system.

## 3. 0NF to 1NF

The merger source is considered conceptually 0NF because it is a spreadsheet-style legacy dump with repeated groups of patient, doctor, ward, and treatment information. After treating each exported row as one record and ensuring that each field contains one atomic value, the reconstructed CSV is in 1NF.

### 1NF relation

```text
MEDCORP(K, Patient_Name, Patient_DOB, Patient_Blood_Type,
        Doctor_Name, Doctor_Specialty, Doctor_Phone,
        Ward_Location, Treatment_Description, Treatment_Cost)
```

where `K` is the five-attribute key defined above.

### Anomalies remaining

1NF makes values atomic, but it does not remove redundancy. The relation still has:

- Update anomalies: changing one doctor's phone requires changing many rows.
- Insertion anomalies: a new doctor or treatment cannot be stored without an appointment row.
- Deletion anomalies: deleting the last appointment involving a doctor, ward, or treatment can remove the only copy of that entity's information.

No major dependency anomaly is resolved merely by reaching 1NF; repeating information and partial dependencies remain.

## 4. 1NF to 2NF

2NF requires 1NF and requires every non-key attribute to depend on the entire composite key, not only part of it.

The legacy key is:

```text
K = (Patient_ID, Appointment_Date, Doctor_ID, Ward_ID, Treatment_Code)
```

The following are partial dependencies because their determinants are proper subsets of `K`:

```text
Patient_ID     -> Patient_Name, Patient_DOB, Patient_Blood_Type
Doctor_ID      -> Doctor_Name, Doctor_Specialty, Doctor_Phone
Ward_ID        -> Ward_Location
Treatment_Code -> Treatment_Description, Treatment_Cost
```

These dependencies mean that patient, doctor, ward, and treatment attributes do not depend on the entire legacy key.

### 2NF decomposition

```text
Patient(
    Patient_ID PK,
    Patient_Name,
    Patient_DOB,
    Patient_Blood_Type
)
```

```text
Doctor(
    Doctor_ID PK,
    Doctor_Name,
    Doctor_Specialty,
    Doctor_Phone
)
```

```text
Ward(
    Ward_ID PK,
    Ward_Location
)
```

```text
Treatment(
    Treatment_Code PK,
    Treatment_Description,
    Treatment_Cost
)
```

The remaining appointment-level relationship can first be represented using its natural key:

```text
Appointment(
    Patient_ID PK/FK,
    Appointment_Date PK,
    Doctor_ID PK/FK,
    Ward_ID PK/FK
)
```

```text
AppointmentTreatment(
    Patient_ID PK/FK,
    Appointment_Date PK/FK,
    Doctor_ID PK/FK,
    Ward_ID PK/FK,
    Treatment_Code PK/FK
)
```

In the implementation, the natural appointment key is replaced by the generated surrogate key:

```text
Appointment(
    Appointment_ID PK,
    Patient_ID FK,
    Doctor_ID FK,
    Ward_ID FK,
    Appointment_Date
)
```

```text
AppointmentTreatment(
    Appointment_ID PK/FK,
    Treatment_Code PK/FK
)
```

### Anomalies and dependencies resolved at 2NF

- Partial dependencies are removed by placing each determinant and its attributes in a separate relation.
- Update anomalies are reduced because patient, doctor, ward, and treatment data are changed once.
- Insertion anomalies are reduced because entities can be inserted independently of appointments.
- Deletion anomalies are reduced because deleting an appointment-treatment row does not delete the doctor, patient, ward, or treatment entity.

## 5. 2NF to 3NF

3NF requires 2NF and prohibits transitive dependencies in which a non-key attribute determines another non-key attribute.

In the original relation, dependencies such as the following were effectively transitive through the legacy key:

```text
K -> Doctor_ID -> Doctor_Name, Doctor_Specialty, Doctor_Phone
K -> Patient_ID -> Patient_Name, Patient_DOB, Patient_Blood_Type
K -> Ward_ID -> Ward_Location
K -> Treatment_Code -> Treatment_Description, Treatment_Cost
```

The 2NF decomposition removes these transitive chains from the appointment-treatment relation. Each non-key attribute now belongs to the relation whose key directly determines it.

### Anomalies and dependencies resolved at 3NF

- Transitive dependencies are removed from the relationship relation.
- Remaining update anomalies caused by indirect dependencies are eliminated.
- Entity facts are stored independently from appointment facts.

## 6. 3NF to BCNF

BCNF requires that for every nontrivial functional dependency:

```text
X -> Y
```

the determinant `X` must be a superkey of its relation.

### BCNF verification

| Relation | Relevant dependency | Determinant status | BCNF result |
|---|---|---|---|
| `Patient` | `Patient_ID -> patient attributes` | `Patient_ID` is PK | Satisfies BCNF |
| `Doctor` | `Doctor_ID -> doctor attributes` | `Doctor_ID` is PK | Satisfies BCNF |
| `Ward` | `Ward_ID -> Ward_Location` | `Ward_ID` is PK | Satisfies BCNF |
| `Treatment` | `Treatment_Code -> treatment attributes` | `Treatment_Code` is PK | Satisfies BCNF |
| `Appointment` | `Appointment_ID -> appointment attributes` | `Appointment_ID` is PK | Satisfies BCNF |
| `AppointmentTreatment` | `(Appointment_ID, Treatment_Code) -> no non-key attributes` | Composite PK is a superkey | Satisfies BCNF |

The `AppointmentTreatment` relation contains only foreign keys that together form its composite primary key. Since it has no non-key descriptive attributes, it has no partial or transitive dependency.

### Conclusion of the proof

The final schema is in BCNF under the stated functional dependencies and modeling assumptions. Each determinant is a candidate key or superkey of its relation, and descriptive attributes are stored only with the entity identifier that determines them.

## 7. Evidence from reconstruction

The generated files provide the following validation evidence:

```text
Patient:              19,893 rows
Doctor:                   50 rows
Ward:                     10 rows
Treatment:                50 rows
Appointment:          99,999 rows
AppointmentTreatment: 100,000 rows
```

The 100,000 bridge rows preserve every original legacy row while reducing the appointment entity to 99,999 unique appointment groupings. This confirms that the decomposition separates appointment identity from treatment occurrence without discarding source records.