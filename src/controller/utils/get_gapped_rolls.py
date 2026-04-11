from sqlalchemy import select
from src.model import StudentSessions
from src import db

def get_gapped_rolls(class_id, session_id):
    """
    Get the gapped (missing) roll numbers in a specific class and session,
    and the next available roll number (max + 1).

    Args:
        class_id (int): The ID of the class.
        session_id (int): The ID of the session.

    Returns:
        dict: A dictionary with 'gaped_rolls' (list of missing roll numbers)
              and 'next_roll' (the next available roll number).
    """
    # Query to get all roll numbers for the given class and session, ordered by roll
    query = (
        select(StudentSessions.ROLL)
        .where(
            StudentSessions.class_id == class_id,
            StudentSessions.session_id == session_id,
            StudentSessions.ROLL.isnot(None)
        )
        .order_by(StudentSessions.ROLL)
    )

    # Execute the query and get the list of rolls
    result = db.session.execute(query).scalars().all()
    rolls = list(result)

    if not rolls:
        # No rolls exist, so no gaps, next roll is 1
        return {
            'gapped_rolls': [],
            'next_roll': 1
        }

    # Find min and max roll
    max_roll = max(rolls)

    all_rolls = set(range(1, max_roll + 1))  # All rolls from 1 to max
    existing_rolls = set(rolls)              # Existing rolls
    gapped_rolls = sorted(all_rolls - existing_rolls)  # Missing roll

    # Next available roll
    next_roll = max_roll + 1


    return {
        'gapped_rolls': gapped_rolls,
        'next_roll': next_roll
    }