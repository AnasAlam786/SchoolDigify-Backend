from src.model.FeeHeads import FeeHeads
from src.model.FeeStructure import FeeStructure
from src import db

def get_fee_structure(school_id):
    fee_structure = (
        db.session.query(
            FeeStructure.id,
            FeeStructure.fee_type_id,
            FeeStructure.period_name,
            FeeStructure.year_increment,
            FeeStructure.start_day,
            FeeStructure.start_month,
            FeeHeads.fee_type
        )
        .join(
            FeeHeads,
            FeeHeads.id == FeeStructure.fee_type_id
        )
        .filter(
            FeeStructure.school_id == school_id
        )
        .order_by(
            FeeStructure.sequence_number.asc()
        )
        .all()
    )

    return [
        {
            "id": fee.id,
            "fee_type_id": fee.fee_type_id,
            "fee_type": fee.fee_type,
            "period_name": fee.period_name,
            "year_increment": fee.year_increment,
            "start_day": fee.start_day,
            "start_month": fee.start_month
        }
        for fee in fee_structure
    ]
        
    