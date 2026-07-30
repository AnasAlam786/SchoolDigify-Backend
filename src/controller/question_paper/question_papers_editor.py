# src/controller/tools/question_papers_editor.py

from copy import deepcopy

from flask import session, render_template, request, Blueprint, jsonify, redirect, url_for
from sqlalchemy import or_
from src import db
from src.controller.permissions.has_permission import has_permission
from src.model.Papers import Papers
from src.controller.permissions.permission_required import permission_required
from src.controller.auth.login_required import login_required

question_papers_editor_bp = Blueprint('question_papers_editor_bp', __name__)


@question_papers_editor_bp.route('/question-papers/<int:paper_id>', methods=["GET"])
@login_required
@permission_required('create_paper')
def question_papers_editor(paper_id):
    """Load the question paper editor for a specific paper"""
    
    user_id = session.get('user_id')
    
    # Fetch the paper
    paper = Papers.query.filter_by(id=paper_id, user_id=user_id).filter(or_(Papers.status != 'deleted', Papers.status.is_(None))).first()
    
    if not paper:
        return redirect(url_for('question_papers_dashboard_bp.question_papers_dashboard'))
    
    return render_template('question_paper/question_papers_editor.html', paper=paper)


@question_papers_editor_bp.route('/question-papers/api/create', methods=["POST"])
@login_required
@permission_required('create_paper')
def create_paper():
    """Create a new question paper and return redirect to editor"""
    
    user_id = session.get('user_id')
    school_id = session.get('school_id')
    
    data = request.json
    
    # Validate required fields
    required_fields = ['event', 'subject', 'class_name', 'marks', 'duration']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        # Prepare the paper data with meta information
        paper_data = {
            'meta': {
                'event': data['event'].strip(),
                'subject': data['subject'].strip(),
                'std': data['class_name'].strip(),
                'hrs': data['duration'].strip(),
                'MM': str(data['marks']),
                'fontSize': 20
            },
            'questions': []
        }
        
        # Create new paper with meta and empty questions
        new_paper = Papers(
            user_id=user_id,
            session_id=session.get('session_id'),
            school_id=school_id,            
            event=data['event'].strip(),
            subject=data['subject'].strip(),
            class_name=data['class_name'].strip(),
            marks=int(data['marks']),
            duration=data['duration'].strip(),
            paper_data=paper_data
        )
        
        db.session.add(new_paper)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'paper_id': new_paper.id,
            'redirect': url_for('question_papers_editor_bp.question_papers_editor', paper_id=new_paper.id)
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@question_papers_editor_bp.route('/api/update-paper/<int:paper_id>/', methods=["POST"])
@login_required
@permission_required('create_paper')
def update_paper(paper_id):
    """Update question paper data"""
    
    user_id = session.get('user_id')
    
    paper = Papers.query.filter_by(id=paper_id, user_id=user_id).filter(or_(Papers.status != 'deleted', Papers.status.is_(None))).first()
    
    if not paper:
        return jsonify({'error': 'Paper not found'}), 404
    
    data = request.json
    
    try:
        # Update metadata if provided
        if 'event' in data:
            paper.event = data['event'].strip()
        if 'subject' in data:
            paper.subject = data['subject'].strip()
        if 'class_name' in data:
            paper.class_name = data['class_name'].strip()
        if 'marks' in data:
            try:
                paper.marks = int(data['marks']) if data['marks'] else None
            except (ValueError, TypeError):
                paper.marks = None
        if 'duration' in data:
            paper.duration = data['duration'].strip() if data['duration'] else None
        
        # Update questions and prepare paper_data with meta information
        if 'questions' in data:
            paper_data = {
                'meta': {
                    'event': paper.event,
                    'subject': paper.subject,
                    'std': paper.class_name,
                    'hrs': paper.duration,
                    'MM': str(paper.marks) if paper.marks else '',
                    'fontSize': 20
                },
                'questions': data.get('questions', [])
            }
            paper.paper_data = paper_data
        else:
            # If no questions provided, just update metadata
            if not paper.paper_data:
                paper.paper_data = {}
            
            if 'meta' not in paper.paper_data:
                paper.paper_data['meta'] = {}
            
            paper.paper_data['meta'].update({
                'event': paper.event,
                'subject': paper.subject,
                'std': paper.class_name,
                'hrs': paper.duration,
                'MM': str(paper.marks) if paper.marks else '',
                'fontSize': 20
            })
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Paper updated successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@question_papers_editor_bp.route('/api/delete-paper/<int:paper_id>', methods=["POST"])
@login_required
@permission_required('create_paper')
def delete_paper(paper_id):
    """Soft delete a question paper by marking status as deleted"""
    
    user_id = session.get('user_id')
    
    paper = Papers.query.filter(
        Papers.id == paper_id,
        or_(Papers.status != "deleted", Papers.status.is_(None))
    ).first()    

    if not paper:
        return jsonify({'error': 'Paper not found'}), 404
    
    # Allow deletion if owner or has view_all_papers permission
    if paper.user_id != user_id and not has_permission('view_all_papers'):
        return jsonify({'error': 'Paper not found'}), 404
    
    try:
        paper.status = 'deleted'
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Paper deleted successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@question_papers_editor_bp.route('/api/duplicate-paper/<int:paper_id>', methods=["POST"])
@login_required
@permission_required('view_all_papers')
def duplicate_paper(paper_id):
    """
    Duplicate an existing question paper.

    Rules:
    - A user can duplicate their own papers.
    - Users with 'view_all_papers' permission can duplicate any paper.
    """

    user_id = session.get("user_id")

    try:
        # Get the original paper (ignore deleted papers)
        original_paper = (
            Papers.query
            .filter(
                Papers.id == paper_id,
                or_(Papers.status != "deleted", Papers.status.is_(None))
            )
            .first()
        )

        if original_paper is None:
            return jsonify({
                "error": "Paper not found."
            }), 404

        # Permission check
        can_duplicate = (
            original_paper.user_id == user_id or
            has_permission("view_all_papers")
        )

        if not can_duplicate:
            return jsonify({
                "error": "You do not have permission to duplicate this paper."
            }), 403

        # Create duplicate
        duplicate = Papers(
            user_id=user_id,
            school_id=original_paper.school_id,
            session_id=original_paper.session_id,
            event=f"{original_paper.event} (Copy)",
            subject=original_paper.subject,
            class_name=original_paper.class_name,
            marks=original_paper.marks,
            duration=original_paper.duration,
            paper_data=deepcopy(original_paper.paper_data),
            status=None,
            cloned_from=original_paper.id
        )

        db.session.add(duplicate)
        db.session.commit()

        return jsonify({
            "message": "Paper duplicated successfully.",
            "paper_id": duplicate.id
        }), 200

    except Exception as e:
        db.session.rollback()

        return jsonify({
            "error": "Failed to duplicate paper."
        }), 500


@question_papers_editor_bp.route('/api/paper-data/<int:paper_id>', methods=["GET"])
@login_required
@permission_required('create_paper')
def get_paper_data(paper_id):
    """Get full paper data for editor"""
    
    user_id = session.get('user_id')
    
    paper = Papers.query.filter_by(id=paper_id, user_id=user_id).filter(or_(Papers.status != 'deleted', Papers.status.is_(None))).first()
    
    if not paper:
        return jsonify({'error': 'Paper not found'}), 404
    
    # Return the full paper_data object with meta information
    paper_data = paper.paper_data if paper.paper_data else {'questions': []}
    
    # Ensure meta object exists
    if 'meta' not in paper_data:
        paper_data['meta'] = {
            'event': paper.event,
            'subject': paper.subject,
            'std': paper.class_name,
            'hrs': paper.duration,
            'MM': paper.marks,
            'fontSize': 20
        }
    
    return jsonify({
        'id': paper.id,
        'event': paper.event,
        'subject': paper.subject,
        'class_name': paper.class_name,
        'marks': paper.marks,
        'duration': paper.duration,
        'paper_data': paper_data
    })
