"""Import a Spotify playlist export (Exportify CSV) into a taste profile.

Why a file and not the Spotify API: the six features this recommender ranks on
(energy, danceability, valence, acousticness, instrumentalness, speechiness) come from
Spotify's audio-features endpoint, which newly registered apps can no longer call. A file
import also keeps the whole system reproducible with no key, no OAuth and no network, which
is the rule the rest of the project follows.

Everything here treats the file as untrusted: missing columns, bad numbers, unparseable
dates and unmappable genres are reported, never guessed at.
"""

import csv
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from src.agent.profile import Profile

EXPORTS_DIR = Path(__file__).resolve().parents[2] / "data" / "exports"
EXAMPLE_EXPORT = EXPORTS_DIR / "example_export.csv"

# Exportify's column names. Only the first two are required.
COLUMN_TITLE = "track name"
COLUMN_ARTIST = "artist name(s)"
COLUMN_RELEASE = "album release date"
COLUMN_POPULARITY = "popularity"
COLUMN_GENRES = "artist genres"
REQUIRED_COLUMNS = (COLUMN_TITLE, COLUMN_ARTIST)
# str.title() would render "artist name(s)" as "Artist Name(S)".
COLUMN_DISPLAY = {COLUMN_TITLE: "Track Name", COLUMN_ARTIST: "Artist Name(s)"}

# Audio-feature columns, present only if the exporting app still had access to them.
FEATURE_COLUMNS = {
    "danceability": "danceability",
    "energy": "energy",
    "speechiness": "speechiness",
    "acousticness": "acousticness",
    "instrumentalness": "instrumentalness",
    "valence": "valence",
    "tempo": "tempo",
}

# Spotify's genre vocabulary is far more granular than this catalog's. Most specific
# first: "japanese city pop" must land on city pop, not j-pop or pop.
GENRE_RULES: Tuple[Tuple[str, str], ...] = (
    ("city pop", "city pop"),
    ("chillhop", "lofi"),
    ("lo-fi", "lofi"),
    ("lofi", "lofi"),
    ("nepali", "nepali"),
    ("nepalese", "nepali"),
    ("j-pop", "j-pop"),
    ("jpop", "j-pop"),
    ("anime", "j-pop"),
    ("japanese r&b", "r&b"),
    ("japanese", "j-pop"),
    ("neo soul", "r&b"),
    ("r&b", "r&b"),
    ("rnb", "r&b"),
    ("soul", "r&b"),
    ("trap", "hip-hop"),
    ("drill", "hip-hop"),
    ("hip hop", "hip-hop"),
    ("hip-hop", "hip-hop"),
    ("rap", "hip-hop"),
    ("synthwave", "synthwave"),
    ("retrowave", "synthwave"),
    ("vaporwave", "synthwave"),
    ("house", "edm"),
    ("techno", "edm"),
    ("trance", "edm"),
    ("dubstep", "edm"),
    ("drum and bass", "edm"),
    ("edm", "edm"),
    ("electro", "edm"),
    ("ambient", "ambient"),
    ("drone", "ambient"),
    ("jazz", "jazz"),
    ("bossa", "jazz"),
    ("indie pop", "indie pop"),
    ("indie rock", "indie rock"),
    ("indie", "indie rock"),
    ("singer-songwriter", "acoustic"),
    ("acoustic", "acoustic"),
    ("folk", "acoustic"),
    ("metal", "rock"),
    ("punk", "rock"),
    ("rock", "rock"),
    ("pop", "pop"),
)

DEFAULT_TOP_GENRES = 4
# A decade must account for at least this share of the export to be called a favourite.
MIN_DECADE_SHARE = 0.15
# Mean track popularity above/below these means "likes hits" / "prefers deep cuts".
POPULAR_THRESHOLD = 60.0
OBSCURE_THRESHOLD = 45.0
# Catalog columns that need a value the export cannot supply.
DEFAULT_MOOD = "moody"
DEFAULT_MOOD_TAG = "reflective"
# Mood inferred from valence and energy, so imported rows are not all identical.
MOOD_RULES: Tuple[Tuple[float, float, str, str], ...] = (
    (0.60, 0.70, "happy", "euphoric"),
    (0.60, 0.00, "relaxed", "playful"),
    (0.35, 0.70, "intense", "aggressive"),
    (0.35, 0.00, "moody", "nostalgic"),
    (0.00, 0.70, "confident", "confident"),
    (0.00, 0.00, "moody", "melancholic"),
)


