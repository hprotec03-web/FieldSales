/// Backend base URL. Override at build/run time:
///   flutter run --dart-define=API_BASE_URL=https://api.example.com
/// Defaults to the Android emulator's alias for the host machine (use http://localhost:8000 for the iOS simulator).
class AppConfig {
  static const String apiBaseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://10.0.2.2:8000');
  static String get api => '$apiBaseUrl/api/v1';
}
