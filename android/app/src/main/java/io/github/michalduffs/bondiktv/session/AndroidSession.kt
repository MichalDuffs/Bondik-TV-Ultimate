package io.github.michalduffs.bondiktv.session

import android.content.SharedPreferences
import io.github.michalduffs.bondiktv.catalog.BondikChannel

const val ANDROID_SESSION_VERSION = 1
const val ANDROID_SESSION_PREFERENCES =
    "bondik-tv-android-session-v1"

private const val KEY_VERSION = "version"
private const val KEY_SELECTED_CHANNEL_URL =
    "selectedChannelUrl"

data class BondikTvAndroidSession(
    val version: Int = ANDROID_SESSION_VERSION,
    val selectedChannelUrl: String? = null,
)

interface AndroidSessionKeyValueStore {
    fun readVersion(): Int
    fun readSelectedChannelUrl(): String?
    fun write(session: BondikTvAndroidSession)
}

class SharedPreferencesAndroidSessionStore(
    private val preferences: SharedPreferences,
) : AndroidSessionKeyValueStore {

    override fun readVersion(): Int =
        preferences.getInt(
            KEY_VERSION,
            ANDROID_SESSION_VERSION,
        )

    override fun readSelectedChannelUrl(): String? =
        preferences.getString(
            KEY_SELECTED_CHANNEL_URL,
            null,
        )

    override fun write(
        session: BondikTvAndroidSession,
    ) {
        preferences
            .edit()
            .putInt(
                KEY_VERSION,
                session.version,
            )
            .apply {
                val url =
                    session.selectedChannelUrl

                if (url == null) {
                    remove(
                        KEY_SELECTED_CHANNEL_URL
                    )
                } else {
                    putString(
                        KEY_SELECTED_CHANNEL_URL,
                        url,
                    )
                }
            }
            .apply()
    }
}

class AndroidSessionRepository(
    private val store: AndroidSessionKeyValueStore,
) {
    fun load(
        channels: List<BondikChannel>,
    ): BondikTvAndroidSession {
        val requestedVersion =
            store.readVersion()

        if (
            requestedVersion !=
            ANDROID_SESSION_VERSION
        ) {
            return defaultSession(channels)
        }

        val requestedUrl =
            store.readSelectedChannelUrl()

        val selectedUrl =
            requestedUrl
                ?.takeIf { url ->
                    channels.any {
                        channel ->
                        channel.url == url
                    }
                }
                ?: channels
                    .firstOrNull()
                    ?.url

        return BondikTvAndroidSession(
            version =
                ANDROID_SESSION_VERSION,
            selectedChannelUrl =
                selectedUrl,
        )
    }

    fun save(
        channel: BondikChannel?,
    ): BondikTvAndroidSession {
        val session =
            BondikTvAndroidSession(
                selectedChannelUrl =
                    channel?.url,
            )

        store.write(session)
        return session
    }
}

fun selectSessionChannel(
    session: BondikTvAndroidSession,
    channels: List<BondikChannel>,
): BondikChannel? {
    val selectedUrl =
        session.selectedChannelUrl

    return channels.firstOrNull {
        channel ->
        channel.url == selectedUrl
    } ?: channels.firstOrNull()
}

private fun defaultSession(
    channels: List<BondikChannel>,
): BondikTvAndroidSession =
    BondikTvAndroidSession(
        selectedChannelUrl =
            channels.firstOrNull()?.url,
    )
