import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';

import '../api/api_client.dart';

/// Background location tracking during working hours.
///
/// * Runs an Android foreground service (permanent notification) so positions keep coming while the phone
///   is locked or another app is open.
/// * Keeps one point every [interval]; points are queued in a small file and uploaded in batches, so nothing
///   is lost while offline.
/// * Started after check-in / break end, stopped on break start / check-out / logout. The server also refuses
///   points outside working time and answers `tracking: false`, which stops the service.
class TrackingService {
  TrackingService(this.api);
  final ApiClient api;

  static const interval = Duration(minutes: 10);
  static const _minGap = Duration(minutes: 9); // the OS may deliver fixes a little early or more often

  StreamSubscription<Position>? _sub;
  Timer? _flushTimer;
  int? _userId;
  bool _flushing = false;
  final List<Map<String, dynamic>> _queue = [];

  DateTime? lastFixAt;   // last point taken on the phone
  DateTime? lastSentAt;  // last successful upload
  String? problem;       // user-facing reason when tracking cannot run
  VoidCallback? onChange;
  VoidCallback? onServerStop; // server says: not working any more (checked out / on break)

  bool get active => _sub != null;
  int get pending => _queue.length;

  File _file(int userId) => File('${Directory.systemTemp.path}/fieldsales_track_$userId.json');

  Future<void> start(int userId) async {
    if (_sub != null && _userId == userId) return;
    await stop(flush: false);
    _userId = userId;
    await _loadQueue();
    final perm = await Geolocator.checkPermission();
    if (perm == LocationPermission.denied || perm == LocationPermission.deniedForever) {
      problem = 'Location permission is off, so your location cannot be shared.';
      onChange?.call();
      return;
    }
    final LocationSettings settings = defaultTargetPlatform == TargetPlatform.android
        ? AndroidSettings(
            accuracy: LocationAccuracy.high,
            distanceFilter: 0,
            intervalDuration: interval,
            foregroundNotificationConfig: const ForegroundNotificationConfig(
              notificationTitle: 'FieldSales · working hours',
              notificationText: 'Your location is shared every 10 minutes until you end your day.',
              enableWakeLock: true,
              setOngoing: true,
            ),
          )
        : const LocationSettings(accuracy: LocationAccuracy.high, distanceFilter: 0);
    try {
      _sub = Geolocator.getPositionStream(locationSettings: settings).listen(
        _onPosition,
        onError: (Object _) {
          problem = 'Location is unavailable. Check that GPS is on.';
          onChange?.call();
        },
      );
      problem = null;
    } catch (_) {
      _sub = null;
      problem = 'Could not start location sharing.';
    }
    _flushTimer = Timer.periodic(const Duration(minutes: 3), (_) => flush());
    onChange?.call();
    unawaited(flush()); // upload anything left from before (e.g. app restarted while offline)
  }

  Future<void> stop({bool flush = true}) async {
    await _sub?.cancel();
    _sub = null;
    _flushTimer?.cancel();
    _flushTimer = null;
    if (flush) await this.flush();
    onChange?.call();
  }

  Future<void> _onPosition(Position p) async {
    final now = DateTime.now().toUtc();
    if (lastFixAt != null && now.difference(lastFixAt!) < _minGap) return;
    lastFixAt = now;
    problem = null;
    _queue.add({
      'recorded_at': now.toIso8601String(),
      'latitude': double.parse(p.latitude.toStringAsFixed(6)),
      'longitude': double.parse(p.longitude.toStringAsFixed(6)),
      'accuracy': double.parse(p.accuracy.toStringAsFixed(1)),
      if (p.speed >= 0) 'speed': double.parse(p.speed.toStringAsFixed(2)),
      'is_mocked': p.isMocked,
      'source': 'background',
    });
    if (_queue.length > 2000) _queue.removeRange(0, _queue.length - 2000); // ~2 weeks offline at most
    await _saveQueue();
    onChange?.call();
    await flush();
  }

  /// Uploads queued points. Keeps them when offline; drops them only after the server has seen them.
  Future<void> flush() async {
    if (_flushing || _queue.isEmpty || api.token == null) return;
    _flushing = true;
    try {
      while (_queue.isNotEmpty) {
        final batch = _queue.take(200).toList();
        final res = await api.post('/attendance/pings', {'pings': batch}) as Map<String, dynamic>;
        _queue.removeRange(0, batch.length);
        await _saveQueue();
        lastSentAt = DateTime.now();
        if (res['tracking'] == false && _sub != null) {
          await stop(flush: false);
          onServerStop?.call();
          break;
        }
      }
    } on ApiException catch (e) {
      if (e.status == 401 || e.status == 403) await stop(flush: false); // signed out: keep the file for next login
    } catch (_) {
      // offline or server unreachable: try again later
    } finally {
      _flushing = false;
      onChange?.call();
    }
  }

  Future<void> _loadQueue() async {
    _queue.clear();
    final id = _userId;
    if (id == null) return;
    try {
      final f = _file(id);
      if (await f.exists()) {
        final data = jsonDecode(await f.readAsString());
        if (data is List) _queue.addAll(data.whereType<Map>().map((m) => Map<String, dynamic>.from(m)));
      }
    } catch (_) {}
  }

  Future<void> _saveQueue() async {
    final id = _userId;
    if (id == null) return;
    try {
      await _file(id).writeAsString(jsonEncode(_queue), flush: true);
    } catch (_) {}
  }
}
