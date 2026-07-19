from datetime import date

from backend.application.services.domestic_fees import mainland_domestic_tax


def test_mainland_domestic_tax_uses_current_distance_bands():
    assert mainland_domestic_tax(
        [("PEK", "TYN")], as_of=date(2026, 7, 19)
    ) == 100
    assert mainland_domestic_tax(
        [("PKX", "SHA")], as_of=date(2026, 7, 19)
    ) == 150


def test_mainland_domestic_tax_charges_each_transfer_segment():
    assert mainland_domestic_tax(
        [("PEK", "TYN"), ("TYN", "SHA")],
        as_of=date(2026, 7, 19),
    ) == 250


def test_mainland_domestic_tax_rejects_unknown_or_regional_airports():
    assert mainland_domestic_tax(
        [("PEK", "HKG")], as_of=date(2026, 7, 19)
    ) is None
    assert mainland_domestic_tax(
        [("PEK", None)], as_of=date(2026, 7, 19)
    ) is None
