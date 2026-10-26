import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'api/api_client.dart';
import 'screens/home_screen.dart';
import 'screens/login_screen.dart';
import 'services/reminder_service.dart';
import 'services/token_store.dart';
import 'state/auth_state.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final api = ApiClient();
  final auth = AuthState(api, TokenStore());
  final reminders = ReminderService();
  await reminders.init();
  runApp(MultiProvider(
    providers: [
      Provider<ApiClient>.value(value: api),
      Provider<ReminderService>.value(value: reminders),
      ChangeNotifierProvider<AuthState>.value(value: auth),
    ],
    child: const FieldSalesApp(),
  ));
  auth.init();
}

class FieldSalesApp extends StatelessWidget {
  const FieldSalesApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'FieldSales',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF2563EB)), useMaterial3: true),
      home: const _Gate(),
    );
  }
}

class _Gate extends StatelessWidget {
  const _Gate();
  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthState>();
    if (auth.initializing) return const Scaffold(body: Center(child: CircularProgressIndicator()));
    return auth.me == null ? const LoginScreen() : const HomeScreen();
  }
}
