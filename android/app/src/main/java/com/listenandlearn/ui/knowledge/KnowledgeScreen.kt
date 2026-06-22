package com.listenandlearn.ui.knowledge

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.listenandlearn.data.AppRepository
import com.listenandlearn.data.PageDetail
import com.listenandlearn.data.SmartSearchResponse
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun KnowledgeScreen(repository: AppRepository) {
    var searchQuery by remember { mutableStateOf("") }
    var searchMode by remember { mutableStateOf("keyword") }
    var searchResults by remember { mutableStateOf<List<Map<String, Any>>?>(null) }
    var smartResult by remember { mutableStateOf<SmartSearchResponse?>(null) }
    var searching by remember { mutableStateOf(false) }
    var selectedPage by remember { mutableStateOf<String?>(null) }
    var showSearchFeedback by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    if (selectedPage != null) {
        PageDetailScreen(repository = repository, pagePath = selectedPage!!) { selectedPage = null }
        return
    }

    Column(modifier = Modifier.fillMaxSize()) {
        TabRow(selectedTabIndex = if (searchMode == "keyword") 0 else 1) {
            Tab(selected = searchMode == "keyword", onClick = { searchMode = "keyword"; searchResults = null; smartResult = null }) { Text("关键词搜索") }
            Tab(selected = searchMode == "smart", onClick = { searchMode = "smart"; searchResults = null; smartResult = null }) { Text("智能搜索") }
        }

        SearchBar(query = searchQuery, onQueryChange = { searchQuery = it }, onSearch = {
            if (searchQuery.isNotBlank()) {
                scope.launch {
                    searching = true
                    if (searchMode == "keyword") {
                        repository.searchKB(searchQuery).onSuccess { searchResults = it.results }
                    } else {
                        repository.smartSearch(searchQuery).onSuccess { smartResult = it }
                            .onFailure { smartResult = SmartSearchResponse(searchQuery, "搜索失败: ${it.message}", emptyList(), null) }
                    }
                    searching = false
                }
            }
        }, searching = searching, isSmart = searchMode == "smart")

        when {
            searching -> Box(Modifier.fillMaxSize(), Alignment.Center) { CircularProgressIndicator() }
            searchMode == "smart" && smartResult != null -> SmartSearchResultView(result = smartResult!!, onSourceClick = { selectedPage = it }, onFeedback = { showSearchFeedback = true })
            searchMode == "keyword" && searchResults != null -> LazyColumn(Modifier.fillMaxSize()) {
                items(searchResults!!) { result ->
                    SearchResultItem(result = result) { result["path"]?.let { p -> selectedPage = p as String } }
                    HorizontalDivider()
                }
            }
            else -> DomainsList(repository = repository) { selectedPage = it }
        }
    }

    if (showSearchFeedback && smartResult != null) {
        SearchFeedbackDialog(onDismiss = { showSearchFeedback = false }, onSubmit = { type, content ->
            scope.launch { repository.submitKBFeedback("search_${smartResult?.log_id ?: 0}", type, content); showSearchFeedback = false }
        })
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SearchBar(query: String, onQueryChange: (String) -> Unit, onSearch: () -> Unit, searching: Boolean, isSmart: Boolean) {
    OutlinedTextField(
        value = query, onValueChange = onQueryChange, modifier = Modifier.fillMaxWidth().padding(16.dp),
        label = { Text(if (isSmart) "智能搜索：用自然语言提问" else "关键词搜索") },
        placeholder = { Text(if (isSmart) "如：最近AI有什么新进展？" else "输入关键词") },
        trailingIcon = {
            if (searching) { CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp) }
            else { IconButton(onClick = onSearch) { Icon(if (isSmart) Icons.Default.AutoAwesome else Icons.Default.Search, "搜索") } }
        }, singleLine = true
    )
}

@Composable
private fun SmartSearchResultView(result: SmartSearchResponse, onSourceClick: (String) -> Unit, onFeedback: () -> Unit) {
    LazyColumn(Modifier.fillMaxSize().padding(16.dp)) {
        item { Text("智能搜索结果", style = MaterialTheme.typography.titleMedium); Spacer(Modifier.height(12.dp)) }
        item { Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(16.dp)) { Text(result.answer, style = MaterialTheme.typography.bodyMedium) } } }
        if (result.sources.isNotEmpty()) {
            item { Spacer(Modifier.height(16.dp)); Text("参考来源", style = MaterialTheme.typography.titleSmall); Spacer(Modifier.height(8.dp)) }
            items(result.sources) { source ->
                val path = source["path"] as? String ?: ""
                ListItem(headlineContent = { Text(source["title"] as? String ?: "未命名", maxLines = 1, overflow = TextOverflow.Ellipsis) }, modifier = Modifier.clickable { if (path.isNotEmpty()) onSourceClick(path) })
                HorizontalDivider()
            }
        }
        item { Spacer(Modifier.height(16.dp)); OutlinedButton(onClick = onFeedback, modifier = Modifier.fillMaxWidth()) { Text("对搜索结果反馈") } }
    }
}

