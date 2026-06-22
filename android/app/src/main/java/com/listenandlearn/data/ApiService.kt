package com.listenandlearn.data

import com.google.gson.annotations.SerializedName
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.*

// ===== API 接口定义 =====
interface ApiService {

    @GET("api/health")
    suspend fun healthCheck(): Response<HealthResponse>

    @GET("api/config")
    suspend fun getConfig(): Response<ConfigResponse>

    // ===== 播客 =====
    @POST("api/podcast/generate")
    suspend fun generatePodcast(@Body req: GenerateRequest): Response<GenerateResponse>

    @GET("api/podcast/jobs")
    suspend fun getJobs(@Query("limit") limit: Int = 10): Response<JobsResponse>

    @GET("api/podcast/jobs/{job_id}")
    suspend fun getJob(@Path("job_id") jobId: Int): Response<JobStatus>

    @GET("api/podcast/list")
    suspend fun listPodcasts(@Query("limit") limit: Int = 30): Response<List<PodcastSummary>>

    @GET("api/podcast/{id}")
    suspend fun getPodcast(@Path("id") id: Int): Response<PodcastDetail>

    @POST("api/podcast/{id}/feedback")
    suspend fun submitFeedback(
        @Path("id") id: Int,
        @Body req: FeedbackRequest
    ): Response<FeedbackResponse>

    @Streaming
    @GET("api/podcast/{id}/download")
    suspend fun downloadPodcastAudio(@Path("id") id: Int, @Query("lang") lang: String = "zh"): Response<ResponseBody>

    // ===== 知识库 =====
    @GET("api/kb/search")
    suspend fun searchKB(@Query("q") query: String, @Query("limit") limit: Int = 20): Response<KBSearchResponse>

    @GET("api/kb/domains")
    suspend fun getDomains(): Response<DomainsResponse>

    @GET("api/kb/pages")
    suspend fun listPages(
        @Query("domain") domain: String? = null,
        @Query("category") category: String? = null
    ): Response<PagesResponse>

    @GET("api/kb/pages/{path}")
    suspend fun getPage(@Path("path") path: String): Response<PageDetail>

    @POST("api/kb/smart-search")
    suspend fun smartSearch(@Body req: SmartSearchRequest): Response<SmartSearchResponse>

    // ===== 监控 =====
    @GET("api/monitor/overview")
    suspend fun getMonitorOverview(): Response<MonitorOverview>

    @GET("api/monitor/logs")
    suspend fun getLogs(
        @Query("agent_name") agentName: String? = null,
        @Query("status") status: String? = null,
        @Query("limit") limit: Int = 50
    ): Response<LogsResponse>

    @GET("api/monitor/logs/{log_id}")
    suspend fun getLog(@Path("log_id") logId: Int): Response<AgentLog>

    @GET("api/monitor/badcases")
    suspend fun getBadcases(@Query("resolved") resolved: Int? = null): Response<BadcasesResponse>

    @GET("api/monitor/evaluations")
    suspend fun getEvaluations(@Query("limit") limit: Int = 20): Response<EvaluationsResponse>

    @GET("api/monitor/evaluations/summary")
    suspend fun getEvaluationsSummary(): Response<EvaluationsSummaryResponse>

    @POST("api/kb/feedback")
    suspend fun submitKBFeedback(@Body req: KBFeedbackRequest): Response<FeedbackResponse>

    @GET("api/kb/feedback/list")
    suspend fun listKBFeedback(@Query("limit") limit: Int = 20): Response<KBFeedbackListResponse>
}

// ===== 数据模型 =====
data class HealthResponse(val status: String, val version: String)

data class ConfigResponse(
    val domains: List<String>,
    val max_podcast_days: Int,
    val male_voice: String,
    val female_voice: String
)

data class GenerateRequest(val date: String? = null)
data class GenerateResponse(val job_id: Int, val status: String, val message: String)

data class JobsResponse(val jobs: List<JobStatus>)
data class JobStatus(
    val id: Int,
    val type: String,
    val status: String,
    val progress: Int,
    val detail: String? = null,
    val error: String? = null,
    val created_at: String,
    val updated_at: String
)

data class PodcastSummary(
    val id: Int,
    val date: String,
    val status: String,
    val duration_zh: Int? = null,
    val duration_en: Int? = null,
    val has_audio_zh: Boolean = false,
    val has_audio_en: Boolean = false,
    val created_at: String
)

data class PodcastDetail(
    val id: Int,
    val date: String,
    val status: String,
    val script_zh: String? = null,
    val script_en: String? = null,
    val duration_zh: Int? = null,
    val duration_en: Int? = null,
    val has_audio_zh: Boolean = false,
    val has_audio_en: Boolean = false,
    val news_items: List<NewsItem> = emptyList(),
    val created_at: String
)

data class NewsItem(
    val id: Int,
    val podcast_date: String,
    val domain: String,
    val title_zh: String,
    val title_en: String? = null,
    val summary_zh: String,
    val source_url: String? = null,
    val image_path: String? = null
)

data class FeedbackRequest(val type: String, val content: String)
data class FeedbackResponse(val id: Int, val status: String, val message: String)

data class KBSearchResponse(val query: String, val results: List<Map<String, Any>>)
data class DomainsResponse(val domains: List<String>, val domain_keys: Map<String, String>)
data class PagesResponse(val domain: String?, val pages: List<Map<String, Any>>)
data class PageDetail(val path: String, val title: String, val content: String, val domain: String? = null, val category: String? = null)

data class MonitorOverview(val agents: List<Map<String, Any>>, val total_badcases: Int, val unresolved_badcases: Int)
data class LogsResponse(val logs: List<AgentLog>, val total: Int)
data class AgentLog(
    val id: Int,
    val agent_name: String,
    val task_id: String? = null,
    val step: String? = null,
    val input: String? = null,
    val output: String? = null,
    val tools_used: String? = null,
    val duration_ms: Int? = null,
    val status: String? = null,
    val error: String? = null,
    val quality_score: Int? = null,
    val quality_comment: String? = null,
    val created_at: String
)
data class BadcasesResponse(val badcases: List<Map<String, Any>>)

data class EvaluationsResponse(val evaluations: List<Map<String, Any>>)
data class EvaluationsSummaryResponse(val summary: List<Map<String, Any>>)

data class KBFeedbackRequest(
    val page_path: String = "",
    val type: String = "content",
    val content: String
)
data class KBFeedbackListResponse(val feedbacks: List<Map<String, Any>>)

data class SmartSearchRequest(val query: String, val page_path: String = "")
data class SmartSearchResponse(
    val query: String,
    val answer: String,
    val sources: List<Map<String, Any>>,
    val log_id: Int? = null
)
