import 'dart:io';

import 'package:flutter/foundation.dart';

import '../api/api_client.dart';
import '../models.dart';
import '../services/location_service.dart';
import '../services/tracking_service.dart';

/// The signed-in user's attendance for today. Salesmen must check in before using the app.
class AttendanceState extends ChangeNotifier {
  AttendanceState(this.api) : tracking = TrackingService(api) {
    tracking.onChange = notifyListeners;
    tracking.onServerStop = () {
      final id = userId;
      if (id != null) load(id); // server says we are on a break or checked out (e.g. from another device)
    };
  }
  final ApiClient api;
  final TrackingService tracking; // background location every 10 minutes while working

  int? userId;              // whose attendance is loaded (reset when another user logs in)
  AttendanceSession? session;      // open session: working or on a break
  AttendanceSession? todayClosed;  // finished session today (shown after "End day")
  List<String> breakTypes = const ['Lunch', 'Tea', 'Prayer', 'Personal', 'Other'];
  Duration clockSkew = Duration.zero;  // server time - phone time
  bool loading = false;
  Object? error;

  DateTime get now => DateTime.now().add(clockSkew);
  int get _tz => DateTime.now().timeZoneOffset.inMinutes;

  bool loadedFor(int id) => userId == id && !loading && error == null;

  Future<void> load(int forUser) async {
    if (userId != forUser) {
      session = null;
      todayClosed = null;
    }
    userId = forUser;
    loading = true;
    error = null;
    notifyListeners();
    try {
      final res = await api.get('/attendance/current', query: {'tz_offset_minutes': _tz}) as Map<String, dynamic>;
      session = res['session'] == null ? null : AttendanceSession.fromJson(res['session'] as Map<String, dynamic>);
      todayClosed = res['today_closed'] == null ? null : AttendanceSession.fromJson(res['today_closed'] as Map<String, dynamic>);
      if (res['break_types'] is List) breakTypes = List<String>.from(res['break_types'] as List);
      final server = DateTime.tryParse(res['server_time']?.toString() ?? '');
      if (server != null) clockSkew = server.toLocal().difference(DateTime.now());
      _syncTracking();
    } catch (e) {
      error = e;
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  static String get _device {
    final s = '${Platform.operatingSystem} ${Platform.operatingSystemVersion}';
    return s.length > 200 ? s.substring(0, 200) : s;
  }

  Future<void> _apply(Future<dynamic> call) async {
    final res = await call as Map<String, dynamic>;
    final s = AttendanceSession.fromJson(res);
    if (s.isOpen) {
      session = s;
    } else {
      session = null;
      todayClosed = s;
    }
    _syncTracking();
    notifyListeners();
  }

  /// Track only while working: after check-in or a break, never during a break or after check-out.
  void _syncTracking() {
    final id = userId;
    final s = session;
    if (id != null && s != null && !s.onBreak) {
      tracking.start(id);
    } else {
      tracking.stop();
    }
  }

  Future<void> checkIn(LocationFix fix, {String? note}) =>
      _apply(api.post('/attendance/check-in', {...fix.toJson(), 'tz_offset_minutes': _tz, 'device_info': _device, if (note != null && note.trim().isNotEmpty) 'note': note.trim()}));

  Future<void> startBreak(LocationFix fix, String type) => _apply(api.post('/attendance/break/start', {...fix.toJson(), 'break_type': type}));

  Future<void> endBreak(LocationFix fix) => _apply(api.post('/attendance/break/end', fix.toJson()));

  Future<void> checkOut(LocationFix fix, {bool atLogout = false}) =>
      _apply(api.post('/attendance/check-out', {...fix.toJson(), 'method': atLogout ? 'logout' : 'manual'}));

  void clear() {
    tracking.stop();
    userId = null;
    session = null;
    todayClosed = null;
    error = null;
    notifyListeners();
  }

  @override
  void dispose() {
    tracking.onChange = null;
    tracking.onServerStop = null;
    tracking.stop(flush: false);
    super.dispose();
  }
}
