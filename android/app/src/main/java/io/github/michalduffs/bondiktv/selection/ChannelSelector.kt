package io.github.michalduffs.bondiktv.selection

import io.github.michalduffs.bondiktv.catalog.BondikChannel

data class ChannelSelection(
    val channel: BondikChannel,
    val mediaUri: String,
)

fun interface ChannelSelector {
    fun select(channel: BondikChannel): ChannelSelection
}

class DefaultChannelSelector : ChannelSelector {
    override fun select(channel: BondikChannel): ChannelSelection =
        ChannelSelection(
            channel = channel,
            mediaUri = channel.url,
        )
}
