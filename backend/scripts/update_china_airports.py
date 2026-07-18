from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Sequence
from xml.etree import ElementTree
from zipfile import ZipFile


_XLSX_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_ALLOWED_COUNTRIES = {"CN", "HK", "MO", "TW"}
_ALLOWED_TYPES = {"large_airport", "medium_airport", "small_airport"}
_COUNTRY_REGION_GROUPS = {
    "HK": "hong_kong",
    "MO": "macau",
    "TW": "taiwan",
}
_REGIONAL_GROUPS = tuple(_COUNTRY_REGION_GROUPS.values())
_ALL_REGION_GROUPS = ("mainland", *_REGIONAL_GROUPS)
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_IATA_CODE = re.compile(r"^[A-Z]{3}$")
_ICAO_CODE = re.compile(r"^[A-Z]{4}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_caac_names(path: Path) -> list[str]:
    namespace = {"main": _XLSX_NS}
    with ZipFile(path) as workbook:
        shared_root = ElementTree.fromstring(workbook.read("xl/sharedStrings.xml"))
        shared_strings = [
            "".join(node.text or "" for node in item.iter(f"{{{_XLSX_NS}}}t"))
            for item in shared_root.findall("main:si", namespace)
        ]
        sheet = ElementTree.fromstring(workbook.read("xl/worksheets/sheet1.xml"))

    names: list[str] = []
    in_airport_rows = False
    for row in sheet.findall(".//main:sheetData/main:row", namespace):
        first_cell = row.find("main:c", namespace)
        if first_cell is None or not (first_cell.get("r") or "").startswith("A"):
            continue
        value_node = first_cell.find("main:v", namespace)
        if value_node is None or value_node.text is None:
            continue
        value = value_node.text
        if first_cell.get("t") == "s":
            value = shared_strings[int(value)]
        value = value.strip()
        if value == "合计":
            in_airport_rows = True
            continue
        if not in_airport_rows:
            continue
        if value.startswith("注："):
            note_airports = value.removeprefix("注：").split("已经颁证", 1)[0]
            names.extend(
                airport
                for airport in note_airports.split("、")
                if airport.endswith("机场")
            )
            break
        names.append(value)
    if not names:
        raise ValueError(f"no CAAC airport rows found in {path}")
    return names


def _read_ourairports(path: Path) -> dict[str, dict[str, str]]:
    airports: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            iata = (row.get("iata_code") or "").strip().upper()
            if (
                row.get("iso_country") not in _ALLOWED_COUNTRIES
                or not iata
                or row.get("type") not in _ALLOWED_TYPES
            ):
                continue
            if iata in airports:
                raise ValueError(f"duplicate OurAirports IATA code: {iata}")
            airports[iata] = row
    return airports


def _float_or_none(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    return float(value)


def _validate_review_evidence(value: Any, *, context: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} requires structured review evidence")
    required = ("source_title", "source_url", "rationale")
    if any(
        not isinstance(value.get(field), str) or not value[field].strip()
        for field in required
    ):
        raise ValueError(f"{context} requires structured review evidence")
    if not value["source_url"].startswith(("https://", "http://")):
        raise ValueError(f"{context} requires a valid review evidence source URL")
    review_date = value.get("effective_date") or value.get("observation_date")
    if not isinstance(review_date, str) or not _ISO_DATE.fullmatch(review_date):
        raise ValueError(f"{context} requires an effective or observation date")
    try:
        date.fromisoformat(review_date)
    except ValueError as exc:
        raise ValueError(
            f"{context} requires an effective or observation date"
        ) from exc
    return value


def _reviewed_override(
    override: dict[str, Any], key: str, *, context: str
) -> dict[str, Any] | None:
    if key not in override:
        return None
    value = override[key]
    if not isinstance(value, dict):
        raise ValueError(f"{context} {key} requires structured review evidence")
    _validate_review_evidence(
        value.get("review_evidence"), context=f"{context} {key}"
    )
    return value


def _airport_payload(
    *,
    row: dict[str, str],
    override: dict[str, Any],
    region_group: str,
    source_names: list[str],
) -> dict[str, Any]:
    iata = str(override.get("iata") or row["iata_code"]).upper()
    icao = str(override.get("icao") or row.get("icao_code") or "").upper() or None
    return {
        "name": override["name"],
        "aliases": sorted(set(override.get("aliases", []))),
        "iata": iata,
        "icao": icao,
        "latitude": _float_or_none(row.get("latitude_deg")),
        "longitude": _float_or_none(row.get("longitude_deg")),
        "timezone": override.get("timezone"),
        "region_group": region_group,
        "transport_airport": True,
        "commercial_passenger": True,
        "status": "active",
        "bookable": True,
        "sources": source_names,
    }


def build_catalog(
    *, caac_xlsx: Path, ourairports_csv: Path, overrides_json: Path
) -> dict[str, Any]:
    caac_xlsx = Path(caac_xlsx)
    ourairports_csv = Path(ourairports_csv)
    overrides_json = Path(overrides_json)
    overrides = json.loads(overrides_json.read_text(encoding="utf-8"))
    caac_names = _read_caac_names(caac_xlsx)
    ourairports = _read_ourairports(ourairports_csv)
    mappings = overrides.get("caac_airports", {})
    city_overrides = overrides.get("cities", {})
    regional_airports = overrides.get("regional_airports", {})
    regional_exclusions = overrides.get("regional_exclusions", {})

    missing_mappings = sorted(set(caac_names) - set(mappings))
    unknown_mappings = sorted(set(mappings) - set(caac_names))
    if missing_mappings:
        raise ValueError(f"CAAC airports missing reviewed mappings: {missing_mappings}")
    if unknown_mappings:
        raise ValueError(
            f"reviewed mappings absent from CAAC source: {unknown_mappings}"
        )

    city_airports: dict[str, list[dict[str, Any]]] = defaultdict(list)
    excluded: dict[str, list[str]] = defaultdict(list)
    for caac_name in caac_names:
        override = mappings[caac_name]
        if reason := override.get("exclude_reason"):
            excluded[str(reason)].append(caac_name)
            continue
        city_id = override["city_id"]
        city = city_overrides.get(city_id)
        if city is None:
            raise ValueError(f"airport {caac_name} references unknown city: {city_id}")
        iata = str(override["iata"]).upper()
        row = ourairports.get(iata)
        source_names = ["caac", "ourairports", "reviewed_overrides"]
        source_record_override = _reviewed_override(
            override,
            "source_record_override",
            context=f"airport {caac_name}",
        )
        scheduled_override = _reviewed_override(
            override,
            "scheduled_passenger_override",
            context=f"airport {caac_name}",
        )
        if row is None and source_record_override is not None:
            source_record = source_record_override.get("record")
            if not isinstance(source_record, dict):
                raise ValueError(
                    f"airport {caac_name} source_record_override requires a record"
                )
            row = {
                **source_record,
                "iata_code": iata,
                "icao_code": str(override.get("icao") or ""),
                "iso_country": "CN",
                "scheduled_service": "yes",
            }
            source_names = ["caac", "reviewed_overrides"]
        if row is None:
            raise ValueError(
                f"airport {caac_name} has no active airport record for {iata}"
            )
        if row["iso_country"] != "CN":
            raise ValueError(f"mainland airport {caac_name} maps outside CN: {iata}")
        if (
            row.get("scheduled_service") != "yes"
            and scheduled_override is None
        ):
            raise ValueError(
                f"airport {caac_name} has no scheduled passenger service: {iata}"
            )
        city_airports[city_id].append(
            _airport_payload(
                row=row,
                override=override,
                region_group="mainland",
                source_names=source_names,
            )
        )

    regional_source = {
        iata: row
        for iata, row in ourairports.items()
        if row["iso_country"] in _COUNTRY_REGION_GROUPS
    }
    included_codes = {str(iata).upper() for iata in regional_airports}
    excluded_codes = {str(iata).upper() for iata in regional_exclusions}
    source_codes = set(regional_source)
    overlap = sorted(included_codes & excluded_codes)
    if overlap:
        raise ValueError(f"regional candidates both included and excluded: {overlap}")
    missing_reviews = sorted(source_codes - included_codes - excluded_codes)
    if missing_reviews:
        raise ValueError(
            f"regional candidates missing review: {missing_reviews}"
        )
    unknown_reviews = sorted((included_codes | excluded_codes) - source_codes)
    if unknown_reviews:
        raise ValueError(f"regional reviews absent from source: {unknown_reviews}")

    for iata, override in regional_airports.items():
        normalized_iata = iata.upper()
        row = regional_source[normalized_iata]
        city_id = override["city_id"]
        city = city_overrides.get(city_id)
        if city is None:
            raise ValueError(f"airport {iata} references unknown city: {city_id}")
        region_group = city["region_group"]
        expected_country = next(
            (
                country
                for country, candidate_region in _COUNTRY_REGION_GROUPS.items()
                if candidate_region == region_group
            ),
            None,
        )
        if row["iso_country"] != expected_country:
            raise ValueError(f"airport {iata} does not match region {region_group}")
        scheduled_override = _reviewed_override(
            override,
            "scheduled_passenger_override",
            context=f"regional airport {normalized_iata}",
        )
        if (
            row.get("scheduled_service") != "yes"
            and scheduled_override is None
        ):
            raise ValueError(
                f"regional airport has no scheduled passenger service: {iata}"
            )
        city_airports[city_id].append(
            _airport_payload(
                row=row,
                override={**override, "iata": normalized_iata},
                region_group=region_group,
                source_names=["ourairports", "reviewed_overrides"],
            )
        )

    reviewed_regional_exclusions: dict[str, dict[str, Any]] = {}
    for iata in sorted(regional_exclusions):
        normalized_iata = iata.upper()
        override = regional_exclusions[iata]
        category = override.get("category")
        reason = override.get("reason")
        if not isinstance(category, str) or not category.strip():
            raise ValueError(f"regional exclusion {iata} requires a category")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"regional exclusion {iata} requires a reason")
        evidence = _validate_review_evidence(
            override.get("review_evidence"),
            context=f"regional exclusion {normalized_iata}",
        )
        row = regional_source[normalized_iata]
        reviewed_regional_exclusions[normalized_iata] = {
            "category": category,
            "name": row["name"],
            "reason": reason,
            "region_group": _COUNTRY_REGION_GROUPS[row["iso_country"]],
            "review_evidence": evidence,
        }

    cities: list[dict[str, Any]] = []
    for city_id in sorted(city_airports):
        city = city_overrides[city_id]
        airports = sorted(city_airports[city_id], key=lambda airport: airport["iata"])
        cities.append(
            {
                "city_id": city_id,
                "name": city["name"],
                "province": city["province"],
                "region_group": city["region_group"],
                "aliases": sorted(set(city.get("aliases", []))),
                "provider_codes": dict(sorted(city.get("provider_codes", {}).items())),
                "airports": airports,
            }
        )

    region_airports = Counter(
        airport["region_group"] for city in cities for airport in city["airports"]
    )
    region_cities = Counter(city["region_group"] for city in cities)
    mainland_transport_airports = sum(
        airport["region_group"] == "mainland" and airport["transport_airport"]
        for city in cities
        for airport in city["airports"]
    )
    mainland_bookable_airports = sum(
        airport["region_group"] == "mainland" and airport["bookable"]
        for city in cities
        for airport in city["airports"]
    )
    regional_source_counts = Counter(
        _COUNTRY_REGION_GROUPS[row["iso_country"]]
        for row in regional_source.values()
    )
    regional_included_counts = Counter(
        airport["region_group"]
        for city in cities
        for airport in city["airports"]
        if airport["region_group"] in _REGIONAL_GROUPS
    )
    regional_exclusion_categories = Counter(
        exclusion["category"] for exclusion in reviewed_regional_exclusions.values()
    )
    source_metadata = json.loads(json.dumps(overrides["sources"]))
    source_metadata["caac"]["sha256"] = _sha256(caac_xlsx)
    source_metadata["ourairports"]["sha256"] = _sha256(ourairports_csv)
    source_metadata["reviewed_overrides"] = {
        "path": "backend/data/china_airport_overrides.json",
        "sha256": _sha256(overrides_json),
    }
    payload = {
        "metadata": {
            "catalog_version": overrides["catalog_version"],
            "generated_at": overrides["generated_at"],
            "sources": source_metadata,
            "mainland_transport_airports": mainland_transport_airports,
            "mainland_bookable_airports": mainland_bookable_airports,
            "regional_airports": {
                region: region_airports[region] for region in _ALL_REGION_GROUPS
            },
            "regional_cities": {
                region: region_cities[region] for region in _ALL_REGION_GROUPS
            },
            "excluded_airports": {
                reason: sorted(names) for reason, names in sorted(excluded.items())
            },
            "regional_reconciliation": {
                "source_candidate_airports": {
                    region: regional_source_counts[region]
                    for region in _REGIONAL_GROUPS
                },
                "included_airports": {
                    region: regional_included_counts[region]
                    for region in _REGIONAL_GROUPS
                },
                "excluded_airports": reviewed_regional_exclusions,
                "excluded_airports_by_category": dict(
                    sorted(regional_exclusion_categories.items())
                ),
            },
        },
        "cities": cities,
    }
    validate_catalog(payload)
    return payload


def validate_catalog(payload: dict[str, Any]) -> None:
    metadata = payload.get("metadata")
    cities = payload.get("cities")
    if not isinstance(metadata, dict) or not isinstance(cities, list):
        raise ValueError("catalog requires metadata and cities")

    city_ids: set[str] = set()
    iata_codes: set[str] = set()
    icao_codes: set[str] = set()
    region_airports: Counter[str] = Counter()
    region_cities: Counter[str] = Counter()
    mainland_transport_airports = 0
    mainland_bookable_airports = 0
    for city in cities:
        city_id = city["city_id"]
        if city_id in city_ids:
            raise ValueError(f"duplicate city_id: {city_id}")
        city_ids.add(city_id)
        if not city.get("airports"):
            raise ValueError(f"city has no airports: {city_id}")
        city_region = city.get("region_group")
        if city_region not in _ALL_REGION_GROUPS:
            raise ValueError(f"invalid city region: {city_region}")
        region_cities[city_region] += 1
        for airport in city["airports"]:
            airport_region = airport.get("region_group")
            if airport_region != city_region:
                raise ValueError(
                    "city/airport region mismatch: "
                    f"{city_id}={city_region}, {airport.get('name')}={airport_region}"
                )
            if not airport.get("bookable"):
                raise ValueError(
                    f"non-bookable airport in runtime catalog: {airport['name']}"
                )
            if (
                airport.get("status") != "active"
                or not airport.get("transport_airport")
                or not airport.get("commercial_passenger")
            ):
                raise ValueError(
                    f"inactive or non-commercial airport: {airport['name']}"
                )
            region_airports[airport_region] += 1
            if airport_region == "mainland":
                if airport.get("transport_airport"):
                    mainland_transport_airports += 1
                if airport.get("bookable"):
                    mainland_bookable_airports += 1
            iata = airport.get("iata")
            if not isinstance(iata, str) or not _IATA_CODE.fullmatch(iata):
                raise ValueError(f"invalid IATA code: {iata!r}")
            if iata in iata_codes:
                raise ValueError(f"duplicate IATA code: {iata}")
            iata_codes.add(iata)
            icao = airport.get("icao")
            if not isinstance(icao, str) or not _ICAO_CODE.fullmatch(icao):
                raise ValueError(f"invalid ICAO code: {icao!r}")
            if icao in icao_codes:
                raise ValueError(f"duplicate ICAO code: {icao}")
            icao_codes.add(icao)

    if metadata.get("mainland_transport_airports") != mainland_transport_airports:
        raise ValueError(
            "mainland transport count does not match catalog entries: "
            f"{metadata.get('mainland_transport_airports')} != "
            f"{mainland_transport_airports}"
        )
    if metadata.get("mainland_bookable_airports") != mainland_bookable_airports:
        raise ValueError(
            "mainland bookable count does not match catalog entries: "
            f"{metadata.get('mainland_bookable_airports')} != "
            f"{mainland_bookable_airports}"
        )

    expected_region_airports = {
        region: region_airports[region] for region in _ALL_REGION_GROUPS
    }
    if metadata.get("regional_airports") != expected_region_airports:
        raise ValueError(
            "regional airport counts do not match catalog entries: "
            f"{metadata.get('regional_airports')} != {expected_region_airports}"
        )
    expected_region_cities = {
        region: region_cities[region] for region in _ALL_REGION_GROUPS
    }
    if metadata.get("regional_cities") != expected_region_cities:
        raise ValueError(
            "regional city counts do not match catalog entries: "
            f"{metadata.get('regional_cities')} != {expected_region_cities}"
        )

    excluded_airports = metadata.get("excluded_airports")
    if not isinstance(excluded_airports, dict):
        raise ValueError("excluded airport summary must be a mapping")
    excluded_names: list[str] = []
    for category, names in excluded_airports.items():
        if not isinstance(category, str) or not category.strip():
            raise ValueError("excluded airport summary has an invalid category")
        if not isinstance(names, list) or any(
            not isinstance(name, str) or not name.strip() for name in names
        ):
            raise ValueError("excluded airport summary has invalid airport names")
        excluded_names.extend(names)
    if len(excluded_names) != len(set(excluded_names)):
        raise ValueError("excluded airport summary contains duplicate airports")

    reconciliation = metadata.get("regional_reconciliation")
    if not isinstance(reconciliation, dict):
        raise ValueError("regional reconciliation summary is required")
    source_counts = reconciliation.get("source_candidate_airports")
    included_counts = reconciliation.get("included_airports")
    expected_included_counts = {
        region: region_airports[region] for region in _REGIONAL_GROUPS
    }
    if included_counts != expected_included_counts:
        raise ValueError(
            "regional reconciliation included counts do not match catalog entries"
        )
    if not isinstance(source_counts, dict) or set(source_counts) != set(
        _REGIONAL_GROUPS
    ):
        raise ValueError("regional reconciliation counts are incomplete")

    regional_exclusions = reconciliation.get("excluded_airports")
    if not isinstance(regional_exclusions, dict):
        raise ValueError("regional reconciliation exclusions must be a mapping")
    excluded_by_region: Counter[str] = Counter()
    excluded_by_category: Counter[str] = Counter()
    for iata, exclusion in regional_exclusions.items():
        if not isinstance(iata, str) or not _IATA_CODE.fullmatch(iata):
            raise ValueError(f"invalid regional exclusion IATA code: {iata!r}")
        if iata in iata_codes:
            raise ValueError(f"regional airport is both included and excluded: {iata}")
        if not isinstance(exclusion, dict):
            raise ValueError(f"invalid regional exclusion: {iata}")
        region = exclusion.get("region_group")
        category = exclusion.get("category")
        reason = exclusion.get("reason")
        if region not in _REGIONAL_GROUPS:
            raise ValueError(f"invalid regional exclusion region: {iata}")
        if not isinstance(category, str) or not category.strip():
            raise ValueError(f"invalid regional exclusion category: {iata}")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"invalid regional exclusion reason: {iata}")
        _validate_review_evidence(
            exclusion.get("review_evidence"),
            context=f"regional exclusion {iata}",
        )
        excluded_by_region[region] += 1
        excluded_by_category[category] += 1

    for region in _REGIONAL_GROUPS:
        if source_counts.get(region) != (
            expected_included_counts[region] + excluded_by_region[region]
        ):
            raise ValueError(
                f"regional reconciliation counts do not balance for {region}"
            )
    category_summary = reconciliation.get("excluded_airports_by_category")
    if category_summary != dict(sorted(excluded_by_category.items())):
        raise ValueError(
            "regional exclusion category summary does not match exclusions"
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the China airport catalog")
    parser.add_argument("--caac-xlsx", type=Path, required=True)
    parser.add_argument("--ourairports-csv", type=Path, required=True)
    parser.add_argument("--overrides", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    payload = build_catalog(
        caac_xlsx=args.caac_xlsx,
        ourairports_csv=args.ourairports_csv,
        overrides_json=args.overrides,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    metadata = payload["metadata"]
    print(f"mainland transport airports: {metadata['mainland_transport_airports']}")
    print(f"mainland bookable airports: {metadata['mainland_bookable_airports']}")
    print(
        "regional city counts: "
        + ", ".join(
            f"{region}={count}"
            for region, count in metadata["regional_cities"].items()
        )
    )
    print("duplicate IATA/ICAO codes: 0/0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
