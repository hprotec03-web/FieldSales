import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../api/api_client.dart';
import '../models.dart';
import '../state/auth_state.dart';
import '../widgets/charts.dart';
import '../widgets/common.dart';
import 'followup_detail_screen.dart';
import 'visit_form_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});
  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  Map<String, dynamic>? _data;
  Object? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  /// Refresh keeps the previous data on screen (dimmed) instead of flashing a full-page spinner.
  Future<void> _load() async {
    setState(() => _loading = true);
    await _fetch();
  }

  Future<void> _fetch() async {
    try {
      final offset = DateTime.now().timeZoneOffset.inMinutes;
      final d = await context.read<ApiClient>().get('/dashboard', query: {'tz_offset_minutes': offset}) as Map<String, dynamic>;
      if (mounted) {
        setState(() {
          _data = d;
          _error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _recordVisit() async {
    final saved = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => const VisitFormScreen()));
    if (saved == true) _load();
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthState>();
    final d = _data;
    Widget body;
    if (d == null && _error != null) {
      body = ErrorView(message: errorText(_error!), onRetry: _load);
    } else if (d == null) {
      body = const Center(child: CircularProgressIndicator());
    } else {
      body = RefreshIndicator(
        onRefresh: _load,
        child: _DashboardBody(data: d, loading: _loading, onRefresh: _load, onChanged: _load),
      );
    }
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light,
      child: Scaffold(
        backgroundColor: const Color(0xFFF6F7F9),
        floatingActionButton: auth.can('Visit.Create')
            ? FloatingActionButton.extended(
                onPressed: _recordVisit,
                backgroundColor: kSeries,
                foregroundColor: Colors.white,
                icon: const Icon(Icons.add_location_alt_outlined),
                label: const Text('Record visit', style: TextStyle(fontWeight: FontWeight.w600)))
            : null,
        body: body,
      ),
    );
  }
}

int _n(dynamic v) => v is num ? v.toInt() : 0;

class _DashboardBody extends StatelessWidget {
  const _DashboardBody({required this.data, required this.loading, required this.onRefresh, required this.onChanged});
  final Map<String, dynamic> data;
  final bool loading;
  final VoidCallback onRefresh, onChanged;

  @override
  Widget build(BuildContext context) {
    final d = data;
    final me = context.watch<AuthState>().me;
    final company = d['kind'] != 'salesman';

    // visit trend (last 14 days)
    final trend = ((d['visit_trend'] ?? const []) as List).cast<Map<String, dynamic>>();
    final values = [for (final p in trend) _n(p['visits'])];
    final last7 = values.length >= 7 ? values.sublist(values.length - 7).fold<int>(0, (a, b) => a + b) : values.fold<int>(0, (a, b) => a + b);
    final prev7 = values.length >= 14 ? values.sublist(values.length - 14, values.length - 7).fold<int>(0, (a, b) => a + b) : 0;
    final points = <ChartPoint>[
      for (var i = 0; i < trend.length; i++)
        ChartPoint(
          i == trend.length - 1 ? 'Today' : DateFormat('d MMM').format(DateTime.parse(trend[i]['date'] as String)),
          DateFormat('EEE, d MMM').format(DateTime.parse(trend[i]['date'] as String)),
          values[i],
        ),
    ];

    // follow-ups
    final pending = _n(d['pending_followups']);
    final overdue = _n(d['overdue_followups']);
    final completed = _n(d['completed_followups']);
    final cancelled = _n(d['cancelled_followups']);
    final completionRate = completed + pending == 0 ? 0 : (completed * 100 / (completed + pending)).round();

    final outcomes = ((d['visit_outcomes'] ?? const []) as List).cast<Map<String, dynamic>>();
    final team = ((d['salesman_summaries'] ?? const []) as List).cast<Map<String, dynamic>>();
    final upcoming = ((d['upcoming_followups'] ?? const []) as List).map((e) => FollowUp.fromJson(e as Map<String, dynamic>)).toList();
    final recent = ((d['recent_visits'] ?? const []) as List).map((e) => Visit.fromJson(e as Map<String, dynamic>)).toList();

    final assigned = _n(d['assignment_summary']?['assigned_customers']);
    final unassigned = _n(d['assignment_summary']?['unassigned_customers']);
    final coverage = assigned + unassigned == 0 ? 0 : (assigned * 100 / (assigned + unassigned)).round();

    return AnimatedOpacity(
      duration: const Duration(milliseconds: 200),
      opacity: loading ? 0.6 : 1,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: EdgeInsets.zero,
        children: [
          _Header(
            name: (me?.fullName ?? '').split(' ').first,
            subtitle: '${me?.roleName ?? ''} · ${me?.companyName ?? ''}',
            last7: last7,
            prev7: prev7,
            totalVisits: _n(d['total_visits']),
            trend: values,
            loading: loading,
            onRefresh: onRefresh,
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
            child: Column(children: [
              Row(children: [
                Expanded(
                  child: company
                      ? _Kpi(icon: Icons.people_alt_outlined, label: 'Customers', value: _n(d['total_customers']), sub: '${_n(d['active_customers'])} active')
                      : _Kpi(icon: Icons.people_alt_outlined, label: 'My customers', value: _n(d['assigned_customers']), sub: '${_n(d['created_by_me_visible'])} created by me'),
                ),
                const SizedBox(width: 12),
                Expanded(child: _Kpi(icon: Icons.place_outlined, label: 'Visits today', value: _n(d['todays_visits']), sub: '${_n(d['total_visits'])} all time')),
              ]),
              const SizedBox(height: 12),
              Row(children: [
                Expanded(child: _Kpi(icon: Icons.event_note_outlined, label: 'Pending', value: pending, sub: '$completionRate% completed', tone: kWarning)),
                const SizedBox(width: 12),
                Expanded(
                  child: _Kpi(
                    icon: overdue > 0 ? Icons.warning_amber_rounded : Icons.verified_outlined,
                    label: 'Overdue',
                    value: overdue,
                    sub: overdue > 0 ? 'Need attention' : 'All on track',
                    tone: overdue > 0 ? kCritical : kGood,
                  ),
                ),
              ]),
              const SizedBox(height: 16),

              _Section(
                title: 'Visit activity',
                subtitle: 'Visits per day · last 14 days · tap a bar',
                child: values.fold<int>(0, (a, b) => a + b) == 0
                    ? const _Empty('No visits recorded in the last 14 days.')
                    : ColumnChart(points: points),
              ),

              _Section(
                title: 'Follow-up health',
                subtitle: 'All follow-ups by state',
                trailing: Text('${pending + completed + cancelled}', style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: kInk)),
                child: StackedBar(segments: [
                  StackedSegment('Overdue', overdue, kCritical, Icons.warning_amber_rounded),
                  StackedSegment('Upcoming', pending - overdue, kWarning, Icons.schedule),
                  StackedSegment('Completed', completed, kGood, Icons.check_rounded),
                  StackedSegment('Cancelled', cancelled, kNeutral, Icons.close_rounded),
                ]),
              ),

              if (company)
                _Section(
                  title: 'Team performance',
                  subtitle: 'Total visits per salesman',
                  child: team.isEmpty
                      ? const _Empty('No active salesmen yet.')
                      : HBarList(items: [
                          for (final s in [...team]..sort((a, b) => _n(b['total_visits']).compareTo(_n(a['total_visits']))))
                            HBarItem(
                              s['salesman_name'] as String? ?? '',
                              _n(s['total_visits']),
                              trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                                _Pill('${_n(s['todays_visits'])} today', color: kMuted),
                                if (_n(s['overdue_followups']) > 0) ...[const SizedBox(width: 4), _Pill('${_n(s['overdue_followups'])} overdue', color: kCritical)],
                              ]),
                            ),
                        ]),
                ),

              _Section(
                title: 'Visit outcomes',
                subtitle: 'Last 30 days',
                child: outcomes.isEmpty
                    ? const _Empty('No visits in the last 30 days.')
                    : HBarList(items: [for (final o in outcomes) HBarItem(o['outcome'] as String? ?? '', _n(o['visits']))]),
              ),

              if (company)
                _Section(
                  title: 'Customer coverage',
                  subtitle: 'Customers with an assigned salesman',
                  trailing: Text('$coverage%', style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: kInk)),
                  child: Column(children: [
                    Meter(value: assigned, total: assigned + unassigned),
                    const SizedBox(height: 14),
                    Row(children: [
                      Expanded(child: _MiniStat('Assigned', assigned)),
                      const SizedBox(width: 10),
                      Expanded(child: _MiniStat('Unassigned', unassigned, color: unassigned > 0 ? const Color(0xFFB45309) : null)),
                      const SizedBox(width: 10),
                      Expanded(child: _MiniStat('Salesmen', _n(d['total_salesmen']))),
                    ]),
                  ]),
                ),

              _Section(
                title: 'Upcoming follow-ups',
                subtitle: 'Next scheduled',
                padBody: false,
                child: upcoming.isEmpty
                    ? const Padding(padding: EdgeInsets.fromLTRB(16, 0, 16, 16), child: _Empty('No upcoming follow-ups.'))
                    : Column(children: [
                        for (final f in upcoming.take(6))
                          _ListRow(
                            icon: Icons.event_outlined,
                            title: f.title,
                            subtitle: [f.customerName ?? '—', if (f.salesmanName != null) f.salesmanName!].join(' · '),
                            trailing: _Pill(f.dueDate == null ? '—' : DateFormat('d MMM').format(f.dueDate!), color: const Color(0xFFB45309)),
                            onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => FollowUpDetailScreen(id: f.id))).then((_) => onChanged()),
                          ),
                      ]),
              ),

              _Section(
                title: 'Recent visits',
                subtitle: 'Latest field activity',
                padBody: false,
                child: recent.isEmpty
                    ? const Padding(padding: EdgeInsets.fromLTRB(16, 0, 16, 16), child: _Empty('No visits recorded yet.'))
                    : Column(children: [
                        for (final v in recent.take(6))
                          _ListRow(
                            icon: Icons.place_outlined,
                            title: v.customerName ?? '',
                            subtitle: [v.userName ?? '', fmtDateTime(v.visitTime)].where((s) => s.isNotEmpty).join(' · '),
                            trailing: v.outcome == null ? null : _Pill(v.outcome!, color: kMuted),
                          ),
                      ]),
              ),
              const SizedBox(height: 96),
            ]),
          ),
        ],
      ),
    );
  }
}

