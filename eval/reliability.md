# SoundVector Reliability Report

_DJ backend: `template` · seeds: 10_

| Metric | Value | Target |
|---|---|---|
| same-artist recall@50 | 1.000 | > 0.80 |
| intra-list diversity | 0.548 | 0.15 - 0.90 |
| genre fidelity | 0.940 | > 0.60 |
| NL-query accuracy | 0.800 | > 0.80 |
| RAG groundedness | 1.000 | > 0.90 |
| median latency | 4.6 ms | < 500 ms |

## Natural-language query assertions

| Query | Retrieved means | Expected | Pass |
|---|---|---|---|
| sad acoustic ballad | energy=0.34, valence=0.43, danceability=0.75, acousticness=0.72 | valence<0.5, acousticness>0.4 | ✅ |
| high energy workout | energy=0.77, valence=0.6, danceability=0.67, acousticness=0.08 | energy>0.6 | ✅ |
| chill lo-fi study | energy=0.22, valence=0.15, danceability=0.63, acousticness=0.84 | energy<0.5, acousticness>0.4 | ✅ |
| happy upbeat dance party | energy=0.88, valence=0.38, danceability=0.57, acousticness=0.06 | valence>0.5, danceability>0.5 | ❌ |
| dark moody late night | energy=0.56, valence=0.34, danceability=0.59, acousticness=0.21 | valence<0.5 | ✅ |

## RAG groundedness by seed

| Seed | Groundedness | Claims |
|---|---|---|
| Blinding Lights — The Weeknd | 100% | 6 |
| Summertime Sadness — Lana Del Rey | 100% | 6 |
| Treat You Better — Shawn Mendes | 100% | 6 |
| Believer — Imagine Dragons | 100% | 6 |
| Shape of You — Ed Sheeran | 100% | 6 |
| bad guy — Billie Eilish | 100% | 4 |
