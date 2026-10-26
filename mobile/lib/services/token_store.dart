import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Access token lives in the platform keystore (Android Keystore / iOS Keychain), never in plain preferences.
class TokenStore {
  static const _key = 'access_token';
  final FlutterSecureStorage _s = const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
    iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock_this_device),
  );
  Future<String?> read() => _s.read(key: _key);
  Future<void> write(String t) => _s.write(key: _key, value: t);
  Future<void> clear() => _s.delete(key: _key);
}
