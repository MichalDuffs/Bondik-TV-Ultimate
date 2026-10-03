export const SESSION_STORAGE_KEY =
  "bondik-tv-session-v1";

export const SESSION_VERSION = 1;
export const DEFAULT_THEME = "ultimate";

function playlistIds(playlistLibrary) {
  if (!playlistLibrary?.playlists) {
    return [];
  }

  return playlistLibrary.playlists
    .map((playlist) => playlist?.id)
    .filter(
      (id) =>
        typeof id === "string" &&
        id.length > 0,
    );
}

export function createDefaultSession({
  playlistLibrary,
} = {}) {
  const ids = playlistIds(playlistLibrary);

  const activePlaylistId =
    typeof playlistLibrary?.activeId === "string" &&
    ids.includes(playlistLibrary.activeId)
      ? playlistLibrary.activeId
      : (ids[0] ?? "");

  return {
    version: SESSION_VERSION,
    theme: DEFAULT_THEME,
    activePlaylistId,
  };
}

export function normalizeSession(
  value,
  {
    validThemes = [],
    playlistLibrary,
  } = {},
) {
  const fallback =
    createDefaultSession({ playlistLibrary });

  if (
    !value ||
    typeof value !== "object" ||
    value.version !== SESSION_VERSION
  ) {
    return fallback;
  }

  const theme =
    typeof value.theme === "string" &&
    validThemes.includes(value.theme)
      ? value.theme
      : fallback.theme;

  const ids = playlistIds(playlistLibrary);

  const activePlaylistId =
    typeof value.activePlaylistId === "string" &&
    ids.includes(value.activePlaylistId)
      ? value.activePlaylistId
      : fallback.activePlaylistId;

  return {
    version: SESSION_VERSION,
    theme,
    activePlaylistId,
  };
}

export function loadStoredSession(
  storage,
  options = {},
) {
  const fallback =
    createDefaultSession(options);

  try {
    const raw =
      storage?.getItem?.(
        SESSION_STORAGE_KEY,
      );

    if (!raw) {
      return fallback;
    }

    return normalizeSession(
      JSON.parse(raw),
      options,
    );
  } catch {
    return fallback;
  }
}

export function saveStoredSession(
  storage,
  value,
  options = {},
) {
  const normalized = normalizeSession(
    {
      ...value,
      version: SESSION_VERSION,
    },
    options,
  );

  try {
    storage?.setItem?.(
      SESSION_STORAGE_KEY,
      JSON.stringify(normalized),
    );
  } catch {
    // Storage can be unavailable in restricted browser contexts.
  }

  return normalized;
}
