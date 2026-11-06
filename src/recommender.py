import csv
from dataclasses import asdict, dataclass
from typing import Dict, List, Tuple

INT_FIELDS = ("id", "popularity")
FLOAT_FIELDS = (
    "energy",
    "tempo_bpm",
    "valence",
    "danceability",
    "acousticness",
    "instrumentalness",
    "speechiness",
)

# Each user preference key matches the song column of the same name.
CATEGORICAL_FEATURES = {
    "genre": "Genre match",
    "mood": "Mood match",
    "release_decade": "Decade match",
    "detailed_mood_tag": "Mood tag match",
}
PROXIMITY_FEATURES = {
    "energy": "Energy proximity",
    "danceability": "Danceability proximity",
    "acousticness": "Acousticness proximity",
    "instrumentalness": "Instrumentalness proximity",
    "speechiness": "Speechiness proximity",
}

# Strategy Pattern: each mode is a weight table; score_song stays the same.
WEIGHT_STRATEGIES = {
    "balanced": {
        "genre": 2.0,
        "mood": 1.5,
        "release_decade": 0.5,
        "detailed_mood_tag": 1.0,
        "energy": 1.5,
        "danceability": 1.0,
        "acousticness": 1.0,
        "tempo_bpm": 0.5,
        "popularity": 0.5,
        "instrumentalness": 1.0,
        "speechiness": 0.5,
    },
    "genre_first": {
        "genre": 4.0,
        "mood": 1.0,
        "release_decade": 0.5,
        "detailed_mood_tag": 0.5,
        "energy": 1.0,
        "danceability": 0.5,
        "acousticness": 0.5,
        "tempo_bpm": 0.25,
        "popularity": 0.25,
        "instrumentalness": 0.5,
        "speechiness": 0.25,
    },
    "vibe_and_energy": {
        "genre": 0.75,
        "mood": 2.0,
        "release_decade": 0.25,
        "detailed_mood_tag": 2.0,
        "energy": 3.0,
        "danceability": 1.5,
        "acousticness": 1.0,
        "tempo_bpm": 0.75,
        "popularity": 0.25,
        "instrumentalness": 1.5,
        "speechiness": 0.5,
    },
}
DEFAULT_MODE = "balanced"

MAX_TEMPO_GAP_BPM = 100.0
MAX_POPULARITY = 100.0
ACOUSTIC_LOVER_TARGET = 0.8
ACOUSTIC_AVOIDER_TARGET = 0.2

ARTIST_REPEAT_PENALTY = 0.75
GENRE_REPEAT_PENALTY = 0.35
MAX_GENRE_REPEATS = 2

ScoredSong = Tuple[Dict, float, List[str]]


@dataclass
class Song:
    """
    Represents a song and its attributes.
    Required by tests/test_recommender.py
    """
    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float
    popularity: int = 0
    release_decade: str = ""
    detailed_mood_tag: str = ""
    instrumentalness: float = 0.0
    speechiness: float = 0.0

@dataclass
class UserProfile:
    """
    Represents a user's taste preferences.
    Required by tests/test_recommender.py
    """
    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool

class Recommender:
    """
    OOP implementation of the recommendation logic.
    Required by tests/test_recommender.py
    """
    def __init__(self, songs: List[Song]):
        """Store the catalog of Song objects to recommend from."""
        self.songs = songs

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        """Return the top k Song objects for the given user profile."""
        songs_by_id = {song.id: song for song in self.songs}
        song_dicts = [asdict(song) for song in self.songs]
        results = recommend_songs(_profile_to_prefs(user), song_dicts, k=k)
        return [songs_by_id[song["id"]] for song, _, _ in results]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        """Return a human-readable explanation of why a song fits the user."""
        _, reasons = score_song(_profile_to_prefs(user), asdict(song))
        return "; ".join(reasons) or "No strong matches with your preferences."

def _profile_to_prefs(user: UserProfile) -> Dict:
    """Convert a UserProfile into the user_prefs dict used by score_song."""
    return {
        "genre": user.favorite_genre,
        "mood": user.favorite_mood,
        "energy": user.target_energy,
        "likes_acoustic": user.likes_acoustic,
    }

def _parse_row(row: Dict[str, str], line_number: int) -> Dict:
    """Return a new song dict with numeric CSV fields cast to int or float."""
    try:
        ints = {field: int(row[field]) for field in INT_FIELDS if field in row}
        floats = {field: float(row[field]) for field in FLOAT_FIELDS if field in row}
    except ValueError as error:
        raise ValueError(f"Bad numeric value on line {line_number} of songs CSV: {error}") from error
    return {**row, **ints, **floats}

def load_songs(csv_path: str) -> List[Dict]:
    """
    Loads songs from a CSV file.
    Required by src/main.py
    """
    try:
        with open(csv_path, newline="", encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)
            # Line 1 is the header, so data rows start on line 2.
            return [_parse_row(row, line_number) for line_number, row in enumerate(reader, start=2)]
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Songs file not found: {csv_path}") from error

def _weights_for(mode: str) -> Dict[str, float]:
    """Look up the weight table for a scoring mode, failing fast on unknown modes."""
    if mode not in WEIGHT_STRATEGIES:
        options = ", ".join(sorted(WEIGHT_STRATEGIES))
        raise ValueError(f"Unknown scoring mode '{mode}'. Choose one of: {options}")
    return WEIGHT_STRATEGIES[mode]

def _with_acoustic_target(user_prefs: Dict) -> Dict:
    """Return prefs with an acousticness target derived from likes_acoustic when none is given."""
    if "acousticness" in user_prefs or "likes_acoustic" not in user_prefs:
        return user_prefs
    target = ACOUSTIC_LOVER_TARGET if user_prefs["likes_acoustic"] else ACOUSTIC_AVOIDER_TARGET
    return {**user_prefs, "acousticness": target}

