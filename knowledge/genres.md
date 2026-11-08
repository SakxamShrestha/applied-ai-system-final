# Genre notes

How each genre in this catalog tends to behave, written to help the planner turn a
vague request into concrete targets.

## Lofi and ambient

Both are production styles before they are genres: heavily instrumental, low
speechiness, moderate acousticness, and deliberately low dynamic range. Lofi keeps
a drum pulse; ambient often has none. Either satisfies a request for background
music.

- hint: instrumentalness = 0.9
- hint: energy = 0.3

## Jazz

In this catalog jazz is instrumental and relaxed rather than vocal-led, and it is
the only genre present before 1990. Requests for "old" or "classy" music land here.

- hint: instrumentalness = 0.75
- hint: acousticness = 0.6

## Hip-hop and rap

Vocal-forward by definition: high speechiness, near-zero instrumentalness. A
request for instrumental hip-hop cannot be satisfied by this catalog, so expect the
agent to surrender either the genre or the instrumental requirement.

- hint: speechiness = 0.25
- hint: danceability = 0.8

## EDM and synthwave

Built for energy and movement. Synthwave trades tempo for nostalgia and sits in
the 2010s; EDM is the highest-energy genre available.

- hint: energy = 0.85
- hint: danceability = 0.8

## Acoustic, indie rock and indie pop

Guitar-led and vocal-led, with high acousticness for the acoustic entries. These
are the genres to reach for when someone wants something warm or organic.

- hint: acousticness = 0.7
- hint: instrumentalness = 0.1

## Pop and r&b

Polished, popular and vocal-led. Pop skews high-energy and recent; r&b skews
moody, romantic and slower.

- hint: prefers_popular = true
- hint: speechiness = 0.1

## Nepali classics

Older Nepali songs in this catalog are vocal-led and harmonium- or guitar-backed: high
acousticness, low energy, low valence. They are written to sit with a feeling rather than
lift it, so they fit reflective and late-night listening better than anything energetic.
Narayan Gopal, Arun Thapa and Aruna Lama are the reference points here, all pre-1990.

- hint: acousticness = 0.7
- hint: energy = 0.35
- hint: instrumentalness = 0.05

## Japanese city pop and J-pop

Two different things that often get asked for together. City pop is 1980s, warm, groovy and
nostalgic — high valence and danceability with analogue production. Modern J-pop is brighter
and much denser, often very high tempo, and leans on vocal performance. Both are polished
and popular rather than obscure.

- hint: prefers_popular = true
- hint: danceability = 0.7

## Kanye and Young Thug style hip-hop

Vocal-forward with near-zero instrumentalness and the highest speechiness in the catalog.
Energy sits high but not peak — it is weight rather than speed, so these do not compete with
EDM on raw energy and should not be ranked as if they did.

- hint: speechiness = 0.2
- hint: energy = 0.78
- hint: instrumentalness = 0.0
