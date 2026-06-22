package com.listenandlearn.ui.podcast

import android.content.Intent
import android.net.Uri
import android.os.Environment
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.listenandlearn.data.AppRepository
import com.listenandlearn.data.PodcastSummary
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PodcastScreen(repository: AppRepository) {
    var podcasts by remember { mutableStateOf<List<PodcastSummary>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var generating by remember { mutableStateOf(false) }
    var generatingJobId by remember { mutableStateOf<Int?>(null) }
    var generatingProgress by remember { mutableStateOf(0) }
    var generatingDetail by remember { mutableStateOf("") }
    var selectedPodcast by remember { mutableStateOf<Int?>(null) }
    var showLogView by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        scope.launch {
            loading = true
            repository.listPodcasts().onSuccess { podcasts = it }
            repository.getJobs().onSuccess { jobsResp ->
                val runningJob = jobsResp.jobs.find { it.status == "running" }
                if (runningJob != null) {
                    generating = true
                    generatingJobId = runningJob.id
                    generatingProgress = runningJob.progress
                    generatingDetail = runningJob.detail ?: ""
                }
            }
            loading = false
        }
    }

    LaunchedEffect(generatingJobId) {
        val jobId = generatingJobId ?: return@LaunchedEffect
        if (jobId == 0) return@LaunchedEffect  // job_id=0 表示已存在，不需要轮询
        while (generating) {
            delay(3000)
            repository.getJobs().onSuccess { jobsResp ->
                val job = jobsResp.jobs.find { it.id == jobId }
                if (job != null) {
                    generatingProgress = job.progress
                    generatingDetail = job.detail ?: ""
                    if (job.status == "success" || job.status == "failed") {
                        generating = false
                        repository.listPodcasts().onSuccess { podcasts = it }
                    }
                } else {
                    // 找不到任务，停止轮询
                    generating = false
                    repository.listPodcasts().onSuccess { podcasts = it }
                }
            }.onFailure {
                generating = false
            }
        }
    }

    if (showLogView) {
        LogStreamScreen(repository = repository, onBack = { showLogView = false })
        return
    }

    if (selectedPodcast != null) {
        PodcastDetailScreen(
            repository = repository,
            podcastId = selectedPodcast!!,
            onBack = {
                selectedPodcast = null
                scope.launch {
                    loading = true
                    repository.listPodcasts().onSuccess { podcasts = it }
                    loading = false
                }
            }
        )
        return
    }

    Scaffold(
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = {
                    scope.launch {
                        generating = true
                        generatingProgress = 0
                        generatingDetail = "正在启动..."
                        val result = repository.generatePodcast()
                        result.onSuccess {
                            if (it.job_id == 0 || it.status == "ready") {
                                // 播客已存在，直接刷新列表
                                generating = false
                                repository.listPodcasts().onSuccess { podcasts = it }
                            } else {
                                generatingJobId = it.job_id
                            }
                        }.onFailure { generating = false }
                    }
                },
                icon = { Icon(Icons.Default.Refresh, contentDescription = "生成") },
                text = { Text("获取播客") },
                expanded = !generating
            )
        }
    ) { padding ->
        Column(modifier = Modifier.padding(padding).fillMaxSize()) {
            if (generating) {
                Card(
                    modifier = Modifier.fillMaxWidth().padding(16.dp).clickable { showLogView = true },
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("生成中... 点击查看实时日志", style = MaterialTheme.typography.titleSmall)
                        Spacer(modifier = Modifier.height(8.dp))
                        LinearProgressIndicator(
                            progress = { generatingProgress / 100f },
                            modifier = Modifier.fillMaxWidth()
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            "进度: $generatingProgress% - $generatingDetail",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onPrimaryContainer
                        )
                    }
                }
            }

            if (loading) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator()
                }
            } else if (podcasts.isEmpty()) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("暂无播客，点击右下角按钮生成今日播客")
                }
            } else {
                LazyColumn(modifier = Modifier.fillMaxSize()) {
                    items(podcasts) { podcast ->
                        PodcastListItem(podcast = podcast, onClick = { selectedPodcast = podcast.id })
                        HorizontalDivider()
                    }
                }
            }
        }
    }
}

@Composable
private fun PodcastListItem(podcast: PodcastSummary, onClick: () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick).padding(16.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(podcast.date, style = MaterialTheme.typography.titleMedium)
            Spacer(modifier = Modifier.height(4.dp))
            Row {
                if (podcast.has_audio_zh) {
                    AssistChip(onClick = {}, label = { Text("中文 ${podcast.duration_zh?.let { "${it/60}分" } ?: ""}") })
                    Spacer(modifier = Modifier.width(8.dp))
                }
                if (podcast.has_audio_en) {
                    AssistChip(onClick = {}, label = { Text("英文 ${podcast.duration_en?.let { "${it/60}分" } ?: ""}") })
                }
            }
        }
        if (podcast.status == "generating") {
            CircularProgressIndicator(modifier = Modifier.size(24.dp), strokeWidth = 2.dp)
        } else if (podcast.status == "ready" && (podcast.has_audio_zh || podcast.has_audio_en)) {
            Icon(Icons.Default.PlayArrow, contentDescription = "播放")
        }
    }
}