/* ---------------- header ---------------- */

class _Header extends StatelessWidget {
  const _Header({
    required this.name,
    required this.subtitle,
    required this.last7,
    required this.prev7,
    required this.totalVisits,
    required this.trend,
    required this.loading,
    required this.onRefresh,
  });
  final String name, subtitle;
  final int last7, prev7, totalVisits;
  final List<int> trend;
  final bool loading;
  final VoidCallback onRefresh;

  String get _greeting {
    final h = DateTime.now().hour;
    return h < 12 ? 'Good morning' : (h < 17 ? 'Good afternoon' : 'Good evening');
  }

  @override
  Widget build(BuildContext context) {
    final top = MediaQuery.of(context).padding.top;
    final pct = prev7 == 0 ? null : ((last7 - prev7) * 100 / prev7).round();
    return Container(
      padding: EdgeInsets.fromLTRB(20, top + 16, 12, 20),
      decoration: const BoxDecoration(
        gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF0B1220), Color(0xFF0D366B), Color(0xFF1C5CAB)]),
        borderRadius: BorderRadius.vertical(bottom: Radius.circular(28)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(DateFormat('EEEE, d MMMM').format(DateTime.now()),
                  style: const TextStyle(color: Color(0xFF9EC5F4), fontSize: 13, fontWeight: FontWeight.w500)),
              const SizedBox(height: 4),
              Text('$_greeting, $name',
                  maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.w700, letterSpacing: -0.3)),
              const SizedBox(height: 2),
              Text(subtitle, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Color(0xFFB6C2D4), fontSize: 13)),
            ]),
          ),
          IconButton(
            tooltip: 'Refresh',
            onPressed: loading ? null : onRefresh,
            icon: loading
                ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                : const Icon(Icons.refresh_rounded, color: Colors.white),
          ),
        ]),
        const SizedBox(height: 18),
        Container(
          margin: const EdgeInsets.only(right: 8),
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.white.withAlpha(22),
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: Colors.white.withAlpha(30)),
          ),
          child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('Visits · last 7 days', style: TextStyle(color: Color(0xFFB6C2D4), fontSize: 12)),
                const SizedBox(height: 4),
                Text('$last7', style: const TextStyle(color: Colors.white, fontSize: 40, height: 1.1, fontWeight: FontWeight.w700, letterSpacing: -1)),
                const SizedBox(height: 6),
                Row(children: [
                  if (pct != null) ...[
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                      decoration: BoxDecoration(
                        color: (pct >= 0 ? kGood : kCritical).withAlpha(60),
                        borderRadius: BorderRadius.circular(99),
                      ),
                      child: Row(mainAxisSize: MainAxisSize.min, children: [
                        Icon(pct >= 0 ? Icons.arrow_upward_rounded : Icons.arrow_downward_rounded, size: 12, color: Colors.white),
                        const SizedBox(width: 2),
                        Text('${pct.abs()}%', style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w700)),
                      ]),
                    ),
                    const SizedBox(width: 6),
                    const Text('vs prior 7 days', style: TextStyle(color: Color(0xFFB6C2D4), fontSize: 11)),
                  ] else
                    Text('$totalVisits visits all time', style: const TextStyle(color: Color(0xFFB6C2D4), fontSize: 11)),
                ]),
              ]),
            ),
            Sparkline(values: trend, width: 110, height: 44),
          ]),
        ),
      ]),
    );
  }
}

