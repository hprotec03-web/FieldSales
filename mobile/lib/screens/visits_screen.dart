import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/api_client.dart';
import '../models.dart';
import '../widgets/common.dart';
import 'followup_detail_screen.dart';

/// Visit history: all visible visits, or one customer's history when [customerId] is given.
class VisitsScreen extends StatefulWidget {
  const VisitsScreen({super.key, this.customerId, this.title});
  final int? customerId;
  final String? title;
  @override
  State<VisitsScreen> createState() => _VisitsScreenState();
}

class _VisitsScreenState extends State<VisitsScreen> {
  late Future<PagedList<Visit>> _future;
  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<PagedList<Visit>> _load() async {
    final j = await context.read<ApiClient>().get('/visits', query: {'customer_id': widget.customerId, 'page_size': 100}) as Map<String, dynamic>;
    return PagedList.fromJson(j, Visit.fromJson);
  }

  void _reload() => setState(() => _future = _load());

  @override
  Widget build(BuildContext context) {
    final body = FutureView<PagedList<Visit>>(
      future: _future,
      onRetry: _reload,
      builder: (context, page) {
        if (page.items.isEmpty) return const EmptyView('No visits recorded yet.');
        return RefreshIndicator(
          onRefresh: () async => _reload(),
          child: ListView.separated(
            itemCount: page.items.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (_, i) {
              final v = page.items[i];
              return ListTile(
                title: Text(v.customerName ?? 'Customer #${v.customerId}'),
                subtitle: Text('${fmtDateTime(v.visitTime)} · ${v.userName ?? ''}\n${[v.purpose, v.outcome].whereType<String>().join(' · ')}'),
                isThreeLine: true,
                trailing: v.followUpId != null ? const Icon(Icons.event_available_outlined) : null,
                onTap: () => showModalBottomSheet(context: context, showDragHandle: true, isScrollControlled: true, builder: (_) => _VisitSheet(visit: v)),
              );
            },
          ),
        );
      },
    );
    if (widget.customerId != null) return Scaffold(appBar: AppBar(title: Text('Visits · ${widget.title ?? ''}')), body: body);
    return Scaffold(appBar: AppBar(title: const Text('Visit history')), body: body);
  }
}

class _VisitSheet extends StatelessWidget {
  const _VisitSheet({required this.visit});
  final Visit visit;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(visit.customerName ?? '', style: Theme.of(context).textTheme.titleLarge),
          LabeledValue('When', fmtDateTime(visit.visitTime)), LabeledValue('Salesman', visit.userName), LabeledValue('Purpose', visit.purpose),
          LabeledValue('Outcome', visit.outcome), LabeledValue('Notes', visit.notes), LabeledValue('Branch', visit.branchName),
          LabeledValue('Location', visit.latitude == null ? 'Not captured' : '${visit.latitude}, ${visit.longitude}'),
          if (visit.followUpId != null)
            TextButton.icon(icon: const Icon(Icons.event_note), label: const Text('Open follow-up'),
                onPressed: () { Navigator.pop(context); Navigator.push(context, MaterialPageRoute(builder: (_) => FollowUpDetailScreen(id: visit.followUpId!))); }),
        ]),
      );
}
