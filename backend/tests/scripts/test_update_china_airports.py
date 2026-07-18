from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from backend.scripts.update_china_airports import build_catalog, main, validate_catalog


FIXTURES = Path(__file__).parents[1] / "fixtures" / "airports"


def _write_overrides(path: Path) -> Path:
    payload = {
        "catalog_version": "test-2025.1",
        "generated_at": "2026-07-19T00:00:00Z",
        "sources": {
            "caac": {
                "title": "CAAC fixture",
                "url": "https://www.caac.gov.cn/fixture.xlsx",
                "published": "2026-02-26",
            },
            "ourairports": {
                "title": "OurAirports fixture",
                "url": "https://ourairports.com/data/airports.csv",
                "snapshot": "2026-07-17",
            },
        },
        "cities": {
            "beijing": {
                "name": "北京",
                "province": "北京",
                "region_group": "mainland",
                "aliases": ["北京市"],
                "provider_codes": {
                    "ctrip": "BJS",
                    "flyai": "BJS",
                    "serpapi": "BJS",
                    "variflight": "BJS",
                },
            },
            "hong-kong": {
                "name": "香港",
                "province": "香港",
                "region_group": "hong_kong",
                "aliases": ["香港特别行政区"],
                "provider_codes": {"ctrip": "HKG", "serpapi": "HKG"},
            },
            "sansha": {
                "name": "三沙",
                "province": "海南",
                "region_group": "mainland",
                "aliases": [],
                "provider_codes": {"ctrip": "XYI", "serpapi": "XYI"},
            },
            "xingtai": {
                "name": "邢台",
                "province": "河北",
                "region_group": "mainland",
                "aliases": [],
                "provider_codes": {"ctrip": "XNT", "serpapi": "XNT"},
            },
            "yiwu": {
                "name": "义乌",
                "province": "浙江",
                "region_group": "mainland",
                "aliases": [],
                "provider_codes": {"ctrip": "YIW", "serpapi": "YIW"},
            },
        },
        "caac_airports": {
            "北京/首都": {
                "city_id": "beijing",
                "name": "北京首都国际机场",
                "iata": "PEK",
                "aliases": ["首都机场"],
            },
            "北京/大兴": {
                "city_id": "beijing",
                "name": "北京大兴国际机场",
                "iata": "PKX",
                "aliases": ["大兴机场"],
            },
            "义乌": {
                "city_id": "yiwu",
                "name": "义乌机场",
                "iata": "YIW",
                "aliases": [],
            },
            "邢台/褡裢": {
                "city_id": "xingtai",
                "name": "邢台褡裢机场",
                "iata": "XNT",
                "aliases": [],
                "scheduled_passenger_override": True,
            },
            "三沙/永兴": {
                "city_id": "sansha",
                "name": "三沙永兴机场",
                "iata": "XYI",
                "icao": "ZJYX",
                "aliases": ["永兴机场"],
                "source_record_override": {
                    "latitude_deg": "16.8328",
                    "longitude_deg": "112.344002",
                },
            },
            "蚌埠滕湖机场": {"exclude_reason": "not_yet_operational"},
        },
        "regional_airports": {
            "HKG": {
                "city_id": "hong-kong",
                "name": "香港国际机场",
                "aliases": ["赤鱲角机场"],
            }
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_build_catalog_merges_sources_and_applies_reviewed_overrides(
    tmp_path: Path,
) -> None:
    payload = build_catalog(
        caac_xlsx=FIXTURES / "caac_airports.xlsx",
        ourairports_csv=FIXTURES / "ourairports_cn.csv",
        overrides_json=_write_overrides(tmp_path / "overrides.json"),
    )

    assert payload["metadata"]["mainland_transport_airports"] == 6
    assert payload["metadata"]["mainland_bookable_airports"] == 5
    assert payload["metadata"]["excluded_airports"] == {
        "not_yet_operational": ["蚌埠滕湖机场"]
    }
    assert [city["city_id"] for city in payload["cities"]] == [
        "beijing",
        "hong-kong",
        "sansha",
        "xingtai",
        "yiwu",
    ]
    assert [airport["iata"] for airport in payload["cities"][0]["airports"]] == [
        "PEK",
        "PKX",
    ]
    assert payload["cities"][0]["airports"][0]["latitude"] == 40.080101
    assert payload["cities"][1]["airports"][0]["region_group"] == "hong_kong"
    assert payload["cities"][2]["airports"][0]["sources"] == [
        "caac",
        "reviewed_overrides",
    ]
    assert payload["cities"][3]["airports"][0]["iata"] == "XNT"
    validate_catalog(payload)


def test_build_catalog_is_byte_stable_for_the_same_inputs(tmp_path: Path) -> None:
    overrides = _write_overrides(tmp_path / "overrides.json")
    kwargs = {
        "caac_xlsx": FIXTURES / "caac_airports.xlsx",
        "ourairports_csv": FIXTURES / "ourairports_cn.csv",
        "overrides_json": overrides,
    }

    first = build_catalog(**kwargs)
    second = build_catalog(**kwargs)

    assert json.dumps(first, ensure_ascii=False, sort_keys=True) == json.dumps(
        second, ensure_ascii=False, sort_keys=True
    )


def test_validate_catalog_rejects_duplicate_and_non_bookable_airports(
    tmp_path: Path,
) -> None:
    payload = build_catalog(
        caac_xlsx=FIXTURES / "caac_airports.xlsx",
        ourairports_csv=FIXTURES / "ourairports_cn.csv",
        overrides_json=_write_overrides(tmp_path / "overrides.json"),
    )
    duplicate = copy.deepcopy(payload)
    duplicate["cities"][1]["airports"][0]["iata"] = "PEK"
    with pytest.raises(ValueError, match="duplicate IATA"):
        validate_catalog(duplicate)

    non_bookable = copy.deepcopy(payload)
    non_bookable["cities"][0]["airports"][0]["bookable"] = False
    with pytest.raises(ValueError, match="non-bookable"):
        validate_catalog(non_bookable)


def test_validate_catalog_rejects_declared_count_mismatch(tmp_path: Path) -> None:
    payload = build_catalog(
        caac_xlsx=FIXTURES / "caac_airports.xlsx",
        ourairports_csv=FIXTURES / "ourairports_cn.csv",
        overrides_json=_write_overrides(tmp_path / "overrides.json"),
    )
    payload["metadata"]["mainland_bookable_airports"] += 1

    with pytest.raises(ValueError, match="mainland bookable count"):
        validate_catalog(payload)


def test_validate_catalog_rejects_inactive_commercial_entry(tmp_path: Path) -> None:
    payload = build_catalog(
        caac_xlsx=FIXTURES / "caac_airports.xlsx",
        ourairports_csv=FIXTURES / "ourairports_cn.csv",
        overrides_json=_write_overrides(tmp_path / "overrides.json"),
    )
    payload["cities"][0]["airports"][0]["status"] = "closed"

    with pytest.raises(ValueError, match="inactive or non-commercial"):
        validate_catalog(payload)


def test_generator_filters_unscheduled_and_non_airport_records(tmp_path: Path) -> None:
    payload = build_catalog(
        caac_xlsx=FIXTURES / "caac_airports.xlsx",
        ourairports_csv=FIXTURES / "ourairports_cn.csv",
        overrides_json=_write_overrides(tmp_path / "overrides.json"),
    )
    codes = {
        airport["iata"]
        for city in payload["cities"]
        for airport in city["airports"]
    }

    assert "GAO" not in codes
    assert "NOS" not in codes
    assert "XNT" in codes


def test_main_writes_valid_json_and_reports_counts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "catalog.json"
    result = main(
        [
            "--caac-xlsx",
            str(FIXTURES / "caac_airports.xlsx"),
            "--ourairports-csv",
            str(FIXTURES / "ourairports_cn.csv"),
            "--overrides",
            str(_write_overrides(tmp_path / "overrides.json")),
            "--output",
            str(output),
        ]
    )

    assert result == 0
    assert json.loads(output.read_text(encoding="utf-8"))["metadata"][
        "mainland_transport_airports"
    ] == 6
    stdout = capsys.readouterr().out
    assert "mainland transport airports: 6" in stdout
    assert "duplicate IATA/ICAO codes: 0/0" in stdout
