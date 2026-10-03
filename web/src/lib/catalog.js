function channels(catalog) {
  return Array.isArray(catalog?.channels)
    ? catalog.channels
    : [];
}

export function favoriteChannels(
  catalog,
  favoriteIds,
) {
  const byId = new Map(
    channels(catalog).map((channel) => [
      channel.id,
      channel,
    ]),
  );

  return (
    Array.isArray(favoriteIds)
      ? favoriteIds
      : []
  )
    .map((id) => byId.get(id))
    .filter(Boolean);
}

export function epgChannels(catalog) {
  return channels(catalog).filter(
    (channel) =>
      channel?.epg?.enabled === true,
  );
}

export function summarizeCatalog(catalog) {
  const items = channels(catalog);
  const countries = new Set();
  const categories = new Set();
  const providers = new Set();

  let stable = 0;
  let testing = 0;
  let epgEnabled = 0;
  let fhd = 0;
  let hd = 0;
  let sd = 0;

  for (const channel of items) {
    if (channel?.status === "stable") {
      stable += 1;
    } else if (
      channel?.status === "testing"
    ) {
      testing += 1;
    }

    if (channel?.epg?.enabled === true) {
      epgEnabled += 1;
    }

    if (
      typeof channel?.country ===
        "string" &&
      channel.country
    ) {
      countries.add(channel.country);
    }

    if (
      typeof channel?.category ===
        "string" &&
      channel.category
    ) {
      categories.add(channel.category);
    }

    if (
      typeof channel?.provider ===
        "string" &&
      channel.provider
    ) {
      providers.add(channel.provider);
    }

    const quality = String(
      channel?.stream?.quality ?? "",
    ).toUpperCase();

    if (quality === "FHD") {
      fhd += 1;
    } else if (quality === "HD") {
      hd += 1;
    } else if (quality === "SD") {
      sd += 1;
    }
  }

  return {
    channels: items.length,
    stable,
    testing,
    epgEnabled,
    countries: countries.size,
    categories: categories.size,
    providers: providers.size,
    fhd,
    hd,
    sd,
  };
}

export function countByField(
  catalog,
  field,
) {
  const counts = new Map();

  for (const channel of channels(catalog)) {
    const value = channel?.[field];

    if (
      typeof value !== "string" ||
      value.length === 0
    ) {
      continue;
    }

    counts.set(
      value,
      (counts.get(value) ?? 0) + 1,
    );
  }

  return [...counts.entries()]
    .map(([name, count]) => ({
      name,
      count,
    }))
    .sort(
      (first, second) =>
        second.count - first.count ||
        first.name.localeCompare(
          second.name,
        ),
    );
}
