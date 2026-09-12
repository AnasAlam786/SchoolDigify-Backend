# src/controller/utils/verhoeff.py

def is_valid_aadhaar(aadhaar_number: str) -> bool:
    """
    Validates a 12-digit Aadhaar number using the Verhoeff algorithm.

    Args:
        aadhaar_number (str): Aadhaar number as a string. Can include hyphens or spaces.

    Returns:
        bool: True if the Aadhaar number is valid, False otherwise.
    """

    # Remove non-digit characters like hyphens or spaces
    aadhaar_number = ''.join(filter(str.isdigit, aadhaar_number))

    if len(aadhaar_number) != 12:
        return False

    # Verhoeff multiplication table
    d_table = [
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
        [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
        [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
        [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
        [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
        [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
        [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
        [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
        [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
    ]

    # Verhoeff permutation table
    p_table = [
        [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
        [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
        [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
        [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
        [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
        [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
        [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]
    ]

    checksum = 0
    for i, digit in enumerate(reversed(aadhaar_number)):
        checksum = d_table[checksum][p_table[i % 8][int(digit)]]

    return checksum == 0

def make_aadhaar_clean(aadhaar: str):
    if not aadhaar:
        return None

    return aadhaar.replace('-', '').replace(' ', '').strip()


def is_masked_aadhaar(aadhaar: str) -> bool:
    """
    Checks whether the cleaned Aadhaar is masked and contains
    exactly 4 visible digits.
    
    Examples:
        XXXX-XXXX-1234 -> False after cleaning
        ********1234   -> True
        **** **** 1234 -> True
    """
    if not aadhaar:
        return False

    digits = ''.join(filter(str.isdigit, aadhaar))

    return '*' in aadhaar and len(digits) == 4


def verify_aadhaar(aadhaar: str):
    if not aadhaar:
        raise ValueError('There should be 12 digits in aadhaar number')

    # Clean formatting first
    clean_aadhaar = make_aadhaar_clean(aadhaar)

    if not clean_aadhaar:
        raise ValueError('There should be 12 digits in aadhaar number')

    # Check masked Aadhaar AFTER cleaning
    if is_masked_aadhaar(clean_aadhaar):
        return clean_aadhaar

    # Normal Aadhaar must contain exactly 12 digits
    if len(clean_aadhaar) != 12 or not clean_aadhaar.isdigit():
        raise ValueError('There should be 12 digits in aadhaar number')

    if is_valid_aadhaar(clean_aadhaar):
        return clean_aadhaar

    raise ValueError('Invalid Aadhaar Number')