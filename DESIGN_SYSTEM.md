# SoundVector: Paper & Violet

The interface starts with music, using a horizontal masthead, a compact numbered rotation, and a saved-song index. No promotional hero or decorative introductory copy. Song artwork supplies variety; interface surfaces use solid colors.

## Color roles

| Token | Value | Role |
| --- | --- | --- |
| Canvas | `#f6f2ed` | Warm paper behind the collection |
| Surface | `#fffdfb` | Search, rotation, menus |
| Text | `#292331` | Titles and primary information |
| Secondary | `#68606e` | Artist names and supporting information |
| Violet | `#6840bd` | Primary actions, navigation selection, focus |
| Violet hover | `#54319e` | Hover on primary actions |
| Lilac | `#e9dff6` | Saved state and secondary emphasis |
| Divider | `#dcd4df` | Grouping and separation |
| Player ink | `#2d2536` | Persistent playback utility |
| Player accent | `#d4b9ff` | Playback and progress controls |
| Error | `#a12843` | Actionable errors |

No gradients. State also uses labels, filled icons, outlines, and ARIA attributes. Semantic text pairs measured at 4.69:1 or higher; white on violet is 6.87:1. These token checks do not establish a full accessibility certification.

## Type and spacing

Use the platform system font. Page titles are 30–44px, section titles 20–22px, song titles 13–14px, and supporting text 12–14px. Titles describe the destination or content. Supporting copy explains an action or actual recommendation context. No uppercase promotional eyebrows.

Base spacing is 4px, with common gaps of 8, 12, 16, 20, 24, 28, and 32px. Controls use 8–9px corners; content groups use 12px corners. Avoid nesting a card inside another card unless it represents an independently selectable item. Album art stays square. Artist portraits are circular.

Pointer controls use 32px targets on dense song rows; coarse-pointer controls use 44px targets. Primary actions retain 44px targets. Track title and artist text remain separate destinations as text links. Focus is a visible 3px violet outline with an offset. Native dialogs provide focus containment and Escape dismissal. Reduced motion disables decorative transitions and pulsing placeholders.

## Components and behavior

- **Navigation:** horizontal Home / Discover / Library links on desktop; a compact masthead and bottom navigation on phones. Search stays available across destinations.
- **Search:** a labeled combobox, clear control, keyboard suggestions, and full results on unselected Enter. Arrow keys explicitly select a suggestion; Enter on a selected suggestion opens it. Results have All / Songs / Artists / Albums scopes. Existing query text survives the transition.
- **Home:** a compact two-column rotation and discovery index on desktop, followed by real public playlists and a separately attributed current chart. Explicit saves lead; completed previews add lighter evidence. Language and artist cohorts receive coverage before global relevance fills the shelf. Saved and hidden songs are excluded from recommendations. Save and Undo refresh Home in place.
- **Song:** artwork, title, artist, adjacent icon-only like and dislike, real song length, album link, preview, and an anchored three-dot menu. The 292px menu provides song radio, verified album navigation, insights, Play next, Add to queue, dislike, details, and provider links. Desktop items are 34px high; touch items are 44px. Arrow keys and Escape support keyboard use.
- **Album:** verify the selected provider release contains the recording. Use its exact release when available; otherwise resolve by title and artist. Follow provider pagination and show completeness against the advertised track count. Keep live performances and remixes separate from original recordings. Unverified recordings get an explicit unavailable state.
- **Insights:** a contextual panel opened from the song menu, song page, or player. Identify actual Gemini responses. Gemini uses Google Search grounding to find a specific recording story, with source links and Search attribution. Missing grounding shows a truthful unavailable state. Quota exhaustion has its own message and retry; generic catalog descriptions are not presented as insights. No invented measurements for external songs.
- **Mood mixes:** when a provider treats mood words as title terms and returns nothing, gather verified regional candidates and rank only catalog matches with real audio features. Unknown prompts and missing measurement coverage get an honest empty state.
- **Player:** a solid ink surface, preview transport, time, seek, save, queue, volume, and access to current-song options. Narrow layouts prioritize transport and song identity. The current song title opens its menu on every viewport.
- **Queue:** Play next inserts after the current item; Add to queue appends. Adding to an empty queue opens the queue without starting audio. Repeated manual entries retain their positions. Playing an individual song builds a diverse radio queue; explicitly playing an album or playlist retains its sequence. Late radio responses cannot replace manual queue edits.
- **Feedback:** selected thumb icons are filled and expose `aria-pressed`. Undo remains available in a status toast. Errors stay close to the failed action and offer retry where useful.

## Responsive rules

At 950px the masthead places search on its own row and Home becomes one column. At 640px, bottom navigation appears and the player compacts above it. Long release heroes stack at 390px. Dense rows remain a single column on phones. No horizontal content scrolling is required. Test long titles, keyboard focus, modal menus, and the player together.

## Data and ranking boundaries

Search paints indexed matches after a short debounce, then merges independent provider results without a network barrier. Title corrections use the indexed catalog and cached provider recordings. The input has one explicit clear button and avoids duplicate native cancellation chrome. Original recordings, remixes and live performances have separate cache identities. Provider rank cannot replace catalog popularity or measured features. Metadata enrichment updates artwork, credits, albums and lengths in place.

Up next combines embedding, audio, genre and catalog popularity with optional Last.fm listening-neighbor evidence. Related assigns a stronger artist weight and allows more recordings from the same artist. Both cap repetition and honor hidden songs. No named artist, song or language is baked into the ranking. Language coverage requires recording metadata; unknown languages remain unknown.

Credits preserve the roles providers actually supply. A generic Artist or Main credit is not relabeled as a singer. Song details show available credited contributors, duration, release, label, identifiers, content flags and recording genre. Catalog audio estimates are disclosed separately.

When saved recordings have known lengths, discovery avoids very short score cues relative to that listening history. Album track lists and Related still retain those recordings.
