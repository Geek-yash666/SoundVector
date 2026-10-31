/* Small shared state primitives. No DOM, network, or inferred music metadata. */
(function (root) {
  const key = (track) =>
    `${String(track?.name || "")
      .trim()
      .toLocaleLowerCase()}||${String(track?.artist || "")
      .trim()
      .toLocaleLowerCase()}`;
  const escape = (value) =>
    String(value ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
  const time = (seconds) => {
    const value = Number.isFinite(Number(seconds))
      ? Math.max(0, Number(seconds))
      : 0;
    return `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, "0")}`;
  };
  const unique = (tracks) => [
    ...new Map((tracks || []).map((t) => [key(t), t])).values(),
  ];
  const gate = () => {
    let generation = 0;
    return {
      next: () => ++generation,
      valid: (ticket) => ticket === generation,
      cancel: () => {
        generation += 1;
      },
    };
  };
  function safeUrl(value, media = false) {
    try {
      const url = new URL(String(value || "").replace(/^http:/, "https:"));
      if (url.protocol !== "https:") return "";
      if (
        !media &&
        ![
          "deezer.com",
          "www.deezer.com",
          "music.apple.com",
          "itunes.apple.com",
          "www.last.fm",
          "last.fm",
          "music.youtube.com",
          "www.youtube.com",
        ].includes(url.hostname)
      )
        return "";
      return url.href;
    } catch {
      return "";
    }
  }
  const signal = (history, track) =>
    history.find((item) => key(item) === key(track))?.signal || "none";
  function selectedTrack(params, cached) {
    if (!params.name || !params.artist) return null;
    if (cached && key(cached) === key(params)) return cached;
    const row = Number(params.row);
    return {
      name: params.name,
      artist: params.artist,
      row: Number.isInteger(row) && row >= 0 ? row : -1,
    };
  }
  const api = {
    key,
    escape,
    time,
    unique,
    gate,
    safeUrl,
    signal,
    selectedTrack,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.SoundVectorCore = api;
})(typeof globalThis === "undefined" ? this : globalThis);
