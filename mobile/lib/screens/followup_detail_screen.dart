import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/api_client.dart';
import '../models.dart';
import '../services/reminder_service.dart';
import '../state/auth_state.dart';
import '../widgets/common.dart';

class FollowUpDetailScreen extends StatefulWidget {
  const FollowUpDetailScreen({super.key, required this.id});
  final int id;
  @override
  State<FollowUpDetailScreen> createState() => _FollowUpDetailScreenState();
}

class _FollowUpDetailScreenState extends State<FollowUpDetailScreen> {
  late Future<FollowUp> _future;
  final _outcome = TextEditingController();
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<FollowUp> _load() async => FollowUp.fromJson(await context.read<ApiClient>().get('/followups/${widget.id}') as Map<String, dynamic>);
  void _reload() => setState(() => _future = _load());

  Future<void> _run(Future<void> Function() action, String ok) async {
    setState(() => _busy = true);
    try {
      await action();
      if (mounted) showSnack(context, ok);
      _reload();
    } catch (e) {
      if (mounted) showSnack(context, errorText(e), error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthState>();
    final api = context.read<ApiClient>();
    return Scaffold(
      appBar: AppBar(title: const Text('Follow-up')),
      body: FutureView<FollowUp>(
        future: _future,
        onRetry: _reload,
        builder: (context, f) {
          final pending = f.status == 'Pending';
          return ListView(padding: const EdgeInsets.all(16), children: [
            Row(children: [Expanded(child: Text(f.title, style: Theme.of(context).textTheme.titleLarge)), StatusChip(f.isOverdue ? 'Overdue' : f.status)]),
            const SizedBox(height: 8),
            LabeledValue('Customer', '${f.customerName ?? ''}  ${f.customerMobile ?? ''}'),
            LabeledValue('Due', fmtDateTime(f.dueDate)),
            LabeledValue('Responsible salesman', f.salesmanName ?? 'Unassigned'),
            LabeledValue('Created by', f.createdByName),
            if (f.completedAt != null) LabeledValue('Completed', fmtDateTime(f.completedAt)),
            LabeledValue('Notes', f.notes),
            if (pending) Wrap(spacing: 8, children: [
              if (auth.can('FollowUp.Complete')) FilledButton.icon(icon: const Icon(Icons.check), label: const Text('Mark completed'), onPressed: _busy ? null : () => _run(() async {
                    await api.post('/followups/${f.id}/complete', {'outcome_text': _outcome.text.trim().isEmpty ? null : _outcome.text.trim()});
                    _outcome.clear();
                    await context.read<ReminderService>().cancel(f.id);
                  }, 'Follow-up completed')),
              if (auth.can('FollowUp.Edit')) OutlinedButton.icon(icon: const Icon(Icons.cancel_outlined), label: const Text('Cancel'), onPressed: _busy ? null : () => _run(() async {
                    await api.post('/followups/${f.id}/status', {'status': 'Cancelled'});
                    await context.read<ReminderService>().cancel(f.id);
                  }, 'Follow-up cancelled')),
              OutlinedButton.icon(icon: const Icon(Icons.alarm_add_outlined), label: const Text('Remind me'), onPressed: () async {
                final r = context.read<ReminderService>();
                final ok = await r.requestPermission() && await r.schedule(f);
                if (mounted) showSnack(context, ok ? 'Reminder set for 1 hour before the due time' : 'Could not set a reminder (permission denied or due time too close).', error: !ok);
              }),
            ]),
            if (f.status == 'Cancelled' && auth.can('FollowUp.Edit'))
              OutlinedButton.icon(icon: const Icon(Icons.restore), label: const Text('Reopen'), onPressed: _busy ? null : () => _run(() async { await api.post('/followups/${f.id}/status', {'status': 'Pending'}); }, 'Follow-up reopened')),
            const Divider(height: 32),
            Text('Outcome history (${f.outcomes.length})', style: Theme.of(context).textTheme.titleMedium),
            if (f.outcomes.isEmpty) const Padding(padding: EdgeInsets.symmetric(vertical: 12), child: Text('No outcomes recorded yet.', style: TextStyle(color: Colors.grey))),
            for (final o in f.outcomes)
              Card(child: ListTile(title: Text(o.text), subtitle: Text('${fmtDateTime(o.at)} · ${o.by ?? ''}'))),
            const Padding(padding: EdgeInsets.only(top: 4), child: Text('History is append-only; entries cannot be edited or deleted.', style: TextStyle(color: Colors.grey, fontSize: 12))),
            if (pending && auth.can('FollowUp.Edit')) ...[
              const Divider(height: 32),
              Text('Add outcome', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              TextField(controller: _outcome, maxLines: 3, decoration: const InputDecoration(hintText: 'e.g. Customer requested a demonstration', border: OutlineInputBorder())),
              const SizedBox(height: 8),
              FilledButton(
                onPressed: _busy ? null : () {
                  final text = _outcome.text.trim();
                  if (text.isEmpty) { showSnack(context, 'Enter the outcome first', error: true); return; }
                  _run(() async { await api.post('/followups/${f.id}/outcomes', {'outcome_text': text}); _outcome.clear(); }, 'Outcome added');
                },
                child: const Text('Add outcome'),
              ),
            ],
          ]);
        },
      ),
    );
  }
}
