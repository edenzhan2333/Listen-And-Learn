package com.listenandlearn.ui.setup

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.listenandlearn.data.AppRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SetupScreen(repository: AppRepository) {
    var serverIp by remember { mutableStateOf("") }
    var serverPort by remember { mutableStateOf("8000") }
    var testing by remember { mutableStateOf(false) }
    var testResult by remember { mutableStateOf<String?>(null) }
    var testSuccess by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    Column(
        modifier = Modifier.fillMaxSize().padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text("Listen and Learn", style = MaterialTheme.typography.headlineLarge, fontSize = 28.sp)
        Spacer(modifier = Modifier.height(8.dp))
        Text("请输入后端服务地址", color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(modifier = Modifier.height(32.dp))

        OutlinedTextField(
            value = serverIp, onValueChange = { serverIp = it },
            label = { Text("服务器 IP 地址") },
            placeholder = { Text("如 49.232.226.131") },
            singleLine = true, modifier = Modifier.fillMaxWidth()
        )
        Spacer(modifier = Modifier.height(16.dp))

        OutlinedTextField(
            value = serverPort, onValueChange = { serverPort = it.filter { c -> c.isDigit() } },
            label = { Text("端口号") },
            placeholder = { Text("如 8000") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            modifier = Modifier.fillMaxWidth()
        )
        Spacer(modifier = Modifier.height(24.dp))

        Button(
            onClick = {
                scope.launch {
                    testing = true; testResult = null
                    val url = "http://$serverIp:$serverPort"
                    val success = withContext(Dispatchers.IO) { repository.testConnection(url) }
                    testing = false; testSuccess = success
                    testResult = if (success) "连接成功!" else "连接失败，请检查地址和端口"
                    if (success) repository.setBackendUrl(url)
                }
            },
            enabled = serverIp.isNotEmpty() && serverPort.isNotEmpty() && !testing,
            modifier = Modifier.fillMaxWidth()
        ) {
            if (testing) {
                CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp, color = MaterialTheme.colorScheme.onPrimary)
                Spacer(modifier = Modifier.width(8.dp)); Text("测试中...")
            } else { Text("测试连接") }
        }

        testResult?.let { result ->
            Spacer(modifier = Modifier.height(16.dp))
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(
                    containerColor = if (testSuccess) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.errorContainer
                )
            ) {
                Text(
                    result, modifier = Modifier.padding(16.dp),
                    color = if (testSuccess) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onErrorContainer
                )
            }
        }
    }
}
