package com.listenandlearn.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "settings")

class SettingsDataStore(private val context: Context) {

    companion object {
        val BACKEND_URL = stringPreferencesKey("backend_url")
        val LANGUAGE_PREF = stringPreferencesKey("language_pref")
    }

    val backendUrl: Flow<String> = context.dataStore.data.map { it[BACKEND_URL] ?: "" }
    val languagePref: Flow<String> = context.dataStore.data.map { it[LANGUAGE_PREF] ?: "zh" }

    suspend fun setBackendUrl(url: String) {
        context.dataStore.edit { it[BACKEND_URL] = url }
    }

    suspend fun setLanguagePref(lang: String) {
        context.dataStore.edit { it[LANGUAGE_PREF] = lang }
    }
}
