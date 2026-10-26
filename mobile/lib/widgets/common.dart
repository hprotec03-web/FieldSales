import 'package:flutter/material.dart';

import '../api/api_client.dart';

String errorText(Object e) => e is ApiException ? e.message : 'Something went wrong. Please try again.';

void showSnack(BuildContext context, String text, {bool error = false}) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(text), backgroundColor: error ? Colors.red.shade700 : null));
}

class ErrorView extends StatelessWidget {
  const ErrorView({super.key, required this.message, this.onRetry});
  final String message;
  final VoidCallback? onRetry;
  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Icon(Icons.error_outline, size: 40, color: Colors.red),
            const SizedBox(height: 8),
            Text(message, textAlign: TextAlign.center),
            if (onRetry != null) TextButton.icon(onPressed: onRetry, icon: const Icon(Icons.refresh), label: const Text('Retry')),
          ]),
        ),
      );
}

class EmptyView extends StatelessWidget {
  const EmptyView(this.message, {super.key});
  final String message;
  @override
  Widget build(BuildContext context) => Center(child: Padding(padding: const EdgeInsets.all(24), child: Text(message, textAlign: TextAlign.center, style: const TextStyle(color: Colors.grey))));
}

/// FutureBuilder with consistent loading / error / retry handling.
class FutureView<T> extends StatelessWidget {
  const FutureView({super.key, required this.future, required this.builder, this.onRetry});
  final Future<T> future;
  final Widget Function(BuildContext, T) builder;
  final VoidCallback? onRetry;
  @override
  Widget build(BuildContext context) => FutureBuilder<T>(
        future: future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
          if (snap.hasError) return ErrorView(message: errorText(snap.error!), onRetry: onRetry);
          return builder(context, snap.data as T);
        },
      );
}

class LabeledValue extends StatelessWidget {
  const LabeledValue(this.label, this.value, {super.key});
  final String label;
  final String? value;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(label.toUpperCase(), style: Theme.of(context).textTheme.labelSmall?.copyWith(color: Colors.grey.shade600)),
          Text((value == null || value!.isEmpty) ? '—' : value!),
        ]),
      );
}

class StatusChip extends StatelessWidget {
  const StatusChip(this.status, {super.key});
  final String status;
  @override
  Widget build(BuildContext context) {
    final color = switch (status) {
      'Active' || 'Completed' => Colors.green,
      'Pending' => Colors.amber.shade800,
      'Overdue' || 'Suspended' => Colors.red,
      _ => Colors.grey,
    };
    return Chip(label: Text(status, style: TextStyle(color: color, fontSize: 12)), visualDensity: VisualDensity.compact, side: BorderSide(color: color.withOpacity(0.4)), backgroundColor: color.withOpacity(0.08));
  }
}
