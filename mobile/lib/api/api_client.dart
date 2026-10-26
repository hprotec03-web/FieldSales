import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config.dart';

class ApiException implements Exception {
  final int status;
  final String code;
  final String message;
  final Map<String, String> fieldErrors;
  ApiException(this.status, this.code, this.message, [this.fieldErrors = const {}]);
  @override
  String toString() => message;
}

/// Thin REST client. The JWT is sent as a Bearer token (mobile does not use cookies).
class ApiClient {
  ApiClient({http.Client? client}) : _http = client ?? http.Client();
  final http.Client _http;
  String? token;
  void Function()? onUnauthorized;

  Map<String, String> get _headers => {
        'Accept': 'application/json',
        if (token != null) 'Authorization': 'Bearer $token',
      };

  Uri _uri(String path, [Map<String, dynamic>? query]) {
    final q = <String, String>{};
    query?.forEach((k, v) {
      if (v != null && v.toString().isNotEmpty) q[k] = v.toString();
    });
    return Uri.parse('${AppConfig.api}$path').replace(queryParameters: q.isEmpty ? null : q);
  }

  Future<dynamic> _send(Future<http.Response> Function() call, {bool authFailureCallback = true}) async {
    http.Response res;
    try {
      res = await call().timeout(const Duration(seconds: 30));
    } on TimeoutException {
      throw ApiException(0, 'timeout', 'The server took too long to respond. Please try again.');
    } catch (_) {
      throw ApiException(0, 'network_error', 'Cannot reach the server. Check your connection and try again.');
    }
    if (res.statusCode == 401 && authFailureCallback) onUnauthorized?.call();
    if (res.statusCode >= 200 && res.statusCode < 300) {
      if (res.body.isEmpty) return null;
      return jsonDecode(utf8.decode(res.bodyBytes));
    }
    String message = 'Request failed (${res.statusCode})';
    String code = 'http_error';
    final fields = <String, String>{};
    try {
      final body = jsonDecode(utf8.decode(res.bodyBytes));
      final err = body['error'];
      if (err != null) {
        message = (err['message'] ?? message).toString();
        code = (err['code'] ?? code).toString();
        final d = err['details'];
        if (code == 'validation_error' && d is List) {
          for (final item in d) {
            fields[item['field'].toString()] = item['message'].toString();
          }
          if (fields.isNotEmpty) message = fields.entries.map((e) => '${e.key}: ${e.value}').join('\n');
        }
      }
    } catch (_) {}
    throw ApiException(res.statusCode, code, message, fields);
  }

  Future<dynamic> get(String path, {Map<String, dynamic>? query}) => _send(() => _http.get(_uri(path, query), headers: _headers));

  Future<dynamic> post(String path, [Object? body, bool isLogin = false]) => _send(
        () => _http.post(_uri(path), headers: {..._headers, 'Content-Type': 'application/json'}, body: body == null ? null : jsonEncode(body)),
        authFailureCallback: !isLogin,
      );

  Future<dynamic> put(String path, Object body) => _send(() => _http.put(_uri(path), headers: {..._headers, 'Content-Type': 'application/json'}, body: jsonEncode(body)));

  Future<dynamic> patch(String path, Object body) => _send(() => _http.patch(_uri(path), headers: {..._headers, 'Content-Type': 'application/json'}, body: jsonEncode(body)));

  Future<dynamic> upload(String path, String filePath) => _send(() async {
        final req = http.MultipartRequest('POST', _uri(path))..headers.addAll(_headers);
        req.files.add(await http.MultipartFile.fromPath('file', filePath));
        return http.Response.fromStream(await req.send());
      });

  /// Private images require the Authorization header, so they are downloaded as bytes.
  Future<List<int>> bytes(String path) async {
    final res = await _http.get(Uri.parse('${AppConfig.apiBaseUrl}$path'), headers: _headers);
    if (res.statusCode != 200) throw ApiException(res.statusCode, 'http_error', 'Image unavailable');
    return res.bodyBytes;
  }
}
