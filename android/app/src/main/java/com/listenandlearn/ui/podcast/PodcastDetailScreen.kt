package com.listenandlearn.ui.podcast

import android.content.Intent
import android.net.Uri
import android.os.Environment
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.Feedback
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.listenandlearn.data.AppRepository
import com.listenandlearn.data.PodcastDetail
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PodcastDetailScreen(
    repository: AppRepository,
    podcastId: Int,
    onBack: () -> Unit
) {
    var detail by remember { mutableStateOf<PodcastDetail?>(null) }
    var loading by remember { mutableStateOf(true) }
    var lang by remember { mutableStateOf("zh") }
    var showFeedback by remember { mutableStateOf(false) }
    var downloading by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current

    LaunchedEffect(podcastId) {
        scope.launch {
            loading = true
            repository.getPodcast(podcastId).onSuccess { detail = it }
            loading = false
        }
    }

    if (showFeedback && detail != null) {
        FeedbackDialog(
            onDismiss = { showFeedback = false },
            onSubmit = { type, content ->
                scope.launch {
                    repository.submitFeedback(detail!!.id, type, content)
                    showFeedback = false
                }
            }
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(detail?.date ?: "播客详情") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "返回")
                    }
                },
                actions = {
                    if (detail != null) {
                        val d = detail!!
                        val hasAudio = (lang == "zh" && d.has_audio_zh) || (lang == "en" && d.has_audio_en)
                        if (hasAudio) {
                            IconButton(onClick = {
                                scope.launch {
                                    downloading = true
                                    val downloadUrl = repository.getDownloadUrl(d.id, lang)
                                    withContext(Dispatchers.IO) {
                                        try {
                                            val client = okhttp3.OkHttpClient()
                                            val request = okhttp3.Request.Builder().url(downloadUrl).build()
                                            val response = client.newCall(request).execute()
                                            if (response.isSuccessful) {
                                                val dir = File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), "ListenAndLearn")
                                                dir.mkdirs()
                                                val file = File(dir, "podcast_${d.date}_$lang.mp3")
                                                file.outputStream().use { output ->
                                                    response.body?.byteStream()?.copyTo(output)
                                                }
                                                // 通知媒体扫描器
                                                val intent = Intent(Intent.ACTION_MEDIA_SCANNER_SCAN_FILE)
                                                intent.data = Uri.fromFile(file)
                                                context.sendBroadcast(intent)
                                            }
                                        } catch (e: Exception) {
                                            // 忽略错误
                                        }
                                    }
                                    downloading = false
                                }
                            }, enabled = !downloading) {
                                if (downloading) {
                                    CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
                                } else {
                                    Icon(Icons.Default.Download, contentDescription = "下载")
                                }
                            }
                        }
                        TextButton(onClick = { showFeedback = true }) {
                            Icon(Icons.Default.Feedback, contentDescription = null)
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("反馈")
                        }
                    }
                }
            )
        }
    ) { padding ->
        if (loading) {
            Box(modifier = Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            return@Scaffold
        }

        detail?.let { d ->
            Column(modifier = Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState())) {
                // 语言切换
                TabRow(selectedTabIndex = if (lang == "zh") 0 else 1) {
                    Tab(selected = lang == "zh", onClick = { lang = "zh" }, text = { Text("中文") })
                    Tab(selected = lang == "en", onClick = { lang = "en" }, text = { Text("English") })
                }

                // 音频播放器
                if ((lang == "zh" && d.has_audio_zh) || (lang == "en" && d.has_audio_en)) {
                    val audioUrl = repository.getAudioUrl(d.id, lang)
                    PodcastPlayerView(
                        audioUrl = audioUrl,
                        duration = if (lang == "zh") d.duration_zh else d.duration_en
                    )
                } else {
                    Text("音频生成中...", modifier = Modifier.padding(16.dp))
                }

                // 文案显示
                Spacer(modifier = Modifier.height(16.dp))
                Text("播客文案", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(horizontal = 16.dp))
                Spacer(modifier = Modifier.height(8.dp))
                val rawScript = if (lang == "zh") d.script_zh else d.script_en
                val readableScript = rawScript?.let { cleanScriptForDisplay(it) }
                SelectionContainer {
                    Text(
                        text = readableScript ?: "文案生成中...",
                        modifier = Modifier.padding(16.dp),
                        style = MaterialTheme.typography.bodyMedium
                    )
                }

                // 新闻列表
                if (d.news_items.isNotEmpty()) {
                    Spacer(modifier = Modifier.height(16.dp))
                    Text("新闻素材", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(horizontal = 16.dp))
                    Spacer(modifier = Modifier.height(8.dp))
                    d.news_items.forEach { news ->
                        Card(modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp)) {
                            Column(modifier = Modifier.padding(12.dp)) {
                                Text("[${news.domain}] ${news.title_zh}", style = MaterialTheme.typography.bodyMedium)
                                Spacer(modifier = Modifier.height(4.dp))
                                Text(news.summary_zh, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
                Spacer(modifier = Modifier.height(32.dp))
            }
        }
    }
}

/**
 * 清理文案中的 SSML 标签和说话人标记，转为人类可读格式
 * 只影响客户端显示，不影响后端音频生成
 */
fun cleanScriptForDisplay(script: String): String {
    var text = script

    // 移除 SSML 标签
    text = text.replace(Regex("<speak[^>]*>"), "")
    text = text.replace("</speak>", "")
    text = text.replace(Regex("<break[^>]*/?>"), "\n")
    text = text.replace(Regex("<prosody[^>]*>"), "")
    text = text.replace("</prosody>", "")
    text = text.replace(Regex("<emphasis[^>]*>"), "")
    text = text.replace("</emphasis>", "")
    text = text.replace(Regex("<say-as[^>]*>"), "")
    text = text.replace("</say-as>", "")
    text = text.replace(Regex("<phoneme[^>]*>"), "")
    text = text.replace("</phoneme>", "")
    text = text.replace(Regex("<sub[^>]*>"), "")
    text = text.replace("</sub>", "")
    text = text.replace(Regex("<soundEvent[^>]*/?>"), "")

    // 说话人标记转为可读格式
    text = text.replace(Regex("\\[MARCUS\\]\\s*"), "\n━━ Marcus ━━\n")
    text = text.replace(Regex("\\[CHLOE\\]\\s*"), "\n━━ Chloe ━━\n")
    text = text.replace(Regex("\\*\\*MARCUS\\*\\*\\s*"), "\n━━ Marcus ━━\n")
    text = text.replace(Regex("\\*\\*CHLOE\\*\\*\\s*"), "\n━━ Chloe ━━\n")

    // 移除其他残留的 HTML/XML 标签
    text = text.replace(Regex("<[^>]+>"), "")

    // 清理多余空行
    text = text.replace(Regex("\n{3,}"), "\n\n")
    text = text.trim()

    return text
}

@Composable
fun FeedbackDialog(onDismiss: () -> Unit, onSubmit: (String, String) -> Unit) {
    var type by remember { mutableStateOf("content") }
    var content by remember { mutableStateOf("") }
    val types = listOf("content" to "内容问题", "style" to "播客风格", "duration" to "时长问题", "tag" to "标签使用", "kb_error" to "知识库错误")

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("提交反馈") },
        text = {
            Column {
                Text("反馈类型")
                Spacer(modifier = Modifier.height(8.dp))
                types.forEach { (value, label) ->
                    Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                        RadioButton(selected = type == value, onClick = { type = value })
                        Text(label)
                    }
                }
                Spacer(modifier = Modifier.height(8.dp))
                OutlinedTextField(
                    value = content, onValueChange = { content = it },
                    label = { Text("反馈内容") },
                    modifier = Modifier.fillMaxWidth()
                )
            }
        },
        confirmButton = { TextButton(onClick = { onSubmit(type, content) }) { Text("提交") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } }
    )
}
