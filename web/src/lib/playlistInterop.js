const MAX_IMPORT_BYTES = 5 * 1024 * 1024;
const MAX_IMPORTED_CHANNELS = 1000;

function stripBom(value) {
  return String(value ?? "").replace(/^\uFEFF/, "");
}

function normalizeHeader(value) {
  return String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, "_");
}

function safeFileName(value) {
  return (
    String(value || "Bondik-TV-Playlist")
      .replace(/[<>:"/\\|?*]/g, "-")
      .split("")
      .map((character) =>
        character.charCodeAt(0) < 32
          ? "-"
          : character,
      )
      .join("")
      .replace(/\s+/g, "-")
      .replace(/-+/g, "-")
      .replace(/^-|-$/g, "") ||
    "Bondik-TV-Playlist"
  );
}

function sourceName(value) {
  const fallback = "Importovany playlist";

  if (!value) {
    return fallback;
  }

  try {
    const url = new URL(value);
    const part =
      url.pathname.split("/").filter(Boolean).at(-1) ||
      url.hostname;

    return decodeURIComponent(part)
      .replace(/\.(m3u8?|csv)$/i, "")
      .trim() || fallback;
  } catch {
    return String(value)
      .split(/[\\/]/)
      .at(-1)
      ?.replace(/\.(m3u8?|csv)$/i, "")
      .trim() || fallback;
  }
}

function stableHash(value) {
  let hash = 2166136261;

  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }

  return (hash >>> 0).toString(16).padStart(8, "0");
}

function isStreamLocation(value) {
  return /^[a-z][a-z0-9+.-]*:/i.test(
    String(value ?? "").trim(),
  );
}

function resolveLocation(value, sourceUrl) {
  const location = String(value ?? "").trim();

  if (!location) {
    return "";
  }

  if (isStreamLocation(location)) {
    return location;
  }

  if (sourceUrl) {
    try {
      return new URL(location, sourceUrl).href;
    } catch {
      return location;
    }
  }

  return location;
}

function inferStreamFormat(url) {
  const value = String(url ?? "").toLowerCase();

  if (
    value.includes(".m3u8") ||
    value.startsWith("hls:")
  ) {
    return "hls";
  }

  if (value.includes(".mpd")) {
    return "dash";
  }

  if (value.startsWith("rtmp:")) {
    return "rtmp";
  }

  if (value.startsWith("rtsp:")) {
    return "rtsp";
  }

  if (
    value.startsWith("udp:") ||
    value.startsWith("rtp:")
  ) {
    return "udp";
  }

  return "unknown";
}

function createExternalChannel({
  name,
  url,
  country = "",
  category = "external",
  provider = "External",
  status = "external",
  tvgId = "",
  logo = "",
  language = "",
  quality = "",
}) {
  const streamUrl = String(url ?? "").trim();
  const channelName =
    String(name ?? "").trim() ||
    sourceName(streamUrl);

  return {
    id: `external-${stableHash(
      `${streamUrl}\n${channelName}`,
    )}`,
    name: channelName,
    country: String(country ?? "").trim().toUpperCase(),
    language: String(language ?? "").trim(),
    category:
      String(category ?? "").trim() || "external",
    provider:
      String(provider ?? "").trim() || "External",
    status:
      String(status ?? "").trim() || "external",
    stream: {
      url: streamUrl,
      format: inferStreamFormat(streamUrl),
      quality: String(quality ?? "").trim(),
    },
    epg: {
      id: String(tvgId ?? "").trim(),
      source: "",
      enabled: Boolean(String(tvgId ?? "").trim()),
    },
    logo: {
      url: String(logo ?? "").trim(),
      local: "",
    },
    metadata: {
      website: "",
      notes: "",
      external: true,
    },
  };
}

function parseM3uAttributes(line) {
  const attributes = {};
  const pattern =
    /([A-Za-z0-9_-]+)="([^"]*)"/g;

  let match = pattern.exec(line);

  while (match) {
    attributes[
      normalizeHeader(match[1])
    ] = match[2];

    match = pattern.exec(line);
  }

  return attributes;
}

function limitResult(result) {
  if (
    result.channels.length <=
    MAX_IMPORTED_CHANNELS
  ) {
    return result;
  }

  return {
    ...result,
    channels: result.channels.slice(
      0,
      MAX_IMPORTED_CHANNELS,
    ),
    warnings: [
      ...(result.warnings ?? []),
      `Import byl omezen na ${MAX_IMPORTED_CHANNELS} stanic.`,
    ],
  };
}

