package com.listenandlearn.ui.podcast

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer

@Composable
fun PodcastPlayerView(audioUrl: String, duration: Int? = null) {
    val context = LocalContext.current
    val exoPlayer = remember {
        ExoPlayer.Builder(context).build().apply {
            setMediaItem(MediaItem.fromUri(audioUrl))
            prepare()
        }
    }

    DisposableEffect(Unit) {
        onDispose { exoPlayer.release() }
    }

    var isPlaying by remember { mutableStateOf(false) }
    var currentPosition by remember { mutableStateOf(0L) }

    LaunchedEffect(exoPlayer) {
        while (true) {
            isPlaying = exoPlayer.isPlaying
            currentPosition = exoPlayer.currentPosition
            kotlinx.coroutines.delay(500)
        }
    }

    val totalDuration = duration?.let { it * 1000L } ?: maxOf(exoPlayer.duration, 1L)

    Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
        Text("播客播放", style = MaterialTheme.typography.titleMedium)
        Spacer(modifier = Modifier.height(8.dp))

        Slider(
            value = if (totalDuration > 0) currentPosition.toFloat() / totalDuration.toFloat() else 0f,
            onValueChange = { exoPlayer.seekTo((it * totalDuration).toLong()) },
            modifier = Modifier.fillMaxWidth()
        )

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(formatTime(currentPosition), style = MaterialTheme.typography.bodySmall)
            IconButton(onClick = {
                if (isPlaying) exoPlayer.pause() else exoPlayer.play()
            }) {
                Icon(
                    if (isPlaying) Icons.Default.Pause else Icons.Default.PlayArrow,
                    contentDescription = if (isPlaying) "暂停" else "播放"
                )
            }
            Text(formatTime(totalDuration), style = MaterialTheme.typography.bodySmall)
        }
    }
}

private fun formatTime(ms: Long): String {
    val totalSeconds = ms / 1000
    val minutes = totalSeconds / 60
    val seconds = totalSeconds % 60
    return "%d:%02d".format(minutes, seconds)
}