class SpotifyImportError(ValueError):
    """Raised when an export cannot be used. Carries a readable reason."""


@dataclass(frozen=True)
class ExportTrack:
    """One row of an export, parsed and validated."""

    title: str
    artist: str
    release_year: Optional[int] = None
    popularity: Optional[int] = None
    spotify_genres: Tuple[str, ...] = ()
    features: Mapping[str, float] = field(default_factory=dict)
    line_number: int = 0

    @property
    def decade(self) -> Optional[str]:
        if self.release_year is None:
            return None
        return f"{self.release_year // 10 * 10}s"

    @property
    def catalog_genre(self) -> Optional[str]:
        for genre in self.spotify_genres:
            mapped = map_genre(genre)
            if mapped is not None:
                return mapped
        return None


def map_genre(spotify_genre: str) -> Optional[str]:
    """Collapse one Spotify genre string onto this catalog's vocabulary."""
    text = (spotify_genre or "").strip().lower()
    if not text:
        return None
    for needle, catalog_genre in GENRE_RULES:
        if needle in text:
            return catalog_genre
    return None


def _number(raw: str) -> Optional[float]:
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _year(raw: str) -> Optional[int]:
    """Exportify writes 2007-09-11, 2007-09 or 2007 depending on the album."""
    head = str(raw or "").strip()[:4]
    if len(head) != 4 or not head.isdigit():
        return None
    year = int(head)
    return year if 1900 <= year <= 2100 else None


def _features(row: Mapping[str, str]) -> Dict[str, float]:
    found: Dict[str, float] = {}
    for column, name in FEATURE_COLUMNS.items():
        if column not in row:
            continue
        value = _number(row[column])
        if value is None:
            continue
        found[name] = value
    return found


def _genres(raw: str) -> Tuple[str, ...]:
    return tuple(part.strip().lower() for part in str(raw or "").split(",") if part.strip())


def read_export(path: str) -> Tuple[ExportTrack, ...]:
    """Read an Exportify CSV. Rows without a track title are skipped, not guessed."""
    target = Path(path)
    try:
        # utf-8-sig because spreadsheet exports routinely carry a byte-order mark.
        text = target.read_text(encoding="utf-8-sig")
    except FileNotFoundError as error:
        raise SpotifyImportError(
            f"Spotify export not found: {target}. Export a playlist at https://exportify.net "
            "and save the CSV, or try the bundled sample at "
            "data/exports/example_export.csv."
        ) from error
    except UnicodeDecodeError as error:
        raise SpotifyImportError(f"Export {target} is not valid UTF-8 text: {error}") from error

    reader = csv.DictReader(text.splitlines())
    headers = {name.strip().lower() for name in (reader.fieldnames or [])}
    missing = [column for column in REQUIRED_COLUMNS if column not in headers]
    if missing:
        raise SpotifyImportError(
            "Export is missing required column(s): "
            + ", ".join(COLUMN_DISPLAY.get(column, column) for column in missing)
            + f". Found: {', '.join(sorted(headers)) or '(no header row)'}"
        )

    tracks: List[ExportTrack] = []
    for line_number, raw_row in enumerate(reader, start=2):
        row = {
            (key or "").strip().lower(): (value or "")
            for key, value in raw_row.items()
            if key is not None
        }
        title = row.get(COLUMN_TITLE, "").strip()
        if not title:
            continue
        popularity = _number(row.get(COLUMN_POPULARITY, ""))
        tracks.append(
            ExportTrack(
                title=title,
                artist=row.get(COLUMN_ARTIST, "").strip() or "Unknown artist",
                release_year=_year(row.get(COLUMN_RELEASE, "")),
                popularity=int(popularity) if popularity is not None else None,
                spotify_genres=_genres(row.get(COLUMN_GENRES, "")),
                features=_features(row),
                line_number=line_number,
            )
        )

    if not tracks:
        raise SpotifyImportError(f"Export {target} contained no tracks with a track name.")
    return tuple(tracks)


