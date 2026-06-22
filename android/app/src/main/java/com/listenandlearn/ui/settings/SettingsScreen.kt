package com.listenandlearn.ui.settings

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.listenandlearn.data.AppRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(repository: AppRepository) {
    var showServerConfig by remember { mutableStateOf(false) }
    var showMonitor by remember { mutableStateOf(false) }

    if (showServerConfig) {
        ServerConfigScreen(repository = repository, onBack = { showServerConfig = false })
        return
    }

    if (showMonitor) {
        AgentMonitorScreen(repository = repository, onBack = { showMonitor = false })
        return
    }

    val backendUrl by repository.settings.backendUrl.collectAsState(initial = "")

    LazyColumn(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        item {
            Text("设置", style = MaterialTheme.typography.headlineMedium)
            Spacer(modifier = Modifier.height(16.dp))
        }
        item {
            Card(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("后端服务地址", style = MaterialTheme.typography.titleSmall)
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(backendUrl, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        item {
            Card(
                modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp).clickable { showServerConfig = true }
            ) {
                Text("修改后端地址", modifier = Modifier.padding(16.dp))
            }
        }
        item {
            Card(
                modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp).clickable { showMonitor = true }
            ) {
                Text("Agent 监控", modifier = Modifier.padding(16.dp))
            }
        }
        item {
            Card(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("关于", style = MaterialTheme.typography.titleSmall)
                    Spacer(modifier = Modifier.height(4.dp))
                    Text("Listen and Learn v1.0.0", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text("AI 播客 + 知识库", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ServerConfigScreen(repository: AppRepository, onBack: () -> Unit) {
    val currentUrl by repository.settings.backendUrl.collectAsState(initial = "")
    var ip by remember { mutableStateOf(currentUrl.removePrefix("http://").substringBefore(":")) }
    var port by remember { mutableStateOf(currentUrl.removePrefix("http://").substringAfter(":", "8000").takeWhile { it.isDigit() }) }
    var testing by remember { mutableStateOf(false) }
    var testResult by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("修改后端地址") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "返回") } }
            )
        }
    ) { padding ->
        Column(modifier = Modifier.padding(padding).padding(16.dp)) {
            OutlinedTextField(
                value = ip, onValueChange = { ip = it },
                label = { Text("服务器 IP 地址") },
                singleLine = true, modifier = Modifier.fillMaxWidth()
            )
            Spacer(modifier = Modifier.height(16.dp))
            OutlinedTextField(
                value = port, onValueChange = { port = it.filter { c -> c.isDigit() } },
                label = { Text("端口号") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(modifier = Modifier.height(24.dp))
            Button(
                onClick = {
                    scope.launch {
                        testing = true; testResult = null
                        val url = "http://$ip:$port"
                        val success = withContext(Dispatchers.IO) { repository.testConnection(url) }
                        testing = false
                        if (success) {
                            repository.setBackendUrl(url)
                            testResult = "连接成功! 地址已保存"
                        } else {
                            testResult = "连接失败"
                        }
                    }
                },
                enabled = !testing,
                modifier = Modifier.fillMaxWidth()
            ) {
                if (testing) { CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp); Spacer(modifier = Modifier.width(8.dp)); Text("测试中...") }
                else { Text("测试并保存") }
            }
            testResult?.let {
                Spacer(modifier = Modifier.height(16.dp))
                Text(it)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AgentMonitorScreen(repository: AppRepository, onBack: () -> Unit) {
    var overview by remember { mutableStateOf<Map<String, Any>?>(null) }
    var evalSummary by remember { mutableStateOf<List<Map<String, Any>>?>(null) }
    var evaluations by remember { mutableStateOf<List<Map<String, Any>>?>(null) }
    var loading by remember { mutableStateOf(true) }
    var tabIndex by remember { mutableStateOf(0) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        scope.launch {
            loading = true
            repository.getMonitorOverview().onSuccess {
                overview = mapOf(
                    "agents" to it.agents,
                    "total_badcases" to it.total_badcases,
                    "unresolved_badcases" to it.unresolved_badcases
                )
            }
            repository.getEvaluationsSummary().onSuccess { evalSummary = it.summary }
            repository.getEvaluations().onSuccess { evaluations = it.evaluations }
            loading = false
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Agent 监控") },
                navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "返回") } }
            )
        }
    ) { padding ->
        if (loading) {
            Box(modifier = Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            return@Scaffold
        }

        Column(modifier = Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp)) {
            // Tab 切换
            TabRow(selectedTabIndex = tabIndex) {
                Tab(selected = tabIndex == 0, onClick = { tabIndex = 0 }, text = { Text("运行统计") })
                Tab(selected = tabIndex == 1, onClick = { tabIndex = 1 }, text = { Text("评测详情") })
            }
            Spacer(modifier = Modifier.height(16.dp))

            if (tabIndex == 0) {
                // 运行统计
                overview?.let { ov ->
                    val agents = ov["agents"] as? List<Map<String, Any>> ?: emptyList()
                    val totalBc = ov["total_badcases"] as? Int ?: 0
                    val unresolvedBc = ov["unresolved_badcases"] as? Int ?: 0

                    Text("Badcase 总数: $totalBc (未解决: $unresolvedBc)", style = MaterialTheme.typography.titleSmall)
                    Spacer(modifier = Modifier.height(12.dp))

                    Text("各 Agent 运行统计", style = MaterialTheme.typography.titleMedium)
                    Spacer(modifier = Modifier.height(8.dp))
                    agents.forEach { agent ->
                        Card(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                            Column(modifier = Modifier.padding(12.dp)) {
                                Text(agent["agent_name"] as? String ?: "", style = MaterialTheme.typography.titleSmall)
                                Spacer(modifier = Modifier.height(4.dp))
                                Text("调用次数: ${agent["total_calls"]}", style = MaterialTheme.typography.bodySmall)
                                Text("成功率: ${agent["success_rate"]}%", style = MaterialTheme.typography.bodySmall)
                                Text("平均耗时: ${agent["avg_duration_ms"]}ms", style = MaterialTheme.typography.bodySmall)
                                Text("平均质量分: ${agent["avg_quality_score"]}/5", style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }
                }

                // 评测汇总
                Spacer(modifier = Modifier.height(20.dp))
                Text("评测汇总（正确率/评判标准）", style = MaterialTheme.typography.titleMedium)
                Spacer(modifier = Modifier.height(8.dp))
                evalSummary?.forEach { item ->
                    Card(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                        Column(modifier = Modifier.padding(12.dp)) {
                            Text(item["agent_name"] as? String ?: "", style = MaterialTheme.typography.titleSmall)
                            Spacer(modifier = Modifier.height(4.dp))
                            Text("平均分: ${item["avg_score"]}/5", style = MaterialTheme.typography.bodySmall)
                            Text("通过率: ${item["pass_rate"]}%（评分≥4分占比）", style = MaterialTheme.typography.bodySmall)
                            Text("成功率: ${item["success_rate"]}%", style = MaterialTheme.typography.bodySmall)
                            Text("评测标准: ${item["criteria"]}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            } else {
                // 评测详情
                evaluations?.let { evals ->
                    if (evals.isEmpty()) {
                        Text("暂无评测数据", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    } else {
                        evals.forEach { ev ->
                            Card(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                                Column(modifier = Modifier.padding(12.dp)) {
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Text(ev["agent_name"] as? String ?: "", style = MaterialTheme.typography.titleSmall, modifier = Modifier.weight(1f))
                                        val score = ev["quality_score"] as? Int ?: 0
                                        val scoreColor = when {
                                            score >= 4 -> Color(0xFF4CAF50)
                                            score >= 3 -> Color(0xFFFF9800)
                                            else -> Color(0xFFF44336)
                                        }
                                        Text("$score/5", color = scoreColor, style = MaterialTheme.typography.titleSmall)
                                    }
                                    Spacer(modifier = Modifier.height(4.dp))
                                    Text("步骤: ${ev["step"] ?: ""}", style = MaterialTheme.typography.bodySmall)
                                    Text("评分理由: ${ev["quality_comment"] ?: "无"}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    Text("时间: ${ev["created_at"] ?: ""}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
