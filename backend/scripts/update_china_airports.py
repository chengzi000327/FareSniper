from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Sequence
from xml.etree import ElementTree
from zipfile import ZipFile


_XLSX_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_ALLOWED_COUNTRIES = {"CN", "HK", "MO", "TW"}
_ALLOWED_TYPES = {"large_airport", "medium_airport", "small_airport"}


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
        if row is None and (source_record := override.get("source_record_override")):
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
            and not override.get("scheduled_passenger_override")
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

    for iata, override in overrides.get("regional_airports", {}).items():
        normalized_iata = iata.upper()
        row = ourairports.get(normalized_iata)
        if row is None:
            raise ValueError(f"regional airport has no active airport record: {iata}")
        city_id = override["city_id"]
        city = city_overrides.get(city_id)
        if city is None:
            raise ValueError(f"airport {iata} references unknown city: {city_id}")
        region_group = city["region_group"]
        expected_country = {
            "hong_kong": "HK",
            "macau": "MO",
            "taiwan": "TW",
        }.get(region_group)
        if row["iso_country"] != expected_country:
            raise ValueError(f"airport {iata} does not match region {region_group}")
        if (
            row.get("scheduled_service") != "yes"
            and not override.get("scheduled_passenger_override")
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
            "mainland_transport_airports": len(caac_names),
            "mainland_bookable_airports": region_airports["mainland"],
            "regional_airports": dict(sorted(region_airports.items())),
            "regional_cities": dict(sorted(region_cities.items())),
            "excluded_airports": {
                reason: sorted(names) for reason, names in sorted(excluded.items())
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
    mainland_bookable_airports = 0
    for city in cities:
        city_id = city["city_id"]
        if city_id in city_ids:
            raise ValueError(f"duplicate city_id: {city_id}")
        city_ids.add(city_id)
        if not city.get("airports"):
            raise ValueError(f"city has no airports: {city_id}")
        for airport in city["airports"]:
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
            if airport.get("region_group") == "mainland":
                mainland_bookable_airports += 1
            iata = airport.get("iata")
            if iata in iata_codes:
                raise ValueError(f"duplicate IATA code: {iata}")
            iata_codes.add(iata)
            if icao := airport.get("icao"):
                if icao in icao_codes:
                    raise ValueError(f"duplicate ICAO code: {icao}")
                icao_codes.add(icao)
    if metadata.get("mainland_bookable_airports") != mainland_bookable_airports:
        raise ValueError(
            "mainland bookable count does not match catalog entries: "
            f"{metadata.get('mainland_bookable_airports')} != "
            f"{mainland_bookable_airports}"
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
