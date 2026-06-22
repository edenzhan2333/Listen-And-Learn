package com.listenandlearn.ui

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MenuBook
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.listenandlearn.data.AppRepository
import com.listenandlearn.ui.knowledge.KnowledgeScreen
import com.listenandlearn.ui.podcast.PodcastScreen
import com.listenandlearn.ui.settings.SettingsScreen

sealed class Screen(val route: String, val title: String, val icon: androidx.compose.ui.graphics.vector.ImageVector) {
    data object Podcast : Screen("podcast", "播客", Icons.Default.Mic)
    data object Knowledge : Screen("knowledge", "知识库", Icons.Default.MenuBook)
    data object Settings : Screen("settings", "设置", Icons.Default.Settings)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainApp(repository: AppRepository) {
    val navController = rememberNavController()
    val screens = listOf(Screen.Podcast, Screen.Knowledge, Screen.Settings)
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route

    Scaffold(
        bottomBar = {
            NavigationBar {
                screens.forEach { screen ->
                    NavigationBarItem(
                        icon = { Icon(screen.icon, contentDescription = screen.title) },
                        label = { Text(screen.title) },
                        selected = currentRoute == screen.route,
                        onClick = {
                            navController.navigate(screen.route) {
                                popUpTo(navController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        }
                    )
                }
            }
        }
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = Screen.Podcast.route,
            modifier = Modifier.padding(innerPadding)
        ) {
            composable(Screen.Podcast.route) {
                PodcastScreen(repository = repository)
            }
            composable(Screen.Knowledge.route) {
                KnowledgeScreen(repository = repository)
            }
            composable(Screen.Settings.route) {
                SettingsScreen(repository = repository)
            }
        }
    }
}
