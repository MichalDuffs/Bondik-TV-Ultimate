package io.github.michalduffs.bondiktv

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import io.github.michalduffs.bondiktv.ui.theme.BondikTVTheme

private const val POLAR_STREAM =
    "https://stream.polar.cz/polar/polarlive-1/playlist.m3u8"

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

    val player = remember {
        ExoPlayer.Builder(context)
            .build()
            .apply {
                setMediaItem(
                    MediaItem.fromUri(POLAR_STREAM)
                )
                prepare()
                playWhenReady = false
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
            text = "POLAR \u2022 CZ \u2022 stable",
            style = MaterialTheme.typography.titleMedium,
        )

        Text(
            text = "Stiskni \u25B6 a Bond\u00EDk za\u010Dne vys\u00EDlat.",
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}
