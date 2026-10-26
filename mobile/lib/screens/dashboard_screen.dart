import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/api_client.dart';
import '../models.dart';
import '../state/auth_state.dart';
import '../widgets/common.dart';
import 'followup_detail_screen.dart';
import 'visit_form_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});
  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  late Future<Map<String, dynamic>> _future;
  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<Map<String, dynamic>> _load() async {
    final offset = DateTime.now().timeZoneOffset.inMinutes;
    return await context.read<ApiClient>().get('/dashboard', query: {'tz_offset_minutes': offset}) as Map<String, dynamic>;
  }

  void _reload() => setState(() => _future = _load());

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthState>();
    return Scaffold(
      appBar: AppBar(title: Text('Hello, ${auth.me?.fullName.split(' ').first ?? ''}')),
      floatingActionButton: auth.can('Visit.Create')
          ? FloatingActionButton.extended(
              onPressed: () async {
                final saved = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => const VisitFormScreen()));
                if (saved == true) _reload();
              },
              icon: const Icon(Icons.add_location_alt_outlined),
              label: const Text('Record visit'))
          : null,
      body: FutureView<Map<String, dynamic>>(
        future: _future,
        onRetry: _reload,
        builder: (context, d) {
          final isSales = d['kind'] == 'salesman';
          final stats = <(String, Object?, Color?)>[
            if (isSales) ...[('Assigned customers', d['assigned_customers'], null), ('Created by me', d['created_by_me_visible'], null)]
            else ...[('Customers', d['total_customers'], null), ('Active', d['active_customers'], null), ('Salesmen', d['total_salesmen'], null)],
            ('Total visits', d['total_visits'], null),
            ("Today's visits", d['todays_visits'], null),
            ('Pending follow-ups', d['pending_followups'], Colors.amber.shade800),
            ('Overdue follow-ups', d['overdue_followups'], (d['overdue_followups'] ?? 0) > 0 ? Colors.red : null),
          ];
          final upcoming = ((d['upcoming_followups'] ?? []) as List).map((e) => FollowUp.fromJson(e as Map<String, dynamic>)).toList();
          final recent = ((d['recent_visits'] ?? []) as List).map((e) => Visit.fromJson(e as Map<String, dynamic>)).toList();
          return RefreshIndicator(
            onRefresh: () async => _reload(),
            child: ListView(padding: const EdgeInsets.all(12), children: [
              GridView.count(
                crossAxisCount: 2, shrinkWrap: true, physics: const NeverScrollableScrollPhysics(), childAspectRatio: 2.2, crossAxisSpacing: 8, mainAxisSpacing: 8,
                children: [for (final s in stats) Card(child: Padding(padding: const EdgeInsets.all(12), child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [Text(s.$1, style: const TextStyle(fontSize: 12, color: Colors.grey)), Text('${s.$2 ?? 0}', style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: s.$3))])))],
              ),
              const SizedBox(height: 16),
              Text('Upcoming follow-ups', style: Theme.of(context).textTheme.titleMedium),
              if (upcoming.isEmpty) const Padding(padding: EdgeInsets.all(12), child: Text('No upcoming follow-ups.', style: TextStyle(color: Colors.grey))),
              for (final f in upcoming)
                ListTile(title: Text(f.title), subtitle: Text(fmtDateTime(f.dueDate)), trailing: const Icon(Icons.chevron_right),
                    onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => FollowUpDetailScreen(id: f.id))).then((_) => _reload())),
              const SizedBox(height: 16),
              Text('Recent visits', style: Theme.of(context).textTheme.titleMedium),
              if (recent.isEmpty) const Padding(padding: EdgeInsets.all(12), child: Text('No visits recorded yet.', style: TextStyle(color: Colors.grey))),
              for (final v in recent) ListTile(title: Text(v.customerName ?? ''), subtitle: Text('${fmtDateTime(v.visitTime)} · ${v.outcome ?? 'no outcome'}')),
              const SizedBox(height: 80),
            ]),
          );
        },
      ),
    );
  }
}
