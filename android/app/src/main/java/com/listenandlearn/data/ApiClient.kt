package com.listenandlearn.data

import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object ApiClient {

    private var currentBaseUrl: String = ""
    private var retrofit: Retrofit? = null
    private var apiService: ApiService? = null

    fun getApi(baseUrl: String): ApiService {
        if (apiService != null && currentBaseUrl == baseUrl) {
            return apiService!!
        }

        val url = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"

        val logging = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BASIC
        }

        val client = OkHttpClient.Builder()
            .addInterceptor(logging)
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(120, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build()

        retrofit = Retrofit.Builder()
            .baseUrl(url)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()

        apiService = retrofit!!.create(ApiService::class.java)
        currentBaseUrl = baseUrl

        return apiService!!
    }

    fun getAudioUrl(baseUrl: String, podcastId: Int, lang: String): String {
        val url = if (baseUrl.endsWith("/")) baseUrl.dropLast(1) else baseUrl
        return "$url/api/podcast/$podcastId/audio?lang=$lang"
    }
}
