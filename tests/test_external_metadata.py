"""Provider metadata must not fabricate tastes or attach another artist's preview."""
from concurrent.futures import Future

from backend import external_api as api


def test_preview_fallback_rejects_other_artist(monkeypatch):
    wrong = {'title': 'Song', 'artist': {'name': 'Cover Artist'}, 'preview': 'wrong-preview', 'link': 'wrong-link'}
    monkeypatch.setattr(api, '_fetch_json', lambda url: {'data': [wrong]})
    assert api._fetch_deezer_enrichment('Original Artist', 'Song') == {}


def test_itunes_artwork_and_preview_come_from_the_same_recording(monkeypatch):
    correct = {'trackName': 'Song', 'artistName': 'Original Artist', 'artworkUrl100': 'correct-art', 'trackViewUrl': 'correct-link'}
    wrong = {'trackName': 'Song', 'artistName': 'Cover Artist', 'previewUrl': 'wrong-preview'}
    monkeypatch.setattr(api, '_fetch_json', lambda url: {'results': [correct, wrong]})
    result = api._fetch_itunes_enrichment('Original Artist', 'Song')
    assert result['itunes_album_art'] == 'correct-art'
    assert result['itunes_preview_url'] == ''


def test_primary_artist_collaboration_matches_recording():
    track = {'trackName': 'Song (From "Movie")', 'artistName': 'Original Artist & Composer', 'previewUrl': 'correct-preview'}
    assert api._matching_recording([track], 'Original Artist', 'Song', 'itunes') == track


def test_unknown_genre_does_not_become_pop(monkeypatch):
    track = {'title': 'Song', 'artist': {'name': 'Regional Artist'}, 'id': 1}
    monkeypatch.setattr(api, '_fetch_json', lambda url: {'data': [track]})
    assert api._search_deezer_tracks('Song', 5)[0]['base_genres'] == []


def test_timeout_preserves_completed_provider_results():
    complete, pending = Future(), Future()
    complete.set_result(['track'])
    results = [future.result() for future in api._completed_within([complete, pending], timeout=.01)]
    assert results == [['track']]
    assert pending.cancelled()
