import assert from "node:assert/strict";
import test from "node:test";

import {
  FAVORITES_STORAGE_KEY,
  MAX_FAVORITES,
  loadStoredFavorites,
  normalizeFavoriteIds,
  saveStoredFavorites,
} from "./favorites.js";

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
  "favorites keep unique non-empty string ids",
  () => {
    assert.deepEqual(
      normalizeFavoriteIds([
        "polar-tv-cz",
        "",
        "polar-tv-cz",
        7,
        "joj-sk",
      ]),
      ["polar-tv-cz", "joj-sk"],
    );
  },
);

test(
  "invalid favorite payload fails closed to empty",
  () => {
    assert.deepEqual(
      normalizeFavoriteIds({
        id: "polar-tv-cz",
      }),
      [],
    );
  },
);

test(
  "favorite list is bounded",
  () => {
    const input = Array.from(
      { length: MAX_FAVORITES + 25 },
      (_, index) => `channel-${index}`,
    );

    assert.equal(
      normalizeFavoriteIds(input).length,
      MAX_FAVORITES,
    );
  },
);

test(
  "stored favorites restore valid ids",
  () => {
    const storage = memoryStorage({
      [FAVORITES_STORAGE_KEY]:
        JSON.stringify([
          "polar-tv-cz",
          "polar-tv-cz",
          "joj-sk",
        ]),
    });

    assert.deepEqual(
      loadStoredFavorites(storage),
      ["polar-tv-cz", "joj-sk"],
    );
  },
);

test(
  "corrupt favorites storage fails closed",
  () => {
    const storage = memoryStorage({
      [FAVORITES_STORAGE_KEY]: "{broken",
    });

    assert.deepEqual(
      loadStoredFavorites(storage),
      [],
    );
  },
);

test(
  "save writes only normalized favorites key",
  () => {
    const storage = memoryStorage({
      "bondik-tv-session-v1":
        "leave-session-alone",
    });

    const saved = saveStoredFavorites(
      storage,
      [
        "polar-tv-cz",
        "polar-tv-cz",
        "joj-sk",
      ],
    );

    assert.deepEqual(
      saved,
      ["polar-tv-cz", "joj-sk"],
    );
    assert.equal(
      storage.writes.length,
      1,
    );
    assert.equal(
      storage.writes[0][0],
      FAVORITES_STORAGE_KEY,
    );
    assert.equal(
      storage.values.get(
        "bondik-tv-session-v1",
      ),
      "leave-session-alone",
    );
  },
);
