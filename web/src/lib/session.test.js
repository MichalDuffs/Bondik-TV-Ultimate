import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_THEME,
  SESSION_STORAGE_KEY,
  SESSION_VERSION,
  createDefaultSession,
  loadStoredSession,
  saveStoredSession,
} from "./session.js";

const validThemes = [
  "ultimate",
  "bondik",
  "minimal",
];

function library(
  activeId = "playlist-a",
) {
  return {
    version: 3,
    activeId,
    playlists: [
      { id: "playlist-a" },
      { id: "playlist-b" },
    ],
  };
}

function memoryStorage(initial = {}) {
  const values = new Map(
    Object.entries(initial),
  );
  const writes = [];

  return {
    getItem(key) {
      return values.has(key)
        ? values.get(key)
        : null;
    },
    setItem(key, value) {
      writes.push([key, value]);
      values.set(key, value);
    },
    values,
    writes,
  };
}

test(
  "default session is deterministic and follows the current active playlist",
  () => {
    assert.deepEqual(
      createDefaultSession({
        playlistLibrary:
          library("playlist-b"),
      }),
      {
        version: SESSION_VERSION,
        theme: DEFAULT_THEME,
        activePlaylistId: "playlist-b",
      },
    );
  },
);

test(
  "valid v1 session restores theme and active playlist",
  () => {
    const storage = memoryStorage({
      [SESSION_STORAGE_KEY]:
        JSON.stringify({
          version: 1,
          theme: "minimal",
          activePlaylistId:
            "playlist-b",
        }),
    });

    assert.deepEqual(
      loadStoredSession(storage, {
        validThemes,
        playlistLibrary: library(),
      }),
      {
        version: 1,
        theme: "minimal",
        activePlaylistId:
          "playlist-b",
      },
    );
  },
);

test(
  "invalid theme falls back without discarding a valid active playlist",
  () => {
    const storage = memoryStorage({
      [SESSION_STORAGE_KEY]:
        JSON.stringify({
          version: 1,
          theme: "unknown",
          activePlaylistId:
            "playlist-b",
        }),
    });

    assert.deepEqual(
      loadStoredSession(storage, {
        validThemes,
        playlistLibrary: library(),
      }),
      {
        version: 1,
        theme: DEFAULT_THEME,
        activePlaylistId:
          "playlist-b",
      },
    );
  },
);

test(
  "stale active playlist falls back to the normalized library active id",
  () => {
    const storage = memoryStorage({
      [SESSION_STORAGE_KEY]:
        JSON.stringify({
          version: 1,
          theme: "bondik",
          activePlaylistId:
            "playlist-missing",
        }),
    });

    assert.deepEqual(
      loadStoredSession(storage, {
        validThemes,
        playlistLibrary:
          library("playlist-b"),
      }),
      {
        version: 1,
        theme: "bondik",
        activePlaylistId:
          "playlist-b",
      },
    );
  },
);

test(
  "unknown session version falls back safely to v1 defaults",
  () => {
    const storage = memoryStorage({
      [SESSION_STORAGE_KEY]:
        JSON.stringify({
          version: 99,
          theme: "minimal",
          activePlaylistId:
            "playlist-b",
        }),
    });

    assert.deepEqual(
      loadStoredSession(storage, {
        validThemes,
        playlistLibrary: library(),
      }),
      {
        version: 1,
        theme: DEFAULT_THEME,
        activePlaylistId:
          "playlist-a",
      },
    );
  },
);

test(
  "save writes only the additive session key",
  () => {
    const storage = memoryStorage({
      "bondik-tv-playlist-library-v3":
        "leave-me-alone",
    });

    const saved = saveStoredSession(
      storage,
      {
        theme: "minimal",
        activePlaylistId:
          "playlist-b",
      },
      {
        validThemes,
        playlistLibrary: library(),
      },
    );

    assert.deepEqual(saved, {
      version: 1,
      theme: "minimal",
      activePlaylistId:
        "playlist-b",
    });

    assert.equal(
      storage.writes.length,
      1,
    );
    assert.equal(
      storage.writes[0][0],
      SESSION_STORAGE_KEY,
    );
    assert.equal(
      storage.values.get(
        "bondik-tv-playlist-library-v3",
      ),
      "leave-me-alone",
    );
  },
);
