package io.github.michalduffs.bondiktv.session

import io.github.michalduffs.bondiktv.catalog.BondikChannel
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class AndroidSessionRepositoryTest {

    private fun channel(
        name: String,
        url: String,
    ) = BondikChannel(
        name = name,
        url = url,
        country = "CZ",
        tvgId = null,
    )

    private val first =
        channel(
            "First TV",
            "https://example.test/first.m3u8",
        )

    private val second =
        channel(
            "Second TV",
            "https://example.test/second.m3u8",
        )

    private val channels =
        listOf(first, second)

    @Test
    fun missingSessionFallsBackToFirstChannel() {
        val store = FakeStore()

        val session =
            AndroidSessionRepository(store)
                .load(channels)

        assertEquals(
            ANDROID_SESSION_VERSION,
            session.version,
        )
        assertEquals(
            first.url,
            session.selectedChannelUrl,
        )
        assertEquals(
            first,
            selectSessionChannel(
                session,
                channels,
            ),
        )
    }

    @Test
    fun validSelectionRestoresMatchingChannel() {
        val store = FakeStore(
            version =
                ANDROID_SESSION_VERSION,
            selectedChannelUrl =
                second.url,
        )

        val session =
            AndroidSessionRepository(store)
                .load(channels)

        assertEquals(
            second.url,
            session.selectedChannelUrl,
        )
        assertEquals(
            second,
            selectSessionChannel(
                session,
                channels,
            ),
        )
    }

    @Test
    fun staleSelectionFallsBackToFirstChannel() {
        val store = FakeStore(
            selectedChannelUrl =
                "https://example.test/missing.m3u8",
        )

        val session =
            AndroidSessionRepository(store)
                .load(channels)

        assertEquals(
            first.url,
            session.selectedChannelUrl,
        )
    }

    @Test
    fun unknownVersionFallsBackSafely() {
        val store = FakeStore(
            version = 99,
            selectedChannelUrl =
                second.url,
        )

        val session =
            AndroidSessionRepository(store)
                .load(channels)

        assertEquals(
            ANDROID_SESSION_VERSION,
            session.version,
        )
        assertEquals(
            first.url,
            session.selectedChannelUrl,
        )
    }

    @Test
    fun saveWritesCurrentVersionAndSelection() {
        val store = FakeStore()
        val repository =
            AndroidSessionRepository(store)

        val saved =
            repository.save(second)

        assertEquals(
            ANDROID_SESSION_VERSION,
            saved.version,
        )
        assertEquals(
            second.url,
            saved.selectedChannelUrl,
        )
        assertEquals(
            saved,
            store.writtenSession,
        )
    }

    @Test
    fun emptyCatalogKeepsSelectionEmpty() {
        val store = FakeStore()

        val session =
            AndroidSessionRepository(store)
                .load(emptyList())

        assertNull(
            session.selectedChannelUrl
        )
        assertNull(
            selectSessionChannel(
                session,
                emptyList(),
            ),
        )
    }

    private class FakeStore(
        private val version: Int =
            ANDROID_SESSION_VERSION,
        private val selectedChannelUrl:
            String? = null,
    ) : AndroidSessionKeyValueStore {

        var writtenSession:
            BondikTvAndroidSession? = null

        override fun readVersion():
            Int = version

        override fun readSelectedChannelUrl():
            String? =
            selectedChannelUrl

        override fun write(
            session: BondikTvAndroidSession,
        ) {
            writtenSession = session
        }
    }
}
