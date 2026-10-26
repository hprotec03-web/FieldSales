import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../api/api_client.dart';
import '../models.dart';
import '../widgets/attendance_widgets.dart';
import '../widgets/charts.dart';
import '../widgets/common.dart';

/// "My attendance": the last 30 working days with times, places, breaks and hours worked.
class AttendanceHistoryScreen extends StatefulWidget {
  const AttendanceHistoryScreen({super.key});
  @override
  State<AttendanceHistoryScreen> createState() => _AttendanceHistoryScreenState();
}

class _AttendanceHistoryScreenState extends State<AttendanceHistoryScreen> {
  late Future<List<AttendanceSession>> _future = _load();

  Future<List<AttendanceSession>> _load() async {
    final res = await context.read<ApiClient>().get('/attendance', query: {'page_size': 30}) as Map<String, dynamic>;
    return ((res['items'] ?? const []) as List).map((e) => AttendanceSession.fromJson(e as Map<String, dynamic>)).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('My attendance')),
      body: FutureView<List<AttendanceSession>>(
        future: _future,
        onRetry: () => setState(() => _future = _load()),
        builder: (context, items) {
          if (items.isEmpty) return const EmptyView('No attendance recorded yet.');
          final total = items.fold<int>(0, (a, s) => a + s.workedMinutes);
          return RefreshIndicator(
            onRefresh: () async => setState(() => _future = _load()),
            child: ListView(padding: const EdgeInsets.all(16), children: [
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(color: kSeries.withAlpha(18), borderRadius: BorderRadius.circular(18)),
                child: Row(children: [
                  Expanded(child: _stat('Days', '${items.length}')),
                  Expanded(child: _stat('Total worked', fmtDuration(Duration(minutes: total)))),
                  Expanded(child: _stat('Average / day', fmtDuration(Duration(minutes: total ~/ items.length)))),
                ]),
              ),
              const SizedBox(height: 12),
              for (final s in items) _DayTile(s: s),
            ]),
          );
        },
      ),
    );
  }

  Widget _stat(String label, String value) => Column(children: [
        Text(value, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: kInk)),
        Text(label, style: const TextStyle(fontSize: 11, color: kMuted)),
      ]);
}

class _DayTile extends StatelessWidget {
  const _DayTile({required this.s});
  final AttendanceSession s;
  @override
  Widget build(BuildContext context) {
    final open = s.isOpen;
    final now = DateTime.now();
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(16), border: Border.all(color: kBorder)),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          shape: const RoundedRectangleBorder(),
          title: Text(DateFormat('EEE, d MMM y').format(s.workDate), style: const TextStyle(fontWeight: FontWeight.w700, color: kInk)),
          subtitle: Text('${fmtTime(s.checkInAt)} – ${open ? 'now' : fmtTime(s.checkOutAt)}'
              '${s.checkOutMethod == 'auto' ? ' (auto)' : ''} · breaks ${fmtDuration(s.breakAt(now))}'),
          trailing: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.end, children: [
            Text(fmtDuration(s.workedAt(now)), style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16, color: kInk)),
            if (s.anyMocked) const Text('Fake GPS', style: TextStyle(fontSize: 11, color: kCritical, fontWeight: FontWeight.w600)),
          ]),
          childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
          children: [
            _event(Icons.login_rounded, kGood, 'Check-in', s.checkInAt, s.checkIn.label),
            for (final b in s.breaks) ...[
              _event(breakIcon(b.breakType), const Color(0xFFB45309), '${b.breakType} break', b.startAt, b.start.label),
              if (b.endAt != null) _event(Icons.play_arrow_rounded, kSeries, 'Back to work (${b.minutes}m)', b.endAt!, b.end?.label ?? '—'),
            ],
            if (s.checkOutAt != null)
              _event(Icons.logout_rounded, kCritical, s.checkOutMethod == 'logout' ? 'Check-out (logout)' : (s.checkOutMethod == 'auto' ? 'Closed automatically' : 'Check-out'),
                  s.checkOutAt!, s.checkOut?.label ?? '—'),
          ],
        ),
      ),
    );
  }

  Widget _event(IconData icon, Color color, String title, DateTime at, String place) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(children: [
          Icon(icon, size: 18, color: color),
          const SizedBox(width: 10),
          SizedBox(width: 70, child: Text(fmtTime(at), style: const TextStyle(fontWeight: FontWeight.w600, color: kInk))),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title, style: const TextStyle(fontSize: 13, color: kInk)),
              Text(place, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12, color: kMuted)),
            ]),
          ),
        ]),
      );
}
