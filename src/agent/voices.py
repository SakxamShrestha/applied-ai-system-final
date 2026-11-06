"""Specialised explanation voices over the recommender's own reason strings.

The scorer already says *why* a song was picked ("Genre match: lofi (+0.75)").
These voices re-express the same facts in a constrained style, chosen by few-shot
style templates rather than free generation, so the explanation stays faithful to
the score and is reproducible run to run.
"""

from typing import Dict, List, Sequence, Tuple

VOICE_PLAIN = "plain"
VOICE_DJ = "dj"
VOICE_CRITIC = "critic"
VOICES = (VOICE_PLAIN, VOICE_DJ, VOICE_CRITIC)

# Energy bands used to choose wording. Numbers stay visible in the critic voice.
HIGH_ENERGY = 0.7
LOW_ENERGY = 0.4
STRONG_SCORE = 4.5

# Reason label -> short aspect key, read back from score_song()'s own reason text.
ASPECT_LABELS = {
    "Genre match": "genre",
    "Mood match": "mood",
    "Decade match": "decade",
    "Mood tag match": "mood_tag",
    "Energy proximity": "energy",
    "Danceability proximity": "danceability",
    "Acousticness proximity": "acousticness",
    "Instrumentalness proximity": "instrumentalness",
    "Speechiness proximity": "speechiness",
    "Tempo proximity": "tempo",
    "Popularity bonus": "popularity",
}

PLAIN_FRAGMENTS = {
    "genre": "it is the {genre} you asked for",
    "mood": "the mood matches",
    "decade": "it is from the {release_decade}",
    "mood_tag": "the detailed mood matches",
    "energy": "the energy is close to your target",
    "danceability": "it is about as danceable as you wanted",
    "acousticness": "the acoustic balance fits",
    "instrumentalness": "there is little or no singing",
    "speechiness": "the amount of spoken word fits",
    "tempo": "the tempo is near your target",
    "popularity": "it is a well known track",
}
DJ_FRAGMENTS = {
    "genre": "straight-up {genre}",
    "mood": "the mood is dialled in",
    "decade": "pure {release_decade}",
    "mood_tag": "exactly the vibe you named",
    "energy": "the energy lands right where you wanted it",
    "danceability": "it moves",
    "acousticness": "warm and acoustic",
    "instrumentalness": "no vocals in your way",
    "speechiness": "the voice-to-beat balance is right",
    "tempo": "the tempo is on the money",
    "popularity": "and you already know this one",
}
CRITIC_FRAGMENTS = {
    "genre": "genre {genre}",
    "mood": "mood {mood}",
    "decade": "released {release_decade}",
    "mood_tag": "mood tag {detailed_mood_tag}",
    "energy": "energy {energy:.2f}",
    "danceability": "danceability {danceability:.2f}",
    "acousticness": "acousticness {acousticness:.2f}",
    "instrumentalness": "instrumentalness {instrumentalness:.2f}",
    "speechiness": "speechiness {speechiness:.2f}",
    "tempo": "{tempo_bpm:.0f} BPM",
    "popularity": "popularity {popularity}",
}

DJ_OPENERS = (
    "Up next,",
    "Right behind it,",
    "Keep it rolling with",
    "Then we have",
    "And to close,",
)
CRITIC_VERDICTS = (
    "the clearest fit in the catalog",
    "a defensible second choice",
    "reasonable, with caveats",
    "a weaker fit kept for variety",
    "included mainly to avoid repeating artists",
)


class UnknownVoiceError(ValueError):
    """Raised when a caller asks for a voice that does not exist."""


def aspects(reason_text: str) -> Tuple[str, ...]:
    """Which aspects the scorer actually credited, in the order it reported them."""
    found: List[str] = []
    for chunk in (reason_text or "").split(";"):
        label = chunk.split(":")[0].strip()
        aspect = ASPECT_LABELS.get(label)
        if aspect is not None and aspect not in found:
            found.append(aspect)
    return tuple(found)


def _fill(template: str, song: Dict) -> str:
    try:
        return template.format(**song)
    except (KeyError, IndexError, ValueError):
        # A template referring to a column this song lacks is dropped rather than
        # printed half-rendered.
        return ""


def _fragments(song: Dict, found: Sequence[str], table: Dict[str, str]) -> List[str]:
    rendered = [_fill(table[aspect], song) for aspect in found if aspect in table]
    return [item for item in rendered if item]


def _plain(song: Dict, score: float, found: Sequence[str], rank: int) -> str:
    parts = _fragments(song, found, PLAIN_FRAGMENTS)
    if not parts:
        return (
            f"{song.get('title', 'This track')} scored {score:.2f}; nothing in your request "
            "matched directly, so it is here as a near miss."
        )
    body = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + f" and {parts[-1]}"
    return f"{song.get('title', 'This track')}: {body}."


def _dj(song: Dict, score: float, found: Sequence[str], rank: int) -> str:
    opener = DJ_OPENERS[min(rank - 1, len(DJ_OPENERS) - 1)]
    parts = _fragments(song, found, DJ_FRAGMENTS)
    title = song.get("title", "this one")
    artist = song.get("artist", "unknown")
    if not parts:
        return f"{opener} {title} by {artist} — not what you asked for, but it is the closest I have."
    body = " — ".join(parts[:2])
    tail = "!" if float(song.get("energy", 0.0)) >= HIGH_ENERGY else "."
    return f"{opener} {title} by {artist} — {body}{tail}"


def _critic(song: Dict, score: float, found: Sequence[str], rank: int) -> str:
    verdict = CRITIC_VERDICTS[min(rank - 1, len(CRITIC_VERDICTS) - 1)]
    parts = _fragments(song, found, CRITIC_FRAGMENTS)
    evidence = ", ".join(parts) if parts else "no credited matches"
    confidence_word = "strong" if score >= STRONG_SCORE else "moderate"
    return (
        f"{song.get('title', 'Untitled')} ({song.get('artist', 'unknown')}) — {verdict}; "
        f"{evidence}; score {score:.2f} ({confidence_word})."
    )


RENDERERS = {VOICE_PLAIN: _plain, VOICE_DJ: _dj, VOICE_CRITIC: _critic}


def explain(song: Dict, score: float, reason_text: str, voice: str = VOICE_PLAIN, rank: int = 1) -> str:
    """One voiced sentence for one recommendation."""
    if voice not in RENDERERS:
        raise UnknownVoiceError(f"Unknown voice '{voice}'. Choose one of: {', '.join(VOICES)}.")
    return RENDERERS[voice](song, score, aspects(reason_text), rank)


def explain_all(
    recommendations: Sequence[Tuple[Dict, float, str]], voice: str = VOICE_PLAIN
) -> Tuple[str, ...]:
    """Voiced sentences for a whole result set, numbered by rank."""
    return tuple(
        explain(song, score, reason, voice=voice, rank=rank)
        for rank, (song, score, reason) in enumerate(recommendations, start=1)
    )


def voice_stats(lines: Sequence[str]) -> Dict[str, float]:
    """Simple measurements so baseline and specialised output can be compared."""
    words = [word for line in lines for word in line.split()]
    return {
        "lines": len(lines),
        "total_words": len(words),
        "mean_words_per_line": round(len(words) / len(lines), 1) if lines else 0.0,
        "unique_words": len({word.strip(".,;—!").lower() for word in words}),
        "digits": sum(1 for character in " ".join(lines) if character.isdigit()),
    }
