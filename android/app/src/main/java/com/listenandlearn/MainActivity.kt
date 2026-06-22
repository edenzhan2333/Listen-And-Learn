package com.listenandlearn

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.lifecycle.viewmodel.compose.viewModel
import com.listenandlearn.data.AppRepository
import com.listenandlearn.data.SettingsDataStore
import com.listenandlearn.ui.MainApp
import com.listenandlearn.ui.theme.ListenAndLearnTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            ListenAndLearnTheme {
                val repository = remember { AppRepository(this) }
                val backendUrl by repository.settings.backendUrl.collectAsState(initial = "")

                if (backendUrl.isEmpty()) {
                    com.listenandlearn.ui.setup.SetupScreen(repository = repository)
                } else {
                    MainApp(repository = repository)
                }
            }
        }
    }
}