/* ---------------- building blocks ---------------- */

const _cardDecoration = BoxDecoration(
  color: Colors.white,
  borderRadius: BorderRadius.all(Radius.circular(18)),
  border: Border.fromBorderSide(BorderSide(color: kBorder)),
  boxShadow: [BoxShadow(color: Color(0x0A101828), blurRadius: 4, offset: Offset(0, 1))],
);

class _Kpi extends StatelessWidget {
  const _Kpi({required this.icon, required this.label, required this.value, required this.sub, this.tone = kSeries});
  final IconData icon;
  final String label, sub;
  final int value;
  final Color tone;
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(14),
        decoration: _cardDecoration,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(color: tone.withAlpha(30), borderRadius: BorderRadius.circular(10)),
              child: Icon(icon, size: 18, color: tone == kWarning ? const Color(0xFFB45309) : tone),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(label, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500, color: Color(0xFF475569))),
            ),
          ]),
          const SizedBox(height: 12),
          Text(NumberFormat.compact().format(value), style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w700, color: kInk, letterSpacing: -0.5)),
          const SizedBox(height: 2),
          Text(sub, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12, color: kMuted)),
        ]),
      );
}

class _Section extends StatelessWidget {
  const _Section({required this.title, required this.child, this.subtitle, this.trailing, this.padBody = true});
  final String title;
  final String? subtitle;
  final Widget? trailing;
  final Widget child;
  final bool padBody;
  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        margin: const EdgeInsets.only(bottom: 16),
        decoration: _cardDecoration,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 14),
            child: Row(children: [
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: kInk)),
                  if (subtitle != null) ...[
                    const SizedBox(height: 2),
                    Text(subtitle!, style: const TextStyle(fontSize: 12, color: kMuted)),
                  ],
                ]),
              ),
              if (trailing != null) trailing!,
            ]),
          ),
          padBody ? Padding(padding: const EdgeInsets.fromLTRB(16, 0, 16, 16), child: child) : Padding(padding: const EdgeInsets.only(bottom: 8), child: child),
        ]),
      );
}

