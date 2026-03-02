# src/controller/marks/utils/process_marks.py

from collections import OrderedDict
import pandas as pd
import re
from .calc_grades import get_grade


# -------------------------------
# Utility: Safe subject summation
# -------------------------------

def sum_subject_marks(df):
    totals = OrderedDict()

    for subj_dict in df.get("subject_marks_dict", []):
        if not isinstance(subj_dict, dict):
            continue

        for subj, mark in subj_dict.items():
            try:
                mark = int(mark)
                totals[subj] = totals.get(subj, 0) + mark
            except (ValueError, TypeError):
                continue

    return totals


# -------------------------------
# Add Term Totals
# -------------------------------

def add_term_totals(group: pd.DataFrame) -> pd.DataFrame:
    group = group.copy()

    terms = group["exam_term"].dropna().unique()

    # Safe numeric sorting (handles int or "Term 1")
    def term_sort_key(term):
        match = re.search(r"(\d+)", str(term))
        return int(match.group(1)) if match else 0

    terms = sorted(terms, key=term_sort_key)

    new_rows = []

    for term in terms:
        term_df = group[group["exam_term"] == term]
        if term_df.empty:
            continue

        total_subject_marks = sum_subject_marks(term_df)

        base_row = term_df.iloc[0].copy()
        base_row["exam_name"] = f"{term} Total"
        base_row["exam_display_order"] = term_df["exam_display_order"].max() + 1
        base_row["exam_total"] = sum(total_subject_marks.values())
        base_row["weightage"] = pd.to_numeric(
            term_df["weightage"], errors="coerce"
        ).fillna(0).sum()
        base_row["subject_marks_dict"] = total_subject_marks

        subject_count = len(total_subject_marks)
        max_marks = base_row["weightage"] * subject_count

        base_row["percentage"] = (
            (base_row["exam_total"] / max_marks) * 100
            if max_marks > 0 else 0
        )

        new_rows.append(base_row)

    if new_rows:
        return pd.concat([group, pd.DataFrame(new_rows)], ignore_index=True)

    return group


# -------------------------------
# Add Grades
# -------------------------------

def add_grades(group: pd.DataFrame, exams) -> pd.DataFrame:
    group = group.copy()

    df = group[group["exam_name"].isin(exams)]
    if df.empty:
        return group

    subject_totals = sum_subject_marks(df)

    max_subject_marks = pd.to_numeric(
        df["weightage"], errors="coerce"
    ).fillna(0).sum()

    subject_grades = OrderedDict()

    for subj, total in subject_totals.items():
        percentage = (
            (total / max_subject_marks) * 100
            if max_subject_marks > 0 else 0
        )
        grade, _ = get_grade(percentage)
        subject_grades[subj] = grade

    base_row = df.iloc[0].copy()

    subject_count = len(subject_grades)
    max_total_marks = max_subject_marks * subject_count

    total_percentage = (
        (sum(subject_totals.values()) / max_total_marks) * 100
        if max_total_marks > 0 else 0
    )

    grade, _ = get_grade(total_percentage)

    base_row["exam_name"] = "Grades"
    base_row["exam_display_order"] = df["exam_display_order"].max() + 2
    base_row["exam_total"] = grade
    base_row["weightage"] = ""
    base_row["percentage"] = None
    base_row["subject_marks_dict"] = subject_grades

    return pd.concat([group, pd.DataFrame([base_row])], ignore_index=True)


# -------------------------------
# Add Grand Total
# -------------------------------

def add_grand_total(group: pd.DataFrame, exams) -> pd.DataFrame:
    group = group.copy()

    df = group[group["exam_name"].isin(exams)]
    if df.empty:
        return group

    total_subject_marks = sum_subject_marks(df)

    base_row = df.iloc[0].copy()

    base_row["exam_name"] = "G. Total"
    base_row["exam_display_order"] = df["exam_display_order"].max() + 1
    base_row["exam_total"] = sum(total_subject_marks.values())
    base_row["weightage"] = pd.to_numeric(
        df["weightage"], errors="coerce"
    ).fillna(0).sum()
    base_row["subject_marks_dict"] = total_subject_marks

    subject_count = len(total_subject_marks)
    max_marks = base_row["weightage"] * subject_count

    base_row["percentage"] = (
        (base_row["exam_total"] / max_marks) * 100
        if max_marks > 0 else 0
    )

    return pd.concat([group, pd.DataFrame([base_row])], ignore_index=True)


# -------------------------------
# Main Processor
# -------------------------------

def process_marks(
    student_marks_data,
    add_grades_flag=True,
    add_grand_total_flag=True,
):

    if not student_marks_data:
        return []

    student_marks_df = pd.DataFrame(student_marks_data)

    # Preserve original exams before mutation
    original_exams = set(student_marks_df["exam_name"].dropna().unique())

    # ---------------- Term Totals ----------------
    student_marks_df = (
        student_marks_df
        .groupby("student_id", group_keys=False)
        .apply(add_term_totals)
        .reset_index(drop=True)
    )

    # ---------------- Grades ----------------
    if add_grades_flag:
        student_marks_df = (
            student_marks_df
            .groupby("student_id", group_keys=False)
            .apply(lambda g: add_grades(g, original_exams))
            .reset_index(drop=True)
        )

    # ---------------- Grand Total ----------------
    if add_grand_total_flag:
        student_marks_df = (
            student_marks_df
            .groupby("student_id", group_keys=False)
            .apply(lambda g: add_grand_total(g, original_exams))
            .reset_index(drop=True)
        )

    # ---------------- Clean numeric columns ----------------

    student_marks_df["percentage"] = (
        pd.to_numeric(student_marks_df["percentage"], errors="coerce")
        .fillna(0)
        .round(1)
    )

    student_marks_df["exam_total"] = (
        pd.to_numeric(student_marks_df["exam_total"], errors="coerce")
        .fillna(0)
        .round(1)
    )

    # ---------------- Final Structuring ----------------

    non_common_columns = [
        "exam_name",
        "subject_marks_dict",
        "exam_total",
        "percentage",
        "exam_display_order",
        "weightage",
        "exam_term",
    ]

    common_columns = [
        col for col in student_marks_df.columns
        if col not in non_common_columns
    ]

    def exam_info_group(df):
        df_sorted = df.sort_values(
            "exam_display_order", na_position="last"
        )

        ordered_exams = OrderedDict()

        for _, row in df_sorted.iterrows():
            ordered_exams[row["exam_name"]] = {
                "subject_marks_dict": row["subject_marks_dict"],
                "exam_total": row["exam_total"],
                "percentage": row["percentage"],
                "weightage": row["weightage"],
                "exam_term": row["exam_term"],
            }

        return ordered_exams

    student_marks_df[common_columns] = (
        student_marks_df[common_columns].fillna("")
    )

    student_marks_df = (
        student_marks_df
        .groupby(common_columns, group_keys=False)
        .apply(exam_info_group)
        .reset_index(name="marks")
    )

    student_marks_df = (
        student_marks_df
        .sort_values(["CLASS", "ROLL"])
        .reset_index(drop=True)
    )

    return student_marks_df.to_dict(orient="records")



def process_marks2(students, add_grades=True, add_grand_total=True):
    for student in students:
        exams = student["marks"]

        add_term_totals(exams)

        if add_grades:
            add_grades_logic(exams)

        if add_grand_total:
            add_grand_total_logic(exams)

    return students