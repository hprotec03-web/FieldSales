import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models.dart';
import '../screens/check_in_screen.dart';
import '../services/location_service.dart';
import '../state/attendance_state.dart';
import '../state/auth_state.dart';
import 'charts.dart';
import 'common.dart';

/// Gets a fresh GPS fix, then runs [action] with it. Shows a progress dialog and friendly errors.
/// Returns true when the action succeeded.
Future<bool> withLocation(BuildContext context, String busyText, Future<void> Function(LocationFix fix) action) async {
  final nav = Navigator.of(context, rootNavigator: true);
  unawaited(showDialog<void>(
    context: context,
    barrierDismissible: false,
    builder: (_) => PopScope(
      canPop: false,
      child: AlertDialog(
        content: Row(children: [
          const SizedBox(width: 24, height: 24, child: CircularProgressIndicator(strokeWidth: 2.5)),
          const SizedBox(width: 16),
          Expanded(child: Text(busyText)),
        ]),
      ),
    ),
  ));
  try {
    final fix = await LocationService.current();
    await action(fix);
    nav.pop();
    if (fix.isMocked && context.mounted) {
      showSnack(context, 'A fake-GPS app was detected. This entry is flagged for your manager.', error: true);
    }
    return true;
  } on LocationError catch (e) {
    nav.pop();
    if (context.mounted) await showLocationProblem(context, e);
    return false;
  } catch (e) {
    nav.pop();
    if (context.mounted) showSnack(context, errorText(e), error: true);
    return false;
  }
}

Future<void> showLocationProblem(BuildContext context, LocationError e) => showDialog<void>(
      context: context,
      builder: (c) => AlertDialog(
        icon: const Icon(Icons.location_off_outlined),
        title: const Text('Location needed'),
        content: Text(e.message),
        actions: [
          if (e.openSettings)
            TextButton(
                onPressed: () {
                  Navigator.pop(c);
                  LocationService.openSettings();
                },
                child: const Text('Open settings')),
          FilledButton(onPressed: () => Navigator.pop(c), child: const Text('OK')),
        ],
      ),
    );

IconData breakIcon(String type) => switch (type) {
      'Lunch' => Icons.restaurant_outlined,
      'Tea' => Icons.local_cafe_outlined,
      'Prayer' => Icons.self_improvement_outlined,
      'Personal' => Icons.person_outline,
      _ => Icons.pause_circle_outline,
    };

Future<String?> pickBreakType(BuildContext context, List<String> types) => showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      builder: (c) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Padding(
            padding: EdgeInsets.fromLTRB(24, 0, 24, 8),
            child: Text('Take a break', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
          ),
          const Padding(
            padding: EdgeInsets.fromLTRB(24, 0, 24, 8),
            child: Text('Your location is recorded when the break starts and ends.', style: TextStyle(color: kMuted)),
          ),
          for (final t in types)
            ListTile(
              leading: CircleAvatar(backgroundColor: kWarning.withAlpha(40), child: Icon(breakIcon(t), color: const Color(0xFFB45309))),
              title: Text(t == 'Other' ? 'Other break' : '$t break'),
              onTap: () => Navigator.pop(c, t),
            ),
          const SizedBox(height: 8),
        ]),
      ),
    );

Future<bool> confirmEndDay(BuildContext context, AttendanceSession s, DateTime now, {bool atLogout = false}) async {
  final ok = await showDialog<bool>(
    context: context,
    builder: (c) => AlertDialog(
      icon: const Icon(Icons.logout_rounded),
      title: Text(atLogout ? 'End your day and log out?' : 'End your day?'),
      content: Text('You started at ${fmtTime(s.checkInAt)} and have worked ${fmtDuration(s.workedAt(now))} '
          '(breaks ${fmtDuration(s.breakAt(now))}).\n\nYour current location will be recorded as the check-out location.'),
      actions: [
        TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Cancel')),
        FilledButton(
          style: FilledButton.styleFrom(backgroundColor: kCritical),
          onPressed: () => Navigator.pop(c, true),
          child: Text(atLogout ? 'End day & log out' : 'End day'),
        ),
      ],
    ),
  );
  return ok == true;
}

/// Dashboard card: today's status with a live timer, and break / end-day actions.
class AttendanceCard extends StatefulWidget {
  const AttendanceCard({super.key});
  @override
  State<AttendanceCard> createState() => _AttendanceCardState();
}

class _AttendanceCardState extends State<AttendanceCard> {
  Timer? _tick;

  @override
  void initState() {
    super.initState();
    _tick = Timer.periodic(const Duration(seconds: 30), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _tick?.cancel();
    super.dispose();
  }

  Future<void> _break(AttendanceState att) async {
    final type = await pickBreakType(context, att.breakTypes);
    if (type == null || !mounted) return;
    final ok = await withLocation(context, 'Starting your $type break…', (fix) => att.startBreak(fix, type));
    if (ok && mounted) showSnack(context, '$type break started');
  }

  Future<void> _endBreak(AttendanceState att) async {
    final ok = await withLocation(context, 'Ending your break…', (fix) => att.endBreak(fix));
    if (ok && mounted) showSnack(context, 'Welcome back! Break ended');
  }

  Future<void> _endDay(AttendanceState att, AttendanceSession s) async {
    if (!await confirmEndDay(context, s, att.now) || !mounted) return;
    await withLocation(context, 'Ending your day…', (fix) => att.checkOut(fix));
  }

  @override
  Widget build(BuildContext context) {
    final att = context.watch<AttendanceState>();
    final s = att.session;
    final now = att.now;

    if (s == null) {
      final done = att.todayClosed;
      return _shell(
        color: done != null ? kGood : kMuted,
        title: done != null ? 'Day complete' : 'Not checked in',
        trailing: done != null ? fmtDuration(done.workedAt(now)) : null,
        lines: [
          if (done != null) '${fmtTime(done.checkInAt)} – ${fmtTime(done.checkOutAt)} · breaks ${fmtDuration(done.breakAt(now))}'
          else 'Start your day to record attendance and location.',
        ],
        actions: [
          FilledButton.icon(
            style: FilledButton.styleFrom(backgroundColor: kSeries),
            onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const CheckInScreen(standalone: true))),
            icon: const Icon(Icons.login_rounded, size: 18),
            label: Text(done != null ? 'Start again' : 'Start day'),
          ),
        ],
      );
    }

    final br = s.openBreak;
    return _shell(
      color: br != null ? kWarning : kGood,
      title: br != null ? 'On ${br.breakType.toLowerCase()} break' : 'Working',
      trailing: fmtDuration(s.workedAt(now)),
      trailingLabel: 'worked',
      lines: [
        'Started ${fmtTime(s.checkInAt)} · ${s.checkIn.label}',
        if (br != null) 'Break since ${fmtTime(br.startAt)} (${fmtDuration(now.difference(br.startAt))})'
        else if (s.breaks.isNotEmpty) '${s.breaks.length} break${s.breaks.length == 1 ? '' : 's'} · ${fmtDuration(s.breakAt(now))}',
      ],
      actions: [
        if (br != null)
          FilledButton.icon(
            style: FilledButton.styleFrom(backgroundColor: kSeries),
            onPressed: () => _endBreak(att),
            icon: const Icon(Icons.play_arrow_rounded, size: 18),
            label: const Text('End break'),
          )
        else
          OutlinedButton.icon(onPressed: () => _break(att), icon: const Icon(Icons.coffee_outlined, size: 18), label: const Text('Break')),
        OutlinedButton.icon(
          style: OutlinedButton.styleFrom(foregroundColor: kCritical, side: BorderSide(color: kCritical.withAlpha(90))),
          onPressed: () => _endDay(att, s),
          icon: const Icon(Icons.stop_circle_outlined, size: 18),
          label: const Text('End day'),
        ),
      ],
    );
  }

  Widget _shell({
    required Color color,
    required String title,
    required List<String> lines,
    required List<Widget> actions,
    String? trailing,
    String? trailingLabel,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: kBorder),
        boxShadow: const [BoxShadow(color: Color(0x0A101828), blurRadius: 4, offset: Offset(0, 1))],
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Container(
            margin: const EdgeInsets.only(top: 5),
            width: 10,
            height: 10,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle, boxShadow: [BoxShadow(color: color.withAlpha(90), blurRadius: 6)]),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('ATTENDANCE', style: TextStyle(fontSize: 11, letterSpacing: 0.8, fontWeight: FontWeight.w600, color: kMuted)),
              Text(title, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: kInk)),
            ]),
          ),
          if (trailing != null)
            Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
              Text(trailing, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: kInk)),
              if (trailingLabel != null) Text(trailingLabel, style: const TextStyle(fontSize: 11, color: kMuted)),
            ]),
        ]),
        const SizedBox(height: 8),
        for (final l in lines)
          Padding(
            padding: const EdgeInsets.only(left: 20, bottom: 2),
            child: Text(l, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13, color: Color(0xFF475569))),
          ),
        const SizedBox(height: 12),
        Wrap(spacing: 8, runSpacing: 8, children: actions),
      ]),
    );
  }
}

/// Profile "Log out": a checked-in salesman is offered to end the day first (records logout time and place).
Future<void> logoutWithAttendance(BuildContext context) async {
  final auth = context.read<AuthState>();
  final att = context.read<AttendanceState>();
  final s = att.session;
  if (s != null) {
    final choice = await showDialog<String>(
      context: context,
      builder: (c) => AlertDialog(
        icon: const Icon(Icons.logout_rounded),
        title: const Text('Log out'),
        content: Text('You are still checked in (worked ${fmtDuration(s.workedAt(att.now))}).\n\n'
            'End your day now? Your logout time and location will be recorded.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(c, 'logout'), child: const Text('Log out only')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: kCritical),
            onPressed: () => Navigator.pop(c, 'end'),
            child: const Text('End day & log out'),
          ),
        ],
      ),
    );
    if (choice == null || !context.mounted) return;
    if (choice == 'end') {
      final ok = await withLocation(context, 'Ending your day…', (fix) => att.checkOut(fix, atLogout: true));
      if (!ok) return;
    }
  } else {
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(title: const Text('Log out?'), actions: [
        TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Cancel')),
        FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('Log out')),
      ]),
    );
    if (ok != true) return;
  }
  await auth.logout();
  att.clear();
}
