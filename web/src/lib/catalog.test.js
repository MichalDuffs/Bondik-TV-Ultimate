import assert from "node:assert/strict";
import test from "node:test";

import {
  countByField,
  epgChannels,
  favoriteChannels,
  summarizeCatalog,
} from "./catalog.js";

function sampleCatalog() {
  return {
    channels: [
      {
        id: "a",
        country: "CZ",
        category: "general",
        provider: "one",
        status: "stable",
        epg: { enabled: true },
        stream: { quality: "FHD" },
      },
      {
        id: "b",
        country: "SK",
        category: "news",
        provider: "two",
        status: "testing",
        epg: { enabled: false },
        stream: { quality: "HD" },
      },
      {
        id: "c",
        country: "CZ",
        category: "general",
        provider: "one",
        status: "stable",
        epg: { enabled: true },
        stream: { quality: "SD" },
      },
    ],
  };
}

test(
  "catalog summary reports current dimensions",
  () => {
    assert.deepEqual(
      summarizeCatalog(sampleCatalog()),
      {
        channels: 3,
        stable: 2,
        testing: 1,
        epgEnabled: 2,
        countries: 2,
        categories: 2,
        providers: 2,
        fhd: 1,
        hd: 1,
        sd: 1,
      },
    );
  },
);

test(
  "catalog summary safely handles missing data",
  () => {
    assert.equal(
      summarizeCatalog(null).channels,
      0,
    );
  },
);

test(
  "favorite channels preserve stored order and skip stale ids",
  () => {
    assert.deepEqual(
      favoriteChannels(
        sampleCatalog(),
        ["c", "missing", "a"],
      ).map((channel) => channel.id),
      ["c", "a"],
    );
  },
);

test(
  "epg view includes only enabled channels",
  () => {
    assert.deepEqual(
      epgChannels(
        sampleCatalog(),
      ).map((channel) => channel.id),
      ["a", "c"],
    );
  },
);

test(
  "field counts are sorted by count then name",
  () => {
    assert.deepEqual(
      countByField(
        sampleCatalog(),
        "country",
      ),
      [
        { name: "CZ", count: 2 },
        { name: "SK", count: 1 },
      ],
    );
  },
);

test(
  "field counts ignore missing string fields",
  () => {
    const catalog = sampleCatalog();
    catalog.channels.push({
      id: "d",
      country: null,
    });

    assert.deepEqual(
      countByField(catalog, "country"),
      [
        { name: "CZ", count: 2 },
        { name: "SK", count: 1 },
      ],
    );
  },
);
