package io.github.michalduffs.bondiktv.catalog

import org.junit.Assert.assertEquals
import org.junit.Test

class BondikCatalogRepositoryTest {

    @Test
    fun loadsTrustedUltimatePlaylist() {
        var requestedUrl: String? = null

        val channels = BondikCatalogRepository.load { url ->
            requestedUrl = url

            """
                #EXTM3U

                #EXTINF:-1 tvg-name="POLAR" group-title="CZ" tvg-id="POLAR.cz",POLAR
                https://stream.polar.cz/polar/polarlive-1/playlist.m3u8

                #EXTINF:-1 tvg-name="JOJ 24" group-title="SK",JOJ 24
                https://live.cdn.joj.sk/live/andromeda/joj_news-1080.m3u8
            """.trimIndent()
        }

        assertEquals(
            BondikCatalogRepository.ULTIMATE_PLAYLIST_URL,
            requestedUrl,
        )

        assertEquals(2, channels.size)
        assertEquals("POLAR", channels[0].name)
        assertEquals("JOJ 24", channels[1].name)
    }
}
