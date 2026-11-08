"""Turn a Spotify playlist export into a taste profile (and optionally catalog rows).

Export a playlist as CSV at https://exportify.net, then run from the project root:

    python -m src.import_spotify data/exports/example_export.csv --dry-run
    python -m src.import_spotify my_playlist.csv --name "Sakxam" --write
    python -m src.import_spotify my_playlist.csv --write --append-catalog

Nothing is written unless --write is passed.
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, Sequence

from src.agent.profile import DEFAULT_PROFILE_PATH, Profile
from src.agent.spotify import (
    EXAMPLE_EXPORT,
    SpotifyImportError,
    catalog_rows,
    infer_profile,
    read_export,
    summarize,
)
from src.main import SONGS_CSV
from src.recommender import load_songs

EXIT_OK = 0
EXIT_IMPORT_ERROR = 1
EXIT_NOTHING_TO_WRITE = 2

CATALOG_COLUMNS = (
    "id", "title", "artist", "genre", "mood", "energy", "tempo_bpm", "valence",
    "danceability", "acousticness", "popularity", "release_decade",
    "detailed_mood_tag", "instrumentalness", "speechiness",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.import_spotify",
        description="Import a Spotify (Exportify) CSV export into a taste profile.",
    )
    parser.add_argument(
        "export",
        nargs="?",
        default=str(EXAMPLE_EXPORT),
        help=f"path to the exported CSV (default: {EXAMPLE_EXPORT.name})",
    )
    parser.add_argument("--name", default="listener", help="name to store in the profile")
    parser.add_argument(
        "--out", default=str(DEFAULT_PROFILE_PATH), help="where to write the profile"
    )
    parser.add_argument("--top-genres", type=int, default=4, help="how many genres to claim")
    parser.add_argument("--write", action="store_true", help="actually write the profile file")
    parser.add_argument(
        "--append-catalog",
        action="store_true",
        help="also append importable tracks to data/songs.csv (needs --write)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="show what would happen and write nothing"
    )
    return parser


def profile_to_dict(profile: Profile) -> Dict:
    """Only non-empty fields, so a written profile stays readable and hand-editable."""
    payload: Dict = {"name": profile.name}
    for key, value in (
        ("favorite_genres", profile.favorite_genres),
        ("avoid_genres", profile.avoid_genres),
        ("favorite_moods", profile.favorite_moods),
        ("favorite_decades", profile.favorite_decades),
    ):
        if value:
            payload[key] = list(value)
    if profile.typical_energy is not None:
        payload["typical_energy"] = profile.typical_energy
    if profile.likes_popular is not None:
        payload["likes_popular"] = profile.likes_popular
    if profile.notes:
        payload["notes"] = profile.notes
    return payload


def append_catalog(rows: Sequence[Dict], catalog_path: Path) -> int:
    """Append rows to songs.csv, skipping titles already present. Returns rows written."""
    existing = {str(song["title"]).strip().lower() for song in load_songs(str(catalog_path))}
    fresh = [row for row in rows if str(row["title"]).strip().lower() not in existing]
    if not fresh:
        return 0
    with catalog_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CATALOG_COLUMNS)
        for row in fresh:
            writer.writerow({column: row[column] for column in CATALOG_COLUMNS})
    return len(fresh)


def main(argv: Sequence[str] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        tracks = read_export(args.export)
    except SpotifyImportError as error:
        print(f"Error: {error}", file=sys.stderr)
        return EXIT_IMPORT_ERROR

    profile = infer_profile(tracks, name=args.name, top_genres=args.top_genres)
    print(summarize(tracks, profile))

    payload = profile_to_dict(profile)
    print("\nProfile that would be written:")
    print(json.dumps(payload, indent=2))

    if not profile.favorite_genres:
        print(
            "\nNo catalog genre could be derived from this export, so there is nothing "
            "worth writing. Check the 'Artist Genres' column exists in your CSV.",
            file=sys.stderr,
        )
        return EXIT_NOTHING_TO_WRITE

    importable = catalog_rows(tracks, start_id=0)
    print(
        f"\n{len(importable)} of {len(tracks)} track(s) carry enough audio features to "
        "become catalog rows."
    )

    if args.dry_run or not args.write:
        print("\nDry run: nothing written. Pass --write to save.")
        return EXIT_OK

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {out_path}")

    if args.append_catalog:
        catalog = Path(str(SONGS_CSV))
        next_id = max(int(song["id"]) for song in load_songs(str(catalog))) + 1
        written = append_catalog(catalog_rows(tracks, start_id=next_id), catalog)
        print(f"Appended {written} new song(s) to {catalog.name}")

    print(f"\nTry it: python -m src.agent_cli \"something for the gym\" --profile {out_path}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