def _matches_preference(wanted, actual) -> bool:
    """Return True if the song value equals the preference, or any of several accepted values."""
    accepted = wanted if isinstance(wanted, (list, tuple, set)) else [wanted]
    return str(actual).lower() in {str(value).lower() for value in accepted if value}

def _categorical_points(user_prefs: Dict, song: Dict, weights: Dict) -> List[Tuple[float, str]]:
    """Return (points, reason) pairs for each categorical feature the song matches."""
    matches = []
    for feature, label in CATEGORICAL_FEATURES.items():
        wanted = user_prefs.get(feature)
        if wanted and _matches_preference(wanted, song.get(feature, "")):
            points = weights[feature]
            matches.append((points, f"{label}: {song[feature]} (+{round(points, 2)})"))
    return matches

def _as_number(value, preference_name: str) -> float:
    """Convert a numeric preference to float, failing with a message that names the bad preference."""
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Preference '{preference_name}' must be a number, got {value!r}") from error

def _proximity_points(user_prefs: Dict, song: Dict, weights: Dict) -> List[Tuple[float, str]]:
    """Return (points, reason) pairs for how close each continuous feature is to its target."""
    results = []
    for feature, label in PROXIMITY_FEATURES.items():
        target = user_prefs.get(feature)
        if target is None or song.get(feature) is None:
            continue
        similarity = max(0.0, 1.0 - abs(_as_number(target, feature) - song[feature]))
        points = similarity * weights[feature]
        results.append((points, f"{label}: {similarity:.2f} (+{round(points, 2)})"))
    return results

def _bonus_points(user_prefs: Dict, song: Dict, weights: Dict) -> List[Tuple[float, str]]:
    """Return optional normalized tempo and popularity bonuses when the user asks for them."""
    bonuses = []
    if user_prefs.get("tempo_bpm") is not None and song.get("tempo_bpm") is not None:
        gap = abs(_as_number(user_prefs["tempo_bpm"], "tempo_bpm") - song["tempo_bpm"])
        similarity = max(0.0, 1.0 - gap / MAX_TEMPO_GAP_BPM)
        points = similarity * weights["tempo_bpm"]
        bonuses.append((points, f"Tempo proximity: {similarity:.2f} (+{round(points, 2)})"))
    if user_prefs.get("prefers_popular"):
        share = song.get("popularity", 0) / MAX_POPULARITY
        points = share * weights["popularity"]
        bonuses.append((points, f"Popularity bonus: {song.get('popularity', 0)} (+{round(points, 2)})"))
    return bonuses

def score_song(user_prefs: Dict, song: Dict, mode: str = DEFAULT_MODE) -> Tuple[float, List[str]]:
    """
    Scores a single song against user preferences.
    Required by recommend_songs() and src/main.py
    """
    weights = _weights_for(mode)
    prefs = _with_acoustic_target(user_prefs)
    contributions = (
        _categorical_points(prefs, song, weights)
        + _proximity_points(prefs, song, weights)
        + _bonus_points(prefs, song, weights)
    )
    score = sum(points for points, _ in contributions)
    reasons = [reason for _, reason in contributions]
    return round(score, 2), reasons

def _apply_diversity_penalty(candidate: ScoredSong, selected: List[ScoredSong]) -> ScoredSong:
    """Return a copy of the candidate with repetition penalties applied against the songs already picked."""
    song, score, reasons = candidate
    artist, genre = song.get("artist"), song.get("genre")
    picked_artists = {picked.get("artist") for picked, _, _ in selected}
    same_genre_count = sum(1 for picked, _, _ in selected if genre and picked.get("genre") == genre)

    penalties = []
    if artist and artist in picked_artists:
        penalties.append((ARTIST_REPEAT_PENALTY, f"Diversity penalty: artist {artist} already recommended (-{ARTIST_REPEAT_PENALTY})"))
    if same_genre_count >= MAX_GENRE_REPEATS:
        penalties.append((GENRE_REPEAT_PENALTY, f"Diversity penalty: genre {genre} already appears {same_genre_count}x (-{GENRE_REPEAT_PENALTY})"))
    if not penalties:
        return candidate

    total_penalty = sum(amount for amount, _ in penalties)
    return song, round(score - total_penalty, 2), reasons + [reason for _, reason in penalties]

def _rerank_with_diversity(ranked: List[ScoredSong], k: int) -> List[ScoredSong]:
    """Greedily build the top-k list, re-sorting after each pick so penalties reflect what is already chosen."""
    selected: List[ScoredSong] = []
    remaining = ranked
    while remaining and len(selected) < k:
        candidates = [_apply_diversity_penalty(item, selected) for item in remaining]
        # max() keeps the first of equal scores, so ties preserve the original ranking order.
        best_index = max(range(len(candidates)), key=lambda index: candidates[index][1])
        selected = selected + [candidates[best_index]]
        remaining = remaining[:best_index] + remaining[best_index + 1:]
    return selected

def recommend_songs(
    user_prefs: Dict,
    songs: List[Dict],
    k: int = 5,
    mode: str = DEFAULT_MODE,
    apply_diversity: bool = True,
) -> List[Tuple[Dict, float, str]]:
    """
    Functional implementation of the recommendation logic.
    Required by src/main.py
    """
    if k < 0:
        raise ValueError(f"k must be non-negative, got {k}")
    scored = [(song, *score_song(user_prefs, song, mode)) for song in songs]
    ranked = sorted(scored, key=lambda item: item[1], reverse=True)
    top = _rerank_with_diversity(ranked, k) if apply_diversity else ranked[:k]
    return [(song, score, "; ".join(reasons)) for song, score, reasons in top]
