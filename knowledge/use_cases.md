# Listening situations

Notes on what people actually want in common listening situations. These are
editorial judgements that are not derivable from the song columns, which is why
they live here rather than in `data/songs.csv`.

## Deep focus, studying and coding

Work that competes for language processing is disrupted by lyrics far more than by
tempo. Listeners who ask for focus music almost always mean near-instrumental
tracks at a steady, unobtrusive energy, and they tolerate repetition that would be
boring in active listening.

- hint: instrumentalness = 0.95
- hint: speechiness = 0.0
- hint: energy = 0.3
- hint: mode = vibe_and_energy

## Workouts, gym sessions and hype

Perceived exertion drops when tempo is high and the beat is predictable. Vocals
are welcome here: they carry the motivational content. Danceability matters more
than genre purity.

- hint: energy = 0.9
- hint: danceability = 0.85
- hint: tempo_bpm = 150
- hint: mode = vibe_and_energy

## Late night, winding down and sleep

Late-night listening wants low energy, high acousticness and no sudden dynamics.
Instrumental is preferred but not required; quiet vocals are fine.

- hint: energy = 0.2
- hint: acousticness = 0.8
- hint: instrumentalness = 0.6

## Driving and road trips

Driving music needs mid-to-high energy with enough vocal presence to sing along.
Nostalgia plays well here, which is why older decades over-perform on road trips.

- hint: energy = 0.7
- hint: danceability = 0.7
- hint: detailed_mood_tag = nostalgic

## Parties and social settings

Party listening is about danceability and familiarity rather than personal taste.
Popular tracks outperform deep cuts because recognition drives participation.

- hint: danceability = 0.85
- hint: energy = 0.85
- hint: prefers_popular = true
