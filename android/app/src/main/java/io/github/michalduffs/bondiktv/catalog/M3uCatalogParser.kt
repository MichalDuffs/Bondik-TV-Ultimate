package io.github.michalduffs.bondiktv.catalog

data class BondikChannel(
    val name: String,
    val url: String,
    val country: String?,
    val tvgId: String?,
)

object M3uCatalogParser {

    private val attributeRegex =
        Regex("""([\w-]+)="([^"]*)"""")

    fun parse(text: String): List<BondikChannel> {
        val channels = mutableListOf<BondikChannel>()
        val seenUrls = mutableSetOf<String>()

        var pendingExtInf: String? = null

        for (rawLine in text.lineSequence()) {
            val line = rawLine.trim()

            when {
                line.startsWith("#EXTINF:") -> {
                    pendingExtInf = line
                }

                line.isBlank() || line.startsWith("#") -> {
                    continue
                }

                line.startsWith("https://") ||
                    line.startsWith("http://") -> {
                    val extInf = pendingExtInf ?: continue
                    pendingExtInf = null

                    if (!seenUrls.add(line)) {
                        continue
                    }

                    val attributes = attributeRegex
                        .findAll(extInf)
                        .associate {
                            it.groupValues[1] to it.groupValues[2]
                        }

                    val fallbackName =
                        extInf.substringAfterLast(',').trim()

                    val name = attributes["tvg-name"]
                        ?.trim()
                        ?.takeIf { it.isNotEmpty() }
                        ?: fallbackName

                    if (name.isEmpty()) {
                        continue
                    }

                    channels += BondikChannel(
                        name = name,
                        url = line,
                        country = attributes["group-title"]
                            ?.trim()
                            ?.takeIf { it.isNotEmpty() },
                        tvgId = attributes["tvg-id"]
                            ?.trim()
                            ?.takeIf { it.isNotEmpty() },
                    )
                }

                else -> {
                    pendingExtInf = null
                }
            }
        }

        return channels
    }
}