@Composable
private fun SearchResultItem(result: Map<String, Any>, onClick: () -> Unit) {
    Column(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(16.dp)) {
        Text(result["title"] as? String ?: "未命名", style = MaterialTheme.typography.titleSmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
        Spacer(Modifier.height(4.dp))
        Text((result["snippet"] as? String ?: result["summary"] as? String ?: ""), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2, overflow = TextOverflow.Ellipsis)
    }
}

@Composable
private fun DomainsList(repository: AppRepository, onPageClick: (String) -> Unit) {
    var domains by remember { mutableStateOf<List<String>>(emptyList()) }
    var domainKeys by remember { mutableStateOf<Map<String, String>>(emptyMap()) }
    var pages by remember { mutableStateOf<List<Map<String, Any>>?>(null) }
    var selectedDomain by remember { mutableStateOf<String?>(null) }
    var loadingPages by remember { mutableStateOf(false) }
    var errorMsg by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) { scope.launch { repository.getDomains().onSuccess { domains = it.domains; domainKeys = it.domain_keys } } }
    LaunchedEffect(selectedDomain) {
        selectedDomain?.let { domain ->
            scope.launch {
                loadingPages = true; errorMsg = null
                repository.listPages(domainKeys[domain] ?: domain).onSuccess { pages = it.pages ?: emptyList() }.onFailure { pages = emptyList(); errorMsg = it.message }
                loadingPages = false
            }
        }
    }

    if (pages != null) {
        LazyColumn(Modifier.fillMaxSize()) {
            item { TextButton(onClick = { pages = null; selectedDomain = null; errorMsg = null }) { Text("← 返回领域列表") } }
            if (loadingPages) { item { Box(Modifier.fillMaxWidth().padding(32.dp), Alignment.Center) { CircularProgressIndicator() } } }
            else if (errorMsg != null) { item { Text("加载失败: $errorMsg", Modifier.padding(16.dp), color = MaterialTheme.colorScheme.error) } }
            else if (pages!!.isEmpty()) { item { Text("该领域暂无知识库内容", Modifier.padding(16.dp)) } }
            else {
                items(pages!!) { page ->
                    val path = page["path"] as? String ?: ""
                    ListItem(headlineContent = { Text(page["title"] as? String ?: "未命名") }, supportingContent = { Text((page["summary"] as? String ?: "").take(100), maxLines = 2) }, modifier = Modifier.clickable { if (path.isNotEmpty()) onPageClick(path) })
                    HorizontalDivider()
                }
            }
        }
    } else {
        LazyColumn(Modifier.fillMaxSize().padding(16.dp)) {
            items(domains) { domain ->
                Card(onClick = { selectedDomain = domain }, modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) { Text(domain, Modifier.padding(16.dp), style = MaterialTheme.typography.titleMedium) }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PageDetailScreen(repository: AppRepository, pagePath: String, onBack: () -> Unit) {
    var page by remember { mutableStateOf<PageDetail?>(null) }
    var loading by remember { mutableStateOf(true) }
    var showFeedback by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(pagePath) { scope.launch { loading = true; repository.getPage(pagePath).onSuccess { page = it }; loading = false } }
    if (showFeedback) { KBFeedbackDialog(onDismiss = { showFeedback = false }, onSubmit = { type, content -> scope.launch { repository.submitKBFeedback(pagePath, type, content); showFeedback = false } }) }

    Scaffold(topBar = {
        TopAppBar(title = { Text(page?.title ?: "页面详情") }, navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, "返回") } }, actions = { TextButton(onClick = { showFeedback = true }) { Text("反馈") } })
    }) { padding ->
        if (loading) { Box(Modifier.fillMaxSize().padding(padding), Alignment.Center) { CircularProgressIndicator() } }
        else { page?.let { p ->
            SelectionContainer {
                Text(p.content, Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp))
            }
        } }
    }
}

@Composable
fun KBFeedbackDialog(onDismiss: () -> Unit, onSubmit: (String, String) -> Unit) {
    var type by remember { mutableStateOf("content") }
    var content by remember { mutableStateOf("") }
    val types = listOf("content" to "内容错误", "missing" to "信息缺失", "outdated" to "信息过时", "structure" to "结构问题", "other" to "其他")
    AlertDialog(onDismissRequest = onDismiss, title = { Text("知识库反馈") }, text = {
        Column {
            Text("反馈类型"); Spacer(Modifier.height(8.dp))
            types.forEach { (value, label) -> Row(verticalAlignment = Alignment.CenterVertically) { RadioButton(selected = type == value, onClick = { type = value }); Text(label) } }
            Spacer(Modifier.height(8.dp)); OutlinedTextField(value = content, onValueChange = { content = it }, label = { Text("反馈内容") }, modifier = Modifier.fillMaxWidth())
        }
    }, confirmButton = { TextButton(onClick = { if (content.isNotBlank()) onSubmit(type, content) }) { Text("提交") } }, dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } })
}

@Composable
fun SearchFeedbackDialog(onDismiss: () -> Unit, onSubmit: (String, String) -> Unit) {
    var type by remember { mutableStateOf("accuracy") }
    var content by remember { mutableStateOf("") }
    val types = listOf("accuracy" to "回答不准确", "missing" to "信息缺失", "irrelevant" to "结果不相关", "unclear" to "表达不清晰", "other" to "其他")
    AlertDialog(onDismissRequest = onDismiss, title = { Text("搜索结果反馈") }, text = {
        Column {
            Text("反馈类型"); Spacer(Modifier.height(8.dp))
            types.forEach { (value, label) -> Row(verticalAlignment = Alignment.CenterVertically) { RadioButton(selected = type == value, onClick = { type = value }); Text(label) } }
            Spacer(Modifier.height(8.dp)); OutlinedTextField(value = content, onValueChange = { content = it }, label = { Text("反馈内容") }, modifier = Modifier.fillMaxWidth())
        }
    }, confirmButton = { TextButton(onClick = { if (content.isNotBlank()) onSubmit(type, content) }) { Text("提交") } }, dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } })
}