def _mean(values: Sequence[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def infer_profile(
    tracks: Sequence[ExportTrack], name: str = "listener", top_genres: int = DEFAULT_TOP_GENRES
) -> Profile:
    """Build a taste profile from what the export actually contains.

    Deliberately conservative: it never invents a veto, because "absent from this playlist"
    is not the same as "I do not want to hear this".
    """
    genre_counts: Counter = Counter()
    unmapped: Counter = Counter()
    for track in tracks:
        mapped = track.catalog_genre
        if mapped:
            genre_counts[mapped] += 1
            continue
        for genre in track.spotify_genres:
            unmapped[genre] += 1

    decade_counts = Counter(track.decade for track in tracks if track.decade)
    total_decades = sum(decade_counts.values())
    decades = tuple(
        decade
        for decade, count in decade_counts.most_common()
        if total_decades and count / total_decades >= MIN_DECADE_SHARE
    )

    energies = [track.features["energy"] for track in tracks if "energy" in track.features]
    popularities = [track.popularity for track in tracks if track.popularity is not None]
    mean_popularity = _mean(popularities)

    likes_popular: Optional[bool] = None
    if mean_popularity is not None:
        if mean_popularity >= POPULAR_THRESHOLD:
            likes_popular = True
        elif mean_popularity <= OBSCURE_THRESHOLD:
            likes_popular = False

    warnings: List[str] = []
    if unmapped:
        warnings.append(
            "no catalog genre matches these Spotify genres, so they were ignored: "
            + ", ".join(genre for genre, _ in unmapped.most_common(6))
        )
    if not energies:
        warnings.append(
            "export has no audio-feature columns, so typical_energy was left unset "
            "(Spotify no longer exposes audio features to new apps)"
        )

    mean_energy = _mean(energies)
    notes_parts = [f"Imported from a Spotify export of {len(tracks)} track(s)."]
    if mean_popularity is not None:
        notes_parts.append(f"Mean track popularity {mean_popularity:.0f}.")
    if unmapped:
        notes_parts.append(f"{len(unmapped)} Spotify genre(s) had no catalog equivalent.")

    return Profile(
        name=name,
        favorite_genres=tuple(genre for genre, _ in genre_counts.most_common(top_genres)),
        favorite_decades=decades,
        typical_energy=round(mean_energy, 2) if mean_energy is not None else None,
        likes_popular=likes_popular,
        notes=" ".join(notes_parts),
        warnings=tuple(warnings),
    )


def _mood_for(features: Mapping[str, float]) -> Tuple[str, str]:
    valence = float(features.get("valence", 0.5))
    energy = float(features.get("energy", 0.5))
    for valence_floor, energy_floor, mood, tag in MOOD_RULES:
        if valence >= valence_floor and energy >= energy_floor:
            return mood, tag
    return DEFAULT_MOOD, DEFAULT_MOOD_TAG


def catalog_rows(tracks: Sequence[ExportTrack], start_id: int) -> Tuple[Dict, ...]:
    """Turn export rows into catalog rows, skipping anything we cannot fill honestly.

    A track is only included when the export carried real audio features and its genre
    maps onto the catalog. Nothing is estimated here.
    """
    required = ("energy", "danceability", "acousticness", "instrumentalness", "speechiness", "valence")
    rows: List[Dict] = []
    next_id = start_id
    for track in tracks:
        genre = track.catalog_genre
        if genre is None or not all(key in track.features for key in required):
            continue
        mood, mood_tag = _mood_for(track.features)
        rows.append(
            {
                "id": next_id,
                "title": track.title,
                "artist": track.artist,
                "genre": genre,
                "mood": mood,
                "energy": round(track.features["energy"], 2),
                "tempo_bpm": round(track.features.get("tempo", 120.0), 0),
                "valence": round(track.features["valence"], 2),
                "danceability": round(track.features["danceability"], 2),
                "acousticness": round(track.features["acousticness"], 2),
                "popularity": track.popularity if track.popularity is not None else 50,
                "release_decade": track.decade or "2020s",
                "detailed_mood_tag": mood_tag,
                "instrumentalness": round(track.features["instrumentalness"], 2),
                "speechiness": round(track.features["speechiness"], 2),
            }
        )
        next_id += 1
    return tuple(rows)


def summarize(tracks: Sequence[ExportTrack], profile: Profile) -> str:
    """A readable report of what the import decided, for the CLI and the README."""
    genre_counts = Counter(track.catalog_genre for track in tracks if track.catalog_genre)
    with_features = sum(1 for track in tracks if "energy" in track.features)
    lines = [
        f"Read {len(tracks)} track(s) from the export.",
        f"  with audio features: {with_features}",
        "  catalog genres found: "
        + (", ".join(f"{genre} x{count}" for genre, count in genre_counts.most_common()) or "none"),
        f"Inferred profile: {profile.describe()}",
    ]
    lines.extend(f"  warning: {warning}" for warning in profile.warnings)
    return "\n".join(lines)
