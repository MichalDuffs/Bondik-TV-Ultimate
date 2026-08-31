package io.github.michalduffs.bondiktv.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val BondikColorScheme = darkColorScheme(
    primary = BondikAccent,
    onPrimary = Color(0xFF080808),
    secondary = BondikAccent2,
    onSecondary = Color(0xFF080808),
    tertiary = BondikStable,
    background = BondikBackground,
    onBackground = BondikText,
    surface = BondikSurface,
    onSurface = BondikText,
    surfaceVariant = BondikSurfaceVariant,
    onSurfaceVariant = BondikMuted,
    outline = BondikBorder,
)

@Composable
fun BondikTVTheme(
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = BondikColorScheme,
        typography = Typography,
        content = content,
    )
}
