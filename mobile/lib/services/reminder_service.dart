import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

import '../models.dart';

/// Local follow-up reminders. Scheduled as absolute instants (UTC TZDateTime), so no device time-zone lookup is needed.
/// All calls are best-effort: reminders failing must never break the app (e.g. notification permission denied).
class ReminderService {
  final FlutterLocalNotificationsPlugin _plugin = FlutterLocalNotificationsPlugin();
  bool _ready = false;

  Future<void> init() async {
    try {
      tzdata.initializeTimeZones();
      const init = InitializationSettings(
        android: AndroidInitializationSettings('@mipmap/ic_launcher'),
        iOS: DarwinInitializationSettings(requestAlertPermission: false, requestBadgePermission: false, requestSoundPermission: false),
      );
      await _plugin.initialize(init);
      _ready = true;
    } catch (_) {
      _ready = false;
    }
  }

  /// Asks for notification permission in context (called when the user taps "Remind me").
  Future<bool> requestPermission() async {
    if (!_ready) return false;
    try {
      final android = _plugin.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>();
      final a = await android?.requestNotificationsPermission();
      final ios = _plugin.resolvePlatformSpecificImplementation<IOSFlutterLocalNotificationsPlugin>();
      final i = await ios?.requestPermissions(alert: true, badge: true, sound: true);
      return (a ?? i ?? true);
    } catch (_) {
      return false;
    }
  }

  Future<bool> schedule(FollowUp f, {Duration before = const Duration(hours: 1)}) async {
    if (!_ready || f.dueDate == null) return false;
    final when = f.dueDate!.toUtc().subtract(before);
    if (when.isBefore(DateTime.now().toUtc())) return false;
    try {
      await _plugin.zonedSchedule(
        f.id,
        'Follow-up due soon',
        '${f.title} - ${fmtDateTime(f.dueDate)}',
        tz.TZDateTime.from(when, tz.UTC),
        const NotificationDetails(
          android: AndroidNotificationDetails('followups', 'Follow-up reminders', importance: Importance.high, priority: Priority.high),
          iOS: DarwinNotificationDetails(),
        ),
        androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
        uiLocalNotificationDateInterpretation: UILocalNotificationDateInterpretation.absoluteTime,
      );
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<void> cancel(int followUpId) async {
    if (_ready) {
      try {
        await _plugin.cancel(followUpId);
      } catch (_) {}
    }
  }
}
