package com.listenandlearn.ui.podcast

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.listenandlearn.data.AppRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LogStreamScreen(repository: AppRepository, onBack: () -> Unit) {
    var logs by remember { mutableStateOf(listOf<String>()) }
    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()
    var connected by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        scope.launch {
            val url = repository.getLogStreamUrl()
            withContext(Dispatchers.IO) {
                try {
                    val client = OkHttpClient.Builder()
                        .readTimeout(java.time.Duration.ofHours(1))
                        .build()
                    val request = Request.Builder().url(url).build()
                    val response = client.newCall(request).execute()
                    connected = response.isSuccessful
                    val source = response.body?.source()
                    while (source != null && !source.exhausted()) {
                        val line = source.readUtf8Line() ?: break
                        if (line.startsWith("data: ")) {
                            val logLine = line.removePrefix("data: ")
                            logs = logs + logLine
                            if (logs.size > 500) logs = logs.takeLast(500)
                        }
                    }
                } catch (e: Exception) {
                    logs = logs + "[连接错误] ${e.message}"
                }
            }
        }
    }

    LaunchedEffect(logs.size) {
        if (logs.isNotEmpty()) {
            listState.animateScrollToItem(logs.size - 1)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("实时日志") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "返回")
                    }
                },
                actions = {
                    Text(
                        if (connected) "● 已连接" else "○ 连接中",
                        modifier = Modifier.padding(end = 16.dp),
                        color = if (connected) Color(0xFF4CAF50) else Color.Gray,
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier.padding(padding).fillMaxSize(),
            state = listState,
            contentPadding = PaddingValues(8.dp)
        ) {
            items(logs) { logLine ->
                val color = when {
                    logLine.contains("ERROR", ignoreCase = true) -> Color(0xFFF44336)
                    logLine.contains("WARN", ignoreCase = true) -> Color(0xFFFF9800)
                    logLine.contains("SUCCESS", ignoreCase = true) -> Color(0xFF4CAF50)
                    else -> Color(0xFF666666)
                }
                Text(
                    text = logLine,
                    color = color,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace,
                    modifier = Modifier.padding(vertical = 1.dp)
                )
            }
        }
    }
}
