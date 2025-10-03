import React from 'react'
import { StatusBar } from 'react-native'
import { NavigationContainer } from '@react-navigation/native'
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs'
import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import HomeScreen from './screens/HomeScreen'
import WatchlistScreen from './screens/WatchlistScreen'
import ProSignalsScreen from './screens/ProSignalsScreen'
import LearnListScreen from './screens/LearnListScreen'
import LearnLessonScreen from './screens/LearnLessonScreen'
import SettingsScreen from './screens/SettingsScreen'

const Tab = createBottomTabNavigator()
const LearnStack = createNativeStackNavigator()
function LearnTab() {
  return (
    <LearnStack.Navigator screenOptions={{ headerShown: false }}>
      <LearnStack.Screen name="LearnList" component={LearnListScreen} />
      <LearnStack.Screen name="Lesson" component={LearnLessonScreen} />
    </LearnStack.Navigator>
  )
}

const queryClient = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <NavigationContainer>
        <StatusBar barStyle="light-content" />
        <Tab.Navigator screenOptions={{ headerShown: false }}>
          <Tab.Screen name="Home" component={HomeScreen} />
          <Tab.Screen name="Watchlist" component={WatchlistScreen} />
          <Tab.Screen name="Signals" component={ProSignalsScreen} />
          <Tab.Screen name="Learn" component={LearnTab} />
          <Tab.Screen name="Settings" component={SettingsScreen} />
        </Tab.Navigator>
      </NavigationContainer>
    </QueryClientProvider>
  )
}
