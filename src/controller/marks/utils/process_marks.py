from collections import OrderedDict, defaultdict
import re
from .calc_grades import get_grade


# -------------------------------
# Utility: Safe subject summation
# -------------------------------

def sum_subject_marks(records):
    totals = OrderedDict()

    for record in records:
        subj_dict = record.get("subject_marks_dict")
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
# Utility: Extract numeric term
# -------------------------------

def extract_term_number(term):
    match = re.search(r"(\d+)", str(term))
    return int(match.group(1)) if match else 0



def process_marks(
    student_marks_data,
    add_grand_total_flag=True,
    add_grades_flag=True,
):

    if not student_marks_data:
        return []

    # -----------------------------------
    # 1. Group records by student_id
    # -----------------------------------

    students = defaultdict(list)

    for record in student_marks_data:
        students[record["student_id"]].append(dict(record))  # shallow copy

    final_output = []

    # -----------------------------------
    # 2. Process each student separately
    # -----------------------------------

    for student_id, records in students.items():

        # Sort by term number + exam_display_order
        records.sort(
            key=lambda r: (
                extract_term_number(r.get("exam_term")),
                r.get("exam_display_order", 0),
            )
        )

        original_exam_names = {r["exam_name"] for r in records}
        processed = list(records)

        # ===================================
        # 3. Add Term Totals
        # ===================================

        term_groups = defaultdict(list)
        for r in records:
            term_groups[r.get("exam_term")].append(r)

        for term in sorted(term_groups, key=extract_term_number):

            term_records = term_groups[term]

            total_subject_marks = sum_subject_marks(term_records)
            weightage_sum = sum(
                float(r.get("weightage", 0) or 0)
                for r in term_records
            )

            subject_count = len(total_subject_marks)
            exam_total = sum(total_subject_marks.values())

            max_marks = weightage_sum * subject_count
            percentage = (
                (exam_total / max_marks) * 100
                if max_marks > 0 else 0
            )

            base = dict(term_records[-1])

            base.update({
                "exam_name": f"{term} Total",
                "exam_total": round(exam_total, 1),
                "weightage": weightage_sum,
                "percentage": round(percentage, 1),
                "subject_marks_dict": total_subject_marks,
            })

            processed.append(base)

        # ===================================
        # 4. Add Grand Total (BEFORE Grades)
        # ===================================

        if add_grand_total_flag:

            total_records = [
                r for r in processed
                if r["exam_name"] in original_exam_names
            ]

            if total_records:

                total_subject_marks = sum_subject_marks(total_records)
                weightage_sum = sum(
                    float(r.get("weightage", 0) or 0)
                    for r in total_records
                )

                subject_count = len(total_subject_marks)
                exam_total = sum(total_subject_marks.values())

                max_marks = weightage_sum * subject_count
                percentage = (
                    (exam_total / max_marks) * 100
                    if max_marks > 0 else 0
                )

                base = dict(total_records[-1])

                base.update({
                    "exam_name": "G. Total",
                    "exam_total": round(exam_total, 1),
                    "weightage": weightage_sum,
                    "percentage": round(percentage, 1),
                    "subject_marks_dict": total_subject_marks,
                })

                processed.append(base)

        # ===================================
        # 5. Add Grades (ALWAYS LAST)
        # ===================================

        if add_grades_flag:

            grade_records = [
                r for r in processed
                if r["exam_name"] in original_exam_names
            ]

            if grade_records:

                subject_totals = sum_subject_marks(grade_records)

                weightage_sum = sum(
                    float(r.get("weightage", 0) or 0)
                    for r in grade_records
                )

                subject_grades = OrderedDict()

                for subj, total in subject_totals.items():

                    percentage = (
                        (total / weightage_sum) * 100
                        if weightage_sum > 0 else 0
                    )

                    grade, _ = get_grade(percentage)
                    subject_grades[subj] = grade

                subject_count = len(subject_grades)
                max_total = weightage_sum * subject_count

                total_percentage = (
                    (sum(subject_totals.values()) / max_total) * 100
                    if max_total > 0 else 0
                )

                grade, _ = get_grade(total_percentage)

                base = dict(grade_records[-1])

                base.update({
                    "exam_name": "Grades",
                    "exam_total": grade,
                    "weightage": "",
                    "percentage": 0,
                    "subject_marks_dict": subject_grades,
                })

                processed.append(base)

        # ===================================
        # 6. Final Ordering Logic
        # ===================================

        def exam_priority(r):
            """
            Ensures order:
            1. Regular Exams
            2. Term Totals
            3. Grand Total
            4. Grades (always last)
            """
            name = r["exam_name"]

            if name == "Grades":
                return 3
            elif name == "G. Total":
                return 2
            elif name.endswith("Total"):
                return 1
            else:
                return 0

        processed.sort(
            key=lambda r: (
                extract_term_number(r.get("exam_term")),
                exam_priority(r),
                r.get("exam_display_order", 0),
            )
        )

        # Fresh display order
        for idx, r in enumerate(processed, start=1):
            r["exam_display_order"] = idx

        # ===================================
        # 7. Build Final Output Structure
        # ===================================

        ordered_exams = OrderedDict()

        for r in processed:
            ordered_exams[r["exam_name"]] = {
                "subject_marks_dict": r["subject_marks_dict"],
                "exam_total": r["exam_total"],
                "percentage": round(float(r["percentage"]), 2),
                "weightage": int(r["weightage"]) if r["weightage"] else "",
                "exam_term": r["exam_term"],
            }

        base_info = {
            k: v for k, v in processed[0].items()
            if k not in {
                "exam_name",
                "subject_marks_dict",
                "exam_total",
                "percentage",
                "weightage",
                "exam_display_order",
                "exam_term",
            }
        }

        base_info["marks"] = ordered_exams
        final_output.append(base_info)

    # ===================================
    # 8. Sort Students by CLASS + ROLL
    # ===================================

    final_output.sort(
        key=lambda r: (r.get("CLASS"), r.get("ROLL"))
    )

    return final_output