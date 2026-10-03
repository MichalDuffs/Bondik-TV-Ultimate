package io.github.michalduffs.bondiktv

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
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
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import io.github.michalduffs.bondiktv.catalog.BondikCatalogRepository
import io.github.michalduffs.bondiktv.catalog.BondikChannel
import io.github.michalduffs.bondiktv.selection.DefaultChannelSelector
import io.github.michalduffs.bondiktv.session.ANDROID_SESSION_PREFERENCES
import io.github.michalduffs.bondiktv.session.AndroidSessionRepository
import io.github.michalduffs.bondiktv.session.SharedPreferencesAndroidSessionStore
import io.github.michalduffs.bondiktv.session.selectSessionChannel
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

    val channelSelector = remember {
        DefaultChannelSelector()
    }

    val channelListState =
        rememberLazyListState()

    val sessionRepository = remember {
        AndroidSessionRepository(
            SharedPreferencesAndroidSessionStore(
                context.getSharedPreferences(
                    ANDROID_SESSION_PREFERENCES,
                    android.content.Context.MODE_PRIVATE,
                )
            )
        )
    }

    fun selectChannel(
        channel: BondikChannel,
        autoplay: Boolean,
    ) {
        val selection = channelSelector.select(channel)

        selectedChannel = selection.channel

        player.setMediaItem(
            MediaItem.fromUri(selection.mediaUri)
        )
        player.prepare()
        player.playWhenReady = autoplay

        sessionRepository.save(
            selection.channel
        )
    }

    LaunchedEffect(Unit) {
        try {
            val loadedChannels = withContext(Dispatchers.IO) {
                BondikCatalogRepository.load()
            }

            channels = loadedChannels

            val session =
                sessionRepository.load(
                    loadedChannels
                )

            val restoredChannel =
                selectSessionChannel(
                    session,
                    loadedChannels,
                )

            if (restoredChannel == null) {
                statusText =
                    "Bond\u00EDk katalog je pr\u00E1zdn\u00FD."
            } else {
                selectChannel(
                    restoredChannel,
                    autoplay = false,
                )

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

    LaunchedEffect(
        channels,
        selectedChannel?.url,
    ) {
        val selectedIndex =
            channels.indexOfFirst { channel ->
                channel.url == selectedChannel?.url
            }

        if (selectedIndex >= 0) {
            channelListState.animateScrollToItem(
                selectedIndex
            )
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .safeDrawingPadding()
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
                    useController = true
                    controllerShowTimeoutMs = 0
                    isFocusable = true
                    isFocusableInTouchMode = true
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
            state = channelListState,
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

                ChannelRow(
                    channel = channel,
                    selected = selected,
                    onSelect = {
                        selectChannel(
                            channel,
                            autoplay = true,
                        )
                    },
                )

                HorizontalDivider()
            }
        }

        Text(
            text = "D-PAD: \u2191\u2193 stanice \u2022 OK vybrat \u2022 ovl\u00E1d\u00E1n\u00ED p\u0159ehr\u00E1va\u010De v obrazu",
            modifier = Modifier.padding(top = 6.dp),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        Text(
            text = "v0.1.0 \u2022 \uD83D\uDC3E Bond\u00EDk",
            modifier = Modifier.padding(top = 4.dp),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}


@Composable
private fun ChannelRow(
    channel: BondikChannel,
    selected: Boolean,
    onSelect: () -> Unit,
) {
    var focused by remember(channel.url) {
        mutableStateOf(false)
    }

    val focusRequester = remember(channel.url) {
        FocusRequester()
    }

    val shape = RoundedCornerShape(10.dp)

    LaunchedEffect(selected) {
        if (selected) {
            focusRequester.requestFocus()
        }
    }

    Text(
        text =
            if (selected) {
                "\u25B6 ${channel.name} \u2022 ${channel.country ?: "WORLD"}"
            } else {
                "${channel.name} \u2022 ${channel.country ?: "WORLD"}"
            },
        modifier = Modifier
            .fillMaxWidth()
            .focusRequester(focusRequester)
            .onFocusChanged { state ->
                focused = state.isFocused
            }
            .focusable()
            .background(
                color =
                    if (focused || selected) {
                        MaterialTheme.colorScheme.primaryContainer
                    } else {
                        MaterialTheme.colorScheme.surface
                    },
                shape = shape,
            )
            .border(
                width =
                    if (focused) 2.dp else 1.dp,
                color =
                    if (focused) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        MaterialTheme.colorScheme.outlineVariant
                    },
                shape = shape,
            )
            .clickable(onClick = onSelect)
            .padding(
                vertical = 14.dp,
                horizontal = 14.dp,
            ),
        style =
            if (focused || selected) {
                MaterialTheme.typography.titleMedium
            } else {
                MaterialTheme.typography.bodyLarge
            },
        color =
            if (focused || selected) {
                MaterialTheme.colorScheme.onPrimaryContainer
            } else {
                MaterialTheme.colorScheme.onSurface
            },
    )
}
