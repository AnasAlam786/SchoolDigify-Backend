from collections import defaultdict
from decimal import Decimal


ZERO = Decimal("0")


def as_decimal(value):
    if value is None:
        return ZERO
    return value if isinstance(value, Decimal) else Decimal(str(value))


def aggregate_fee_allocations(records):
    """Aggregate valid allocation rows by student and fee term."""
    transaction_allocations = defaultdict(lambda: ZERO)
    for record in records:
        transaction_id = getattr(record, "transaction_id", None)
        if transaction_id is not None:
            transaction_allocations[transaction_id] += as_decimal(record.paid_amount)

    totals = defaultdict(lambda: {
        "paid_amount": ZERO,
        "discount_amount": ZERO,
        "settled_amount": ZERO,
        "late_fee": ZERO,
        "payment_date": None,
        "transaction_no": None,
    })

    for record in records:
        key = (record.student_session_id, record.fee_session_id)
        total = totals[key]
        allocation = as_decimal(record.paid_amount)
        transaction_id = getattr(record, "transaction_id", None)
        discount_share = ZERO
        if transaction_id is not None:
            discount = as_decimal(getattr(record, "discount", None))
            transaction_paid_amount = getattr(record, "transaction_paid_amount", None)
            transaction_gross = (
                as_decimal(transaction_paid_amount) + discount
                if transaction_paid_amount is not None
                else transaction_allocations[transaction_id]
            )
            if transaction_gross > ZERO:
                discount_share = (
                    discount * allocation / transaction_gross
                )

        total["paid_amount"] += allocation - discount_share
        total["discount_amount"] += discount_share
        total["settled_amount"] += allocation
        total["late_fee"] += as_decimal(getattr(record, "late_fee", None))

        payment_date = getattr(record, "payment_date", None)
        if payment_date and (
            total["payment_date"] is None or payment_date > total["payment_date"]
        ):
            total["payment_date"] = payment_date
            total["transaction_no"] = getattr(record, "transaction_no", None)

    return totals


def calculate_fee_balance(obligatory_amount, allocation_totals=None):
    totals = allocation_totals or {}
    base_obligation = as_decimal(obligatory_amount)
    late_fee = as_decimal(totals.get("late_fee"))
    obligation = base_obligation + late_fee
    settled = as_decimal(totals.get("settled_amount"))
    remaining = obligation - settled

    if remaining < ZERO:
        status = "OVERPAID"
    elif remaining == ZERO:
        status = "PAID"
    elif settled > ZERO:
        status = "PARTIAL"
    else:
        status = "UNPAID"

    return {
        "obligatory_amount": base_obligation,
        "applicable_obligation": obligation,
        "paid_amount": as_decimal(totals.get("paid_amount")),
        "discount_amount": as_decimal(totals.get("discount_amount")),
        "settled_amount": settled,
        "late_fee": late_fee,
        "remaining_amount": remaining,
        "status": status,
    }


def json_money(value):
    return format(as_decimal(value), "f")