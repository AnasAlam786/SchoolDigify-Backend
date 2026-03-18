# src/controller/utils/calc_grades.py
# Used in --> show_marks_api.py
# Used in --> report_card_api.py

from typing import Tuple, Union

def get_grade(score: Union[int, float]) -> Tuple[str, str]:
    """
    Returns a grade and its description based on the score.

    Parameters:
        score (int | float): A numerical score between 0 and 100.

    Returns:
        tuple: A tuple containing the grade (str) and a description (str).

    Raises:
        ValueError: If the score is not a number or is outside the range 0–100.
    """
    try:
        score = float(score)
    except (ValueError, TypeError):
        raise ValueError(f"Score must be a number (int, float, decimal, or numeric string). {type(score)} given.")

    if not (0 <= score <= 100):
        raise ValueError(f"Score must be between 0 and 100. {score} given.")

    if score >= 80:
        return "A", "Excellent"
    elif score >= 60:
        return "B", "Very Good"
    elif score >= 45:
        return "C", "Good"
    elif score >= 33:
        return "D", "Satisfactory"
    else:
        return "E", "Needs Improvement"
