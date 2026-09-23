from collections import OrderedDict, defaultdict
import re

from .calc_grades import get_grade


def to_float(value, default=0.0):
    if value in (None, "", "-"):
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_percentage(value, default=0.0):
    if value in (None, "", "-", "—"):
        return default

    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return default


def extract_term_number(term):
    match = re.search(r"(\d+)", str(term))
    return int(match.group(1)) if match else 0


def subject_order_from_records(records):
    order = []
    for record in records:
        subject_marks = record.get("subject_marks_dict")
        if not isinstance(subject_marks, dict):
            continue

        for subject in subject_marks.keys():
            if subject not in order:
                order.append(subject)

    return order


def sum_subject_marks(records):
    totals = OrderedDict()

    for record in records:
        subject_marks = record.get("subject_marks_dict")
        if not isinstance(subject_marks, dict):
            continue

        for subject, value in subject_marks.items():
            numeric_value = to_float(value, None)
            if numeric_value is None:
                continue

            totals.setdefault(subject, 0.0)
            totals[subject] += numeric_value

    return totals


def ordered_subjects(subjects, preferred_order=None):
    ordered = OrderedDict()

    if preferred_order:
        for subject in preferred_order:
            if subject in subjects:
                ordered[subject] = subjects[subject]

    for subject, value in subjects.items():
        if subject not in ordered:
            ordered[subject] = value

    return ordered


def weighted_average_percentage(records):
    """Use the exam percentage already stored in the raw data as the source of truth."""
    weighted_total = 0.0
    weight_total = 0.0

    for record in records:
        percentage = to_float(record.get("percentage"), None)
        if percentage is None:
            continue

        weightage = to_float(record.get("weightage"), 1.0)
        if weightage > 0:
            weighted_total += percentage * weightage
            weight_total += weightage
        else:
            weighted_total += percentage
            weight_total += 1.0

    if weight_total == 0:
        return 0.0

    return round(weighted_total / weight_total, 2)


def safe_exam_value(value):
    if value in (None, "", "-", "—"):
        return ""

    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def build_exam_payload(record, preferred_subject_order):
    percentage_raw = record.get("percentage")
    weightage_raw = record.get("weightage")

    return {
        "subject_marks_dict": ordered_subjects(
            record.get("subject_marks_dict", {}),
            preferred_subject_order,
        ),
        "exam_total": safe_exam_value(record.get("exam_total")),
        "percentage": to_percentage(percentage_raw, 0.0) if percentage_raw not in (None, "", "-", "—") else "",
        "weightage": weightage_raw if weightage_raw not in (None, "", "-") else "",
        "exam_term": record.get("exam_term"),
        "exam_display_order": record.get("exam_display_order", 0),
    }


def process_marks(student_marks_data, add_grand_total_flag=True, add_grades_flag=True):
    if not student_marks_data:
        return []

    records_by_student = defaultdict(list)
    for record in student_marks_data:
        records_by_student[record["student_id"]].append(dict(record))

    final_output = []

    for student_id, records in records_by_student.items():
        records.sort(
            key=lambda r: (
                extract_term_number(r.get("exam_term")),
                r.get("exam_display_order", 0),
            )
        )

        preferred_subject_order = subject_order_from_records(records)
        original_exam_names = {r["exam_name"] for r in records}
        processed = list(records)

        term_groups = defaultdict(list)
        for record in records:
            term_groups[record.get("exam_term")].append(record)

        for term in sorted(term_groups, key=extract_term_number):
            term_records = term_groups[term]
            total_subject_marks = ordered_subjects(
                sum_subject_marks(term_records),
                preferred_subject_order,
            )
            exam_total = round(sum(total_subject_marks.values()), 1)
            weightage_sum = sum(to_float(r.get("weightage"), 0.0) for r in term_records)
            percentage = weighted_average_percentage(term_records)

            base = dict(term_records[-1])
            base.update({
                "exam_name": f"{term} Total",
                "exam_total": exam_total,
                "weightage": weightage_sum,
                "percentage": percentage,
                "subject_marks_dict": total_subject_marks,
            })
            processed.append(base)

        if add_grand_total_flag:
            total_records = [r for r in processed if r["exam_name"] in original_exam_names]
            if total_records:
                total_subject_marks = ordered_subjects(
                    sum_subject_marks(total_records),
                    preferred_subject_order,
                )
                exam_total = round(sum(total_subject_marks.values()), 1)
                weightage_sum = sum(to_float(r.get("weightage"), 0.0) for r in total_records)
                percentage = weighted_average_percentage(total_records)

                base = dict(total_records[-1])
                base.update({
                    "exam_name": "G. Total",
                    "exam_total": exam_total,
                    "weightage": weightage_sum,
                    "percentage": percentage,
                    "subject_marks_dict": total_subject_marks,
                })
                processed.append(base)

        if add_grades_flag:
            grade_records = [r for r in processed if r["exam_name"] in original_exam_names]
            if grade_records:
                total_percentage = weighted_average_percentage(grade_records)
                grade, _ = get_grade(total_percentage)

                subject_totals = ordered_subjects(
                    sum_subject_marks(grade_records),
                    preferred_subject_order,
                )

                base = dict(grade_records[-1])
                base.update({
                    "exam_name": "Grades",
                    "exam_total": grade,
                    "weightage": "",
                    "percentage": "-",
                    "subject_marks_dict": OrderedDict((subject, grade) for subject in subject_totals),
                })
                processed.append(base)

        def exam_priority(record):
            name = record["exam_name"]
            if name == "Grades":
                return 3
            if name == "G. Total":
                return 2
            if name.endswith("Total"):
                return 1
            return 0

        processed.sort(
            key=lambda r: (
                extract_term_number(r.get("exam_term")),
                exam_priority(r),
                r.get("exam_display_order", 0),
            )
        )

        for idx, record in enumerate(processed, start=1):
            record["exam_display_order"] = idx

        ordered_exams = OrderedDict()
        ordered_exam_names = []

        for record in processed:
            exam_name = record["exam_name"]
            ordered_exams[exam_name] = build_exam_payload(record, preferred_subject_order)
            ordered_exam_names.append(exam_name)

        base_info = {
            key: value for key, value in processed[0].items()
            if key not in {
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
        base_info["exam_order"] = ordered_exam_names
        base_info["subject_order"] = preferred_subject_order
        final_output.append(base_info)

    final_output.sort(key=lambda r: (r.get("CLASS"), r.get("ROLL")))

    return final_output
