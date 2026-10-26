import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/api_client.dart';
import '../models.dart';
import '../widgets/common.dart';
import 'followup_detail_screen.dart';

class FollowUpsScreen extends StatefulWidget {
  const FollowUpsScreen({super.key});
  @override
  State<FollowUpsScreen> createState() => _FollowUpsScreenState();
}

class _FollowUpsScreenState extends State<FollowUpsScreen> {
  String _filter = 'Pending'; // Pending | Overdue | Completed | All
  late Future<PagedList<FollowUp>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<PagedList<FollowUp>> _load() async {
    final q = <String, dynamic>{'page_size': 100};
    switch (_filter) {
      case 'Pending': q['status'] = 'Pending';
      case 'Overdue': q['overdue'] = true;
      case 'Completed': q['status'] = 'Completed';
    }
    final j = await context.read<ApiClient>().get('/followups', query: q) as Map<String, dynamic>;
    return PagedList.fromJson(j, FollowUp.fromJson);
  }

  void _reload() => setState(() => _future = _load());

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Follow-ups')),
      body: Column(children: [
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.all(8),
          child: Row(children: [
            for (final f in const ['Pending', 'Overdue', 'Completed', 'All'])
              Padding(padding: const EdgeInsets.only(right: 8), child: ChoiceChip(label: Text(f), selected: _filter == f, onSelected: (_) { _filter = f; _reload(); })),
          ]),
        ),
        Expanded(
          child: FutureView<PagedList<FollowUp>>(
            future: _future,
            onRetry: _reload,
            builder: (context, page) {
              if (page.items.isEmpty) return EmptyView('No ${_filter == 'All' ? '' : '${_filter.toLowerCase()} '}follow-ups.');
              return RefreshIndicator(
                onRefresh: () async => _reload(),
                child: ListView.separated(
                  itemCount: page.items.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (_, i) {
                    final f = page.items[i];
                    return ListTile(
                      title: Text(f.title),
                      subtitle: Text('${f.customerName ?? ''}\nDue ${fmtDateTime(f.dueDate)}'),
                      isThreeLine: true,
                      trailing: StatusChip(f.isOverdue ? 'Overdue' : f.status),
                      onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => FollowUpDetailScreen(id: f.id))).then((_) => _reload()),
                    );
                  },
                ),
              );
            },
          ),
        ),
      ]),
    );
  }
}
