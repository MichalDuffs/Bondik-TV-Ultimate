export const FAVORITES_STORAGE_KEY =
  "bondik-tv-favorites-v1";

export const MAX_FAVORITES = 200;

export function normalizeFavoriteIds(value) {
  if (!Array.isArray(value)) {
    return [];
  }

  const seen = new Set();
  const result = [];

  for (const item of value) {
    if (
      typeof item !== "string" ||
      item.length === 0 ||
      seen.has(item)
    ) {
      continue;
    }

    seen.add(item);
    result.push(item);

    if (result.length >= MAX_FAVORITES) {
      break;
    }
  }

  return result;
}

export function loadStoredFavorites(storage) {
  try {
    const raw = storage?.getItem?.(
      FAVORITES_STORAGE_KEY,
    );

    if (!raw) {
      return [];
    }

    return normalizeFavoriteIds(
      JSON.parse(raw),
    );
  } catch {
    return [];
  }
}

export function saveStoredFavorites(
  storage,
  value,
) {
  const normalized =
    normalizeFavoriteIds(value);

  try {
    storage?.setItem?.(
      FAVORITES_STORAGE_KEY,
      JSON.stringify(normalized),
    );
  } catch {
    // Storage can be unavailable in restricted browser contexts.
  }

  return normalized;
}