function parseM3u({
  text,
  fileName,
  sourceUrl,
}) {
  const normalized = stripBom(text)
    .replace(/\r\n?/g, "\n");

  const isHlsManifest =
    /^#EXT-X-/m.test(normalized);

  if (isHlsManifest) {
    if (!sourceUrl) {
      throw new Error(
        "Soubor je HLS stream manifest, ne seznam stanic. Otevri ho pres URL.",
      );
    }

    return {
      format: "m3u8",
      name: sourceName(sourceUrl),
      sourceUrl,
      warnings: [
        "URL byla rozpoznana jako primo prehratelny HLS stream.",
      ],
      channels: [
        createExternalChannel({
          name: sourceName(sourceUrl),
          url: sourceUrl,
        }),
      ],
    };
  }

  const lines = normalized.split("\n");
  const channels = [];
  let pending = null;

  lines.forEach((rawLine) => {
    const line = rawLine.trim();

    if (!line) {
      return;
    }

    if (line.startsWith("#EXTINF")) {
      const attributes =
        parseM3uAttributes(line);

      const comma = line.indexOf(",");
      const title =
        comma >= 0
          ? line.slice(comma + 1).trim()
          : "";

      pending = {
        name:
          title ||
          attributes.tvg_name ||
          "",
        tvgId:
          attributes.tvg_id || "",
        logo:
          attributes.tvg_logo || "",
        category:
          attributes.group_title ||
          "external",
      };

      return;
    }

    if (line.startsWith("#")) {
      return;
    }

    const url = resolveLocation(
      line,
      sourceUrl,
    );

    if (!url) {
      return;
    }

    channels.push(
      createExternalChannel({
        name:
          pending?.name ||
          sourceName(url),
        url,
        category:
          pending?.category ||
          "external",
        tvgId:
          pending?.tvgId || "",
        logo:
          pending?.logo || "",
      }),
    );

    pending = null;
  });

  if (channels.length === 0) {
    throw new Error(
      "V M3U/M3U8 nebyla nalezena zadna stanice.",
    );
  }

  return limitResult({
    format:
      /\.m3u8$/i.test(
        fileName || sourceUrl || "",
      )
        ? "m3u8"
        : "m3u",
    name: sourceName(
      fileName || sourceUrl,
    ),
    sourceUrl,
    warnings: [],
    channels,
  });
}

function parseDelimitedLine(line, delimiter) {
  const values = [];
  let value = "";
  let quoted = false;

  for (
    let index = 0;
    index < line.length;
    index += 1
  ) {
    const character = line[index];

    if (character === '"') {
      if (
        quoted &&
        line[index + 1] === '"'
      ) {
        value += '"';
        index += 1;
      } else {
        quoted = !quoted;
      }

      continue;
    }

    if (
      character === delimiter &&
      !quoted
    ) {
      values.push(value);
      value = "";
      continue;
    }

    value += character;
  }

  values.push(value);

  return values.map((item) => item.trim());
}

function detectDelimiter(headerLine) {
  const candidates = [",", ";", "\t"];

  return candidates
    .map((delimiter) => ({
      delimiter,
      count:
        parseDelimitedLine(
          headerLine,
          delimiter,
        ).length,
    }))
    .sort(
      (left, right) =>
        right.count - left.count,
    )[0].delimiter;
}

function valueFromRow(
  row,
  headerIndex,
  aliases,
) {
  for (const alias of aliases) {
    const index =
      headerIndex.get(alias);

    if (index !== undefined) {
      return row[index] ?? "";
    }
  }

  return "";
}

