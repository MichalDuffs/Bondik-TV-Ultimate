package io.github.michalduffs.bondiktv.selection

import io.github.michalduffs.bondiktv.catalog.BondikChannel
import org.junit.Assert.assertEquals
import org.junit.Test

class DefaultChannelSelectorTest {

    @Test
    fun selectPreservesChannelAndMapsMediaUri() {
        val channel = BondikChannel(
            name = "Test TV",
            url = "https://example.test/live.m3u8",
            country = "CZ",
            tvgId = "test.tv",
        )

        val selection = DefaultChannelSelector().select(channel)

        assertEquals(channel, selection.channel)
        assertEquals(channel.url, selection.mediaUri)
    }

    @Test
    fun selectDoesNotRewriteChannelMetadata() {
        val channel = BondikChannel(
            name = "Radio Signal",
            url = "https://example.test/signal.m3u8",
            country = null,
            tvgId = null,
        )

        val selection = DefaultChannelSelector().select(channel)

        assertEquals("Radio Signal", selection.channel.name)
        assertEquals(null, selection.channel.country)
        assertEquals(null, selection.channel.tvgId)
    }
}
