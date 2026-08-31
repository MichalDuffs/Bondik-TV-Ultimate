package io.github.michalduffs.bondiktv

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import io.github.michalduffs.bondiktv.catalog.BondikCatalogRepository
import io.github.michalduffs.bondiktv.catalog.BondikChannel
import io.github.michalduffs.bondiktv.ui.theme.BondikTVTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class MainActivity : ComponentActivity() {
    override fun onCreate(
        savedInstanceState: Bundle?
    ) {
        super.onCreate(savedInstanceState)

        setContent {
            BondikTVTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background,
                ) {
                    BondikTvScreen()
                }
            }
        }
    }
}

@Composable
private fun BondikTvScreen() {
    val context = LocalContext.current

    var channels by remember {
        mutableStateOf<List<BondikChannel>>(emptyList())
    }

    var selectedChannel by remember {
        mutableStateOf<BondikChannel?>(null)
    }

    var statusText by remember {
        mutableStateOf("Na\u010D\u00EDt\u00E1m Bond\u00EDk katalog...")
    }

    val player = remember {
        ExoPlayer.Builder(context)
            .build()
            .apply {
                playWhenReady = false
            }
    }

    fun selectChannel(channel: BondikChannel) {
        selectedChannel = channel

        player.setMediaItem(
            MediaItem.fromUri(channel.url)
        )
        player.prepare()
        player.playWhenReady = false
    }

    LaunchedEffect(Unit) {
        try {
            val loadedChannels = withContext(Dispatchers.IO) {
                BondikCatalogRepository.load()
            }

            channels = loadedChannels

            val firstChannel = loadedChannels.firstOrNull()

            if (firstChannel == null) {
                statusText =
                    "Bond\u00EDk katalog je pr\u00E1zdn\u00FD."
            } else {
                selectChannel(firstChannel)

                statusText =
                    "${loadedChannels.size} kan\u00E1l\u016F p\u0159ipraveno."
            }
        } catch (error: Exception) {
            statusText =
                "Bond\u00EDk katalog se nepoda\u0159ilo na\u010D\u00EDst."
        }
    }

    DisposableEffect(player) {
        onDispose {
            player.release()
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.Top,
    ) {
        Text(
            text = "Bond\u00EDk TV",
            style = MaterialTheme.typography.headlineMedium,
        )

        Text(
            text = "Open \u2022 Free \u2022 No VIP \u2022 Cel\u00E1 Zem\u011Bkoule \uD83C\uDF0D",
            style = MaterialTheme.typography.bodyMedium,
        )

        Spacer(
            modifier = Modifier.height(16.dp)
        )

        AndroidView(
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(16f / 9f),
            factory = { playerContext ->
                PlayerView(playerContext).apply {
                    this.player = player
                    keepScreenOn = true
                }
            },
            update = { playerView ->
                playerView.player = player
            },
        )

        Spacer(
            modifier = Modifier.height(12.dp)
        )

        Text(
            text = selectedChannel?.let { channel ->
                "${channel.name} \u2022 ${channel.country ?: "WORLD"} \u2022 stable"
            } ?: statusText,
            style = MaterialTheme.typography.titleMedium,
        )

        Text(
            text = statusText,
            style = MaterialTheme.typography.bodyMedium,
        )

        Spacer(
            modifier = Modifier.height(12.dp)
        )

        LazyColumn(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f),
        ) {
            items(
                items = channels,
                key = { channel -> channel.url },
            ) { channel ->
                val selected =
                    channel.url == selectedChannel?.url

                Text(
                    text =
                        if (selected) {
                            "\u25B6 ${channel.name} \u2022 ${channel.country ?: "WORLD"}"
                        } else {
                            "${channel.name} \u2022 ${channel.country ?: "WORLD"}"
                        },
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable {
                            selectChannel(channel)
                        }
                        .padding(
                            vertical = 12.dp,
                            horizontal = 4.dp,
                        ),
                    style =
                        if (selected) {
                            MaterialTheme.typography.titleMedium
                        } else {
                            MaterialTheme.typography.bodyLarge
                        },
                )

                HorizontalDivider()
            }
        }
    }
}