function parseCsv({
  text,
  fileName,
  sourceUrl,
}) {
  const normalized = stripBom(text)
    .replace(/\r\n?/g, "\n");

  const lines = normalized
    .split("\n")
    .filter((line) => line.trim());

  if (lines.length === 0) {
    throw new Error("CSV je prazdne.");
  }

  const delimiter =
    detectDelimiter(lines[0]);

  const first =
    parseDelimitedLine(
      lines[0],
      delimiter,
    );

  const normalizedFirst =
    first.map(normalizeHeader);

  const hasHeader =
    normalizedFirst.some((value) =>
      [
        "name",
        "title",
        "url",
        "stream",
        "stream_url",
        "link",
      ].includes(value),
    );

  let headers;
  let dataLines;

  if (hasHeader) {
    headers = normalizedFirst;
    dataLines = lines.slice(1);
  } else {
    const secondLooksLikeUrl =
      isStreamLocation(first[1]);

    const firstLooksLikeUrl =
      isStreamLocation(first[0]);

    if (
      !firstLooksLikeUrl &&
      !secondLooksLikeUrl
    ) {
      throw new Error(
        "CSV musi obsahovat sloupec URL nebo dvojici name,url.",
      );
    }

    headers = secondLooksLikeUrl
      ? ["name", "url"]
      : ["url", "name"];

    dataLines = lines;
  }

  const headerIndex = new Map(
    headers.map(
      (header, index) => [
        header,
        index,
      ],
    ),
  );

  const channels = [];

  dataLines.forEach((line) => {
    const row =
      parseDelimitedLine(
        line,
        delimiter,
      );

    const rawUrl =
      valueFromRow(
        row,
        headerIndex,
        [
          "url",
          "stream",
          "stream_url",
          "link",
        ],
      );

    const url =
      resolveLocation(
        rawUrl,
        sourceUrl,
      );

    if (!url) {
      return;
    }

    channels.push(
      createExternalChannel({
        name:
          valueFromRow(
            row,
            headerIndex,
            ["name", "title"],
          ) ||
          sourceName(url),
        url,
        country:
          valueFromRow(
            row,
            headerIndex,
            ["country", "country_code"],
          ),
        category:
          valueFromRow(
            row,
            headerIndex,
            [
              "category",
              "group",
              "group_title",
            ],
          ) ||
          "external",
        provider:
          valueFromRow(
            row,
            headerIndex,
            ["provider"],
          ) ||
          "External",
        status:
          valueFromRow(
            row,
            headerIndex,
            ["status"],
          ) ||
          "external",
        tvgId:
          valueFromRow(
            row,
            headerIndex,
            [
              "tvg_id",
              "epg",
              "epg_id",
            ],
          ),
        logo:
          valueFromRow(
            row,
            headerIndex,
            [
              "logo",
              "tvg_logo",
            ],
          ),
        language:
          valueFromRow(
            row,
            headerIndex,
            ["language", "lang"],
          ),
        quality:
          valueFromRow(
            row,
            headerIndex,
            ["quality"],
          ),
      }),
    );
  });

  if (channels.length === 0) {
    throw new Error(
      "V CSV nebyla nalezena zadna platna URL.",
    );
  }

  return limitResult({
    format: "csv",
    name: sourceName(
      fileName || sourceUrl,
    ),
    sourceUrl,
    warnings: [],
    channels,
  });
}

export function parsePlaylistText({
  text,
  fileName = "",
  sourceUrl = "",
}) {
  const normalized = stripBom(text);
  const source =
    fileName || sourceUrl;

  if (
    /^#EXTM3U/m.test(normalized) ||
    /^#EXTINF/m.test(normalized) ||
    /^#EXT-X-/m.test(normalized) ||
    /\.m3u8?$/i.test(source)
  ) {
    return parseM3u({
      text: normalized,
      fileName,
      sourceUrl,
    });
  }

  if (
    /\.csv$/i.test(source) ||
    /\b(name|title)\b.*\b(url|stream|link)\b/i.test(
      normalized.split(/\r?\n/, 1)[0],
    )
  ) {
    return parseCsv({
      text: normalized,
      fileName,
      sourceUrl,
    });
  }

  throw new Error(
    "Format nebyl rozpoznan. Podporujeme M3U, M3U8 a CSV.",
  );
}

export async function readPlaylistFile(file) {
  if (!file) {
    throw new Error(
      "Nebyl vybran zadny soubor.",
    );
  }

  if (file.size > MAX_IMPORT_BYTES) {
    throw new Error(
      "Soubor je prilis velky. Maximum je 5 MB.",
    );
  }

  return parsePlaylistText({
    text: await file.text(),
    fileName: file.name,
  });
}

