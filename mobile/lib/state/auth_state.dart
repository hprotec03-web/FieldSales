import 'package:flutter/foundation.dart';

import '../api/api_client.dart';
import '../models.dart';
import '../services/token_store.dart';

class AuthState extends ChangeNotifier {
  AuthState(this.api, this._store) {
    api.onUnauthorized = _expire;
  }
  final ApiClient api;
  final TokenStore _store;
  Me? me;
  bool initializing = true;

  bool can(String permission) => me?.permissions.contains(permission) ?? false;
  bool get isScoped => me?.dataScope == 'assigned';

  Future<void> init() async {
    final t = await _store.read();
    if (t != null) {
      api.token = t;
      try {
        me = Me.fromJson(await api.get('/auth/me') as Map<String, dynamic>);
      } on ApiException catch (e) {
        if (e.status == 401 || e.status == 403) await _clear();
        // network errors keep the token so the user can retry when back online
      }
    }
    initializing = false;
    notifyListeners();
  }

  Future<void> login(String username, String password) async {
    final res = await api.post('/auth/login', {'username': username.trim(), 'password': password}, true) as Map<String, dynamic>;
    api.token = res['access_token'] as String;
    await _store.write(api.token!);
    me = Me.fromJson(res['user'] as Map<String, dynamic>);
    notifyListeners();
  }

  Future<void> logout() async {
    try {
      await api.post('/auth/logout');
    } catch (_) {}
    await _clear();
    notifyListeners();
  }

  Future<void> refreshMe() async {
    me = Me.fromJson(await api.get('/auth/me') as Map<String, dynamic>);
    notifyListeners();
  }

  Future<void> _expire() async {
    if (me == null) return;
    await _clear();
    notifyListeners();
  }

  Future<void> _clear() async {
    api.token = null;
    me = null;
    await _store.clear();
  }
}
