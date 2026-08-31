package io.github.michalduffs.bondiktv.catalog

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class M3uCatalogParserTest {

    @Test
    fun parsesBondikStableChannels() {
        val playlist = """
            #EXTM3U

            #EXTINF:-1 tvg-name="POLAR" group-title="CZ" tvg-id="POLAR.cz",POLAR
            https://stream.polar.cz/polar/polarlive-1/playlist.m3u8

            #EXTINF:-1 tvg-name="JOJ 24" group-title="SK" tvg-id="JOJ.24.HD.sk",JOJ 24
            https://live.cdn.joj.sk/live/andromeda/joj_news-1080.m3u8

            #EXTINF:-1 tvg-name="?TV" group-title="CZ",?TV
            https://vysilani.zaktv.cz/broadcast/hls/utv/index.m3u8
        """.trimIndent()

        val channels = M3uCatalogParser.parse(playlist)

        assertEquals(3, channels.size)

        assertEquals(
            BondikChannel(
                name = "POLAR",
                url = "https://stream.polar.cz/polar/polarlive-1/playlist.m3u8",
                country = "CZ",
                tvgId = "POLAR.cz",
            ),
            channels[0],
        )

        assertEquals("JOJ 24", channels[1].name)
        assertEquals("SK", channels[1].country)

        assertEquals("?TV", channels[2].name)
        assertEquals("CZ", channels[2].country)
        assertNull(channels[2].tvgId)
    }
    @Test
    fun ignoresDuplicatesAndBrokenEntries() {
        val playlist = """
            #EXTM3U

            #EXTINF:-1 group-title="CZ",POLAR
            https://example.test/polar.m3u8

            #EXTINF:-1 group-title="CZ",POLAR duplicate
            https://example.test/polar.m3u8

            #EXTINF:-1 group-title="CZ",Broken channel
            this-is-not-a-stream-url
            https://example.test/orphan.m3u8

            #EXTINF:-1 group-title="SK",JOJ 24
            https://example.test/joj24.m3u8
        """.trimIndent()

        val channels = M3uCatalogParser.parse(playlist)

        assertEquals(2, channels.size)
        assertEquals("POLAR", channels[0].name)
        assertEquals("JOJ 24", channels[1].name)
    }

}
