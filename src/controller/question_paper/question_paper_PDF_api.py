# src/controller/tools/question_paper_PDF_api.py

from flask import session, render_template, request, jsonify, Blueprint
from sqlalchemy import or_
from src.controller.permissions.has_permission import has_permission
from src.model.Papers import Papers

from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

question_paper_PDF_api_bp = Blueprint('question_paper_PDF_api_bp', __name__)


@question_paper_PDF_api_bp.route('/api/question_paper_PDF', methods=["POST"])
@login_required
@permission_required('create_paper')
def question_paper_PDF():
    """Generate PDF content for question papers"""
    
    payload = request.json

    questions = payload.get('questions')
    event = payload.get('eventName')
    subject = payload.get('subject')
    std = payload.get('std')
    MM = payload.get('MM')
    hrs = payload.get('hrs')
    font_size = payload.get('fontSize')

    try:
        school = session["school_name"]
    except Exception as e:
        print(e)
        school = "School Name"

    # Render the paper template
    html = render_template('paper_elements.html', questions=questions, school=school, 
                            event=event, subject=subject, std=std, MM=MM, hrs=hrs, fontSize=font_size)
    return jsonify({"html": str(html)})




@question_paper_PDF_api_bp.route('/api/question-paper-PDF/<int:paper_id>', methods=["GET"])
@login_required
@permission_required('create_paper')
def question_paper_PDF_by_id(paper_id):
    """Generate PDF preview HTML for a question paper"""
    
    user_id = session.get('user_id')
    
    paper = Papers.query.filter_by(id=paper_id).filter(or_(Papers.status != 'deleted', Papers.status.is_(None))).first()
    
    if not paper:
        return jsonify({'error': 'Paper not found'}), 404

    # owners can always preview; others only if they have view_all_papers
    if paper.user_id != user_id and not has_permission('view_all_papers'):
        return jsonify({'error': 'Paper not found'}), 404

    try:
        school = session.get("school_name", "School Name")
        questions = paper.paper_data.get('questions', [])
        
        # read font size from query string if provided
        font_size = request.args.get('fontSize')
        
        html = render_template('paper_elements.html', 
                             questions=questions, 
                             school=school,
                             event=paper.event,
                             subject=paper.subject,
                             std=paper.class_name,
                             MM=paper.marks,
                             hrs=paper.duration,
                             fontSize=font_size)
                
        return jsonify({"html": str(html)})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