export async function loadPlaylistUrl(
  sourceUrl,
) {
  const url = String(sourceUrl ?? "").trim();

  if (!/^https?:\/\//i.test(url)) {
    throw new Error(
      "URL musi zacinat http:// nebo https://.",
    );
  }

  try {
    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(
        `HTTP ${response.status}`,
      );
    }

    const text = await response.text();

    if (
      new Blob([text]).size >
      MAX_IMPORT_BYTES
    ) {
      throw new Error(
        "Playlist je prilis velky. Maximum je 5 MB.",
      );
    }

    return parsePlaylistText({
      text,
      fileName: sourceName(url),
      sourceUrl: url,
    });
  } catch (error) {
    if (/\.m3u8(?:$|[?#])/i.test(url)) {
      return {
        format: "m3u8",
        name: sourceName(url),
        sourceUrl: url,
        warnings: [
          "Server nedovolil nacist obsah v browseru. URL byla pridana jako primy HLS stream.",
        ],
        channels: [
          createExternalChannel({
            name: sourceName(url),
            url,
          }),
        ],
      };
    }

    throw new Error(
      `URL se nepodarilo nacist. Server muze blokovat CORS. ${String(
        error?.message || error,
      )}`,
      { cause: error },
    );
  }
}

function escapeAttribute(value) {
  return String(value ?? "")
    .replaceAll('"', "'");
}

function csvCell(value) {
  const text = String(value ?? "");

  return `"${text.replaceAll(
    '"',
    '""',
  )}"`;
}

function buildM3u(channels) {
  const lines = ["#EXTM3U"];

  channels.forEach((channel) => {
    const name =
      String(channel.name ?? "")
        .replace(/[\r\n]+/g, " ")
        .trim();

    const tvgId =
      escapeAttribute(
        channel.epg?.id,
      );

    const logo =
      escapeAttribute(
        channel.logo?.url,
      );

    const group =
      escapeAttribute(
        channel.category,
      );

    lines.push(
      `#EXTINF:-1 tvg-id="${tvgId}" tvg-name="${escapeAttribute(
        name,
      )}" tvg-logo="${logo}" group-title="${group}",${name}`,
    );

    lines.push(channel.stream.url);
  });

  return `${lines.join("\n")}\n`;
}

function buildCsv(channels) {
  const header = [
    "name",
    "url",
    "country",
    "category",
    "provider",
    "status",
    "tvg_id",
    "logo",
    "format",
    "quality",
  ];

  const rows = channels.map(
    (channel) =>
      [
        channel.name,
        channel.stream?.url,
        channel.country,
        channel.category,
        channel.provider,
        channel.status,
        channel.epg?.id,
        channel.logo?.url,
        channel.stream?.format,
        channel.stream?.quality,
      ]
        .map(csvCell)
        .join(","),
  );

  return [
    header.join(","),
    ...rows,
    "",
  ].join("\n");
}

export function createPlaylistFile({
  format,
  playlistName,
  channels,
}) {
  const normalizedFormat =
    ["m3u", "m3u8", "csv"].includes(
      format,
    )
      ? format
      : "m3u";

  const name =
    `${safeFileName(playlistName)}.${normalizedFormat}`;

  const content =
    normalizedFormat === "csv"
      ? buildCsv(channels)
      : buildM3u(channels);

  const type =
    normalizedFormat === "csv"
      ? "text/csv"
      : normalizedFormat === "m3u8"
        ? "application/vnd.apple.mpegurl"
        : "audio/x-mpegurl";

  return new File(
    ["\uFEFF", content],
    name,
    { type },
  );
}

export function downloadPlaylistFile(file) {
  const url =
    URL.createObjectURL(file);

  const link =
    document.createElement("a");

  link.href = url;
  link.download = file.name;

  document.body.appendChild(link);
  link.click();
  link.remove();

  URL.revokeObjectURL(url);
}

export function supportsSaveAs() {
  return (
    typeof window !== "undefined" &&
    typeof window.showSaveFilePicker ===
      "function"
  );
}

export async function savePlaylistFile(file) {
  if (!supportsSaveAs()) {
    downloadPlaylistFile(file);

    return {
      method: "download",
    };
  }

  const extension =
    `.${file.name.split(".").at(-1)}`;

  const mimeType =
    String(file.type || "text/plain")
      .split(";", 1)[0]
      .trim() || "text/plain";

  const handle =
    await window.showSaveFilePicker({
      suggestedName: file.name,
      types: [
        {
          description:
            "Bondik TV playlist",
          accept: {
            [mimeType]: [extension],
          },
        },
      ],
    });

  const writable =
    await handle.createWritable();

  await writable.write(file);
  await writable.close();

  return {
    method: "picker",
  };
}

export function supportsFileShare() {
  return (
    typeof navigator !== "undefined" &&
    typeof navigator.share ===
      "function" &&
    typeof navigator.canShare ===
      "function"
  );
}

export async function sharePlaylistFile(file) {
  if (
    !supportsFileShare() ||
    !navigator.canShare({
      files: [file],
    })
  ) {
    return false;
  }

  await navigator.share({
    title: "Bondik TV playlist",
    text: "Bondik TV playlist",
    files: [file],
  });

  return true;
}
