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
