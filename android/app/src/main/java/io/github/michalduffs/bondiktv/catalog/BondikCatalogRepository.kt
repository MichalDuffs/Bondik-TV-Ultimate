package io.github.michalduffs.bondiktv.catalog

import java.net.URL

object BondikCatalogRepository {

    const val ULTIMATE_PLAYLIST_URL =
        "https://raw.githubusercontent.com/MichalDuffs/Bondik-TV-Ultimate/main/playlists/ultimate.m3u"

    fun load(
        fetchText: (String) -> String = { url ->
            URL(url).readText()
        },
    ): List<BondikChannel> {
        val playlist = fetchText(ULTIMATE_PLAYLIST_URL)
        return M3uCatalogParser.parse(playlist)
    }
}
