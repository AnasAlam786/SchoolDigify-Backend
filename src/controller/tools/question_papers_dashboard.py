# src/controller/tools/question_papers_dashboard.py

import re

from flask import session, render_template, Blueprint, jsonify
from sqlalchemy import or_
from src import db
from sqlalchemy.orm import joinedload
from src.controller.permissions.has_permission import has_permission
from src.model.Papers import Papers
from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

question_papers_dashboard_bp = Blueprint('question_papers_dashboard_bp', __name__)


@question_papers_dashboard_bp.route('/question-papers', methods=["GET"])
@login_required
@permission_required('create_paper')
def question_papers_dashboard():
    """Render the question papers dashboard.

    No data is fetched on the server side any more since the page uses
    an API call to load papers. The previous `papers` variable was never
    used in the template.
    """
    return render_template('question_paper/question_papers_dashboard.html')



def count_words(text):
    WORD_RE = re.compile(r'\b\w+\b')
    if not text:
        return 0
    return len(WORD_RE.findall(text))


def count_paper_words(questions):
    total = 0

    for q in questions:

        total += count_words(q.get("qText"))

        sub = q.get("subQuestion")
        if sub:
            for s in sub:

                if isinstance(s, str):
                    total += count_words(s)

                elif isinstance(s, dict):
                    total += count_words(s.get("text"))

                    opts = s.get("options")
                    if opts:
                        for opt in opts:
                            total += count_words(opt)

        opts = q.get("options")
        if opts:
            for opt in opts:
                total += count_words(opt)

    return total

@question_papers_dashboard_bp.route('/question-papers/api/list', methods=["GET"])
@login_required
@permission_required('create_paper')
def get_papers_list():


    user_id = session.get('user_id')
    school_id = session.get('school_id')
    session_id = session.get('session_id')

    user_papers = (
        Papers.query
        .options(joinedload(Papers.staff_data))
        .filter(Papers.user_id == user_id)
        .filter(or_(Papers.status != 'deleted', Papers.status.is_(None)))
        .order_by(Papers.created_at.desc())
        .all()
    )

    user_data = []

    for p in user_papers:

        paper_data = p.paper_data or {}
        questions = paper_data.get('questions', [])

        num_questions = len(questions)
        num_words = count_paper_words(questions)

        teacher_name = "Unknown"
        if p.staff_data:
            teacher_name = p.staff_data.Name

        user_data.append({
            'id': p.id,
            'event': p.event,
            'subject': p.subject,
            'class_name': p.class_name,
            'marks': p.marks,
            'duration': p.duration,
            'created_at': p.created_at.strftime('%d %b %Y, %I:%M %p'),
            'updated_at': p.updated_at.strftime('%d %b %Y, %I:%M %p'),
            'teacher_name': teacher_name,
            'num_questions': num_questions,
            'num_words': num_words,
        })

    session_data = []

    if has_permission('view_all_papers'):

        others = (
            Papers.query
            .options(joinedload(Papers.staff_data))
            .filter(
                Papers.school_id == school_id,
                Papers.session_id == session_id,
                Papers.user_id != user_id
            )
            .filter(or_(Papers.status != 'deleted', Papers.status.is_(None)))
            .order_by(Papers.created_at.desc())
            .all()
        )

        for p in others:

            paper_data = p.paper_data or {}
            questions = paper_data.get('questions', [])

            num_questions = len(questions)
            num_words = count_paper_words(questions)

            teacher_name = "Unknown"
            if p.staff_data:
                teacher_name = p.staff_data.Name

            session_data.append({
                'id': p.id,
                'event': p.event,
                'subject': p.subject,
                'class_name': p.class_name,
                'marks': p.marks,
                'duration': p.duration,
                'created_at': p.created_at.strftime('%d %b %Y, %I:%M %p'),
                'updated_at': p.updated_at.strftime('%d %b %Y, %I:%M %p'),
                'teacher_name': teacher_name,
                'num_questions': num_questions,
                'num_words': num_words,
            })


    return jsonify({
        'user_papers': user_data,
        'session_papers': session_data
    })



