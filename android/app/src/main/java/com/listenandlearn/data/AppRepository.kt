package com.listenandlearn.data

import android.content.Context
import kotlinx.coroutines.flow.first

class AppRepository(private val context: Context) {

    val settings = SettingsDataStore(context)

    suspend fun getBackendUrl(): String {
        return settings.backendUrl.first()
    }

    suspend fun setBackendUrl(url: String) {
        settings.setBackendUrl(url)
    }

    suspend fun getLanguagePref(): String {
        return settings.languagePref.first()
    }

    suspend fun setLanguagePref(lang: String) {
        settings.setLanguagePref(lang)
    }

    suspend fun getApi(): ApiService? {
        val url = getBackendUrl()
        return if (url.isNotEmpty()) ApiClient.getApi(url) else null
    }

    suspend fun testConnection(url: String): Boolean {
        return try {
            val api = ApiClient.getApi(url)
            val response = api.healthCheck()
            response.isSuccessful && response.body()?.status == "ok"
        } catch (e: Exception) {
            false
        }
    }

    // ===== 播客 =====
    suspend fun generatePodcast(date: String? = null): Result<GenerateResponse> {
        return try {
            val api = getApi() ?: return Result.failure(Exception("未配置后端地址"))
            val response = api.generatePodcast(GenerateRequest(date))
            if (response.isSuccessful) {
                Result.success(response.body()!!)
            } else {
                Result.failure(Exception("请求失败: ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getJobs(): Result<JobsResponse> {
        return try {
            val api = getApi() ?: return Result.failure(Exception("未配置后端地址"))
            val response = api.getJobs()
            if (response.isSuccessful) Result.success(response.body()!!)
            else Result.failure(Exception("请求失败: ${response.code()}"))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun listPodcasts(): Result<List<PodcastSummary>> {
        return try {
            val api = getApi() ?: return Result.failure(Exception("未配置后端地址"))
            val response = api.listPodcasts()
            if (response.isSuccessful) Result.success(response.body()!!)
            else Result.failure(Exception("请求失败: ${response.code()}"))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getPodcast(id: Int): Result<PodcastDetail> {
        return try {
            val api = getApi() ?: return Result.failure(Exception("未配置后端地址"))
            val response = api.getPodcast(id)
            if (response.isSuccessful) Result.success(response.body()!!)
            else Result.failure(Exception("请求失败: ${response.code()}"))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun submitFeedback(podcastId: Int, type: String, content: String): Result<FeedbackResponse> {
        return try {
            val api = getApi() ?: return Result.failure(Exception("未配置后端地址"))
            val response = api.submitFeedback(podcastId, FeedbackRequest(type, content))
            if (response.isSuccessful) Result.success(response.body()!!)
            else Result.failure(Exception("请求失败: ${response.code()}"))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    // ===== 知识库 =====
    suspend fun searchKB(query: String): Result<KBSearchResponse> {
        return try {
            val api = getApi() ?: return Result.failure(Exception("未配置后端地址"))
            val response = api.searchKB(query)
            if (response.isSuccessful) Result.success(response.body()!!)
            else Result.failure(Exception("请求失败: ${response.code()}"))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getDomains(): Result<DomainsResponse> {
        return try {
            val api = getApi() ?: return Result.failure(Exception("未配置后端地址"))
            val response = api.getDomains()
            if (response.isSuccessful) Result.success(response.body()!!)
            else Result.failure(Exception("请求失败: ${response.code()}"))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun listPages(domain: String? = null): Result<PagesResponse> {
        return try {
            val api = getApi() ?: return Result.failure(Exception("未配置后端地址"))
            val response = api.listPages(domain)
            if (response.isSuccessful) Result.success(response.body()!!)
            else Result.failure(Exception("请求失败: ${response.code()}"))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getPage(path: String): Result<PageDetail> {
        return try {
            val api = getApi() ?: return Result.failure(Exception("未配置后端地址"))
            val response = api.getPage(path)
            if (response.isSuccessful) Result.success(response.body()!!)
            else Result.failure(Exception("请求失败: ${response.code()}"))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    // ===== 监控 =====
    suspend fun getMonitorOverview(): Result<MonitorOverview> {
        return try {
            val api = getApi() ?: return Result.failure(Exception("未配置后端地址"))
            val response = api.getMonitorOverview()
            if (response.isSuccessful) Result.success(response.body()!!)
            else Result.failure(Exception("请求失败: ${response.code()}"))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getLogs(agentName: String? = null): Result<LogsResponse> {
        return try {
            val api = getApi() ?: return Result.failure(Exception("未配置后端地址"))
            val response = api.getLogs(agentName)
            if (response.isSuccessful) Result.success(response.body()!!)
            else Result.failure(Exception("请求失败: ${response.code()}"))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getLog(logId: Int): Result<AgentLog> {
        return try {
            val api = getApi() ?: return Result.failure(Exception("未配置后端地址"))
            val response = api.getLog(logId)
            if (response.isSuccessful) Result.success(response.body()!!)
            else Result.failure(Exception("请求失败: ${response.code()}"))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getBadcases(): Result<BadcasesResponse> {
        return try {
            val api = getApi() ?: return Result.failure(Exception("未配置后端地址"))
            val response = api.getBadcases()
            if (response.isSuccessful) Result.success(response.body()!!)
            else Result.failure(Exception("请求失败: ${response.code()}"))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getEvaluations(): Result<EvaluationsResponse> {
        return try {
            val api = getApi() ?: return Result.failure(Exception("未配置后端地址"))
            val response = api.getEvaluations()
            if (response.isSuccessful) Result.success(response.body()!!)
            else Result.failure(Exception("请求失败: ${response.code()}"))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getEvaluationsSummary(): Result<EvaluationsSummaryResponse> {
        return try {
            val api = getApi() ?: return Result.failure(Exception("未配置后端地址"))
            val response = api.getEvaluationsSummary()
            if (response.isSuccessful) Result.success(response.body()!!)
            else Result.failure(Exception("请求失败: ${response.code()}"))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun submitKBFeedback(pagePath: String, type: String, content: String): Result<FeedbackResponse> {
        return try {
            val api = getApi() ?: return Result.failure(Exception("未配置后端地址"))
            val response = api.submitKBFeedback(KBFeedbackRequest(pagePath, type, content))
            if (response.isSuccessful) Result.success(response.body()!!)
            else Result.failure(Exception("请求失败: ${response.code()}"))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun smartSearch(query: String): Result<SmartSearchResponse> {
        return try {
            val api = getApi() ?: return Result.failure(Exception("未配置后端地址"))
            val response = api.smartSearch(SmartSearchRequest(query))
            if (response.isSuccessful) Result.success(response.body()!!)
            else Result.failure(Exception("请求失败: ${response.code()}"))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    fun getAudioUrl(podcastId: Int, lang: String): String {
        val url = currentBackendUrlSync()
        return ApiClient.getAudioUrl(url, podcastId, lang)
    }

    fun getDownloadUrl(podcastId: Int, lang: String): String {
        val url = currentBackendUrlSync()
        val base = if (url.endsWith("/")) url.dropLast(1) else url
        return "$base/api/podcast/$podcastId/download?lang=$lang"
    }

    fun getLogStreamUrl(): String {
        val url = currentBackendUrlSync()
        val base = if (url.endsWith("/")) url.dropLast(1) else url
        return "$base/api/podcast/logs/stream"
    }

    suspend fun downloadPodcastAudio(podcastId: Int, lang: String): Result<okhttp3.ResponseBody> {
        return try {
            val api = getApi() ?: return Result.failure(Exception("未配置后端地址"))
            val response = api.downloadPodcastAudio(podcastId, lang)
            if (response.isSuccessful) Result.success(response.body()!!)
            else Result.failure(Exception("下载失败: ${response.code()}"))
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    private fun currentBackendUrlSync(): String {
        // 同步获取，仅在已知已配置后使用
        return kotlinx.coroutines.runBlocking { getBackendUrl() }
    }
}