class _ListRow extends StatelessWidget {
  const _ListRow({required this.icon, required this.title, required this.subtitle, this.trailing, this.onTap});
  final IconData icon;
  final String title, subtitle;
  final Widget? trailing;
  final VoidCallback? onTap;
  @override
  Widget build(BuildContext context) => InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          child: Row(children: [
            Container(
              width: 38,
              height: 38,
              decoration: BoxDecoration(color: kSeries.withAlpha(22), borderRadius: BorderRadius.circular(12)),
              child: Icon(icon, size: 20, color: kSeries),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(title, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600, color: kInk)),
                const SizedBox(height: 2),
                Text(subtitle, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12, color: kMuted)),
              ]),
            ),
            if (trailing != null) ...[const SizedBox(width: 8), trailing!],
            if (onTap != null) const Padding(padding: EdgeInsets.only(left: 4), child: Icon(Icons.chevron_right_rounded, color: Color(0xFFCBD5E1))),
          ]),
        ),
      );
}

class _Pill extends StatelessWidget {
  const _Pill(this.text, {required this.color});
  final String text;
  final Color color;
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(color: color.withAlpha(26), borderRadius: BorderRadius.circular(99)),
        child: Text(text, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: color)),
      );
}

class _MiniStat extends StatelessWidget {
  const _MiniStat(this.label, this.value, {this.color});
  final String label;
  final int value;
  final Color? color;
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(color: const Color(0xFFF8FAFC), borderRadius: BorderRadius.circular(12)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(label, style: const TextStyle(fontSize: 11, color: kMuted)),
          const SizedBox(height: 2),
          Text('$value', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: color ?? kInk)),
        ]),
      );
}

class _Empty extends StatelessWidget {
  const _Empty(this.message);
  final String message;
  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(vertical: 28, horizontal: 16),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: kBorder),
          color: const Color(0xFFFCFCFD),
        ),
        child: Text(message, textAlign: TextAlign.center, style: const TextStyle(color: kMuted)),
      );
}
