import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../api/api_client.dart';
import '../models.dart';
import '../state/auth_state.dart';
import '../widgets/common.dart';
import 'visit_form_screen.dart';
import 'visits_screen.dart';

class CustomerDetailScreen extends StatefulWidget {
  const CustomerDetailScreen({super.key, required this.id});
  final int id;
  @override
  State<CustomerDetailScreen> createState() => _CustomerDetailScreenState();
}

class _CustomerDetailScreenState extends State<CustomerDetailScreen> {
  late Future<Customer> _future;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<Customer> _load() async => Customer.fromJson(await context.read<ApiClient>().get('/customers/${widget.id}') as Map<String, dynamic>);
  void _reload() => setState(() => _future = _load());

  Future<void> _addPhoto(Customer c) async {
    // Camera permission is requested by the OS only when the user taps this button.
    try {
      final picked = await ImagePicker().pickImage(source: ImageSource.camera, maxWidth: 1600, imageQuality: 85);
      if (picked == null) return;
      setState(() => _busy = true);
      await context.read<ApiClient>().upload('/customers/${c.id}/photo', picked.path);
      showSnack(context, 'Photo uploaded');
      _reload();
    } catch (e) {
      showSnack(context, errorText(e), error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthState>();
    return Scaffold(
      appBar: AppBar(title: const Text('Customer')),
      body: FutureView<Customer>(
        future: _future,
        onRetry: _reload,
        builder: (context, c) => ListView(padding: const EdgeInsets.all(16), children: [
          Row(children: [Expanded(child: Text(c.name, style: Theme.of(context).textTheme.headlineSmall)), StatusChip(c.status)]),
          const SizedBox(height: 8),
          Wrap(spacing: 8, children: [
            if (auth.can('Visit.Create') && c.status == 'Active')
              FilledButton.icon(icon: const Icon(Icons.add_location_alt_outlined), label: const Text('Record visit'),
                  onPressed: () async { if (await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => VisitFormScreen(customer: c))) == true) _reload(); }),
            OutlinedButton.icon(icon: const Icon(Icons.history), label: const Text('Visit history'),
                onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => VisitsScreen(customerId: c.id, title: c.name)))),
            if (auth.can('Visit.Create') || auth.can('Customer.Edit'))
              OutlinedButton.icon(icon: const Icon(Icons.photo_camera_outlined), label: const Text('Add photo'), onPressed: _busy ? null : () => _addPhoto(c)),
          ]),
          const Divider(height: 32),
          LabeledValue('Mobile', c.mobile), LabeledValue('City', '${c.city}, ${c.country}'), LabeledValue('Business type', c.businessType), LabeledValue('Product', c.product),
          LabeledValue('Contact person', c.contactPerson), LabeledValue('Contact mobile', c.contactPersonMobile), LabeledValue('Email', c.email),
          LabeledValue('Address', c.address), LabeledValue('Location', c.locationUrl), LabeledValue('Responsible salesman', c.salesmanName ?? 'Unassigned'), LabeledValue('Notes', c.notes),
          if (c.photoUrl != null) ...[const SizedBox(height: 12), _PrivateImage(path: c.photoUrl!)],
        ]),
      ),
    );
  }
}

class _PrivateImage extends StatefulWidget {
  const _PrivateImage({required this.path});
  final String path;
  @override
  State<_PrivateImage> createState() => _PrivateImageState();
}

class _PrivateImageState extends State<_PrivateImage> {
  late Future<List<int>> _bytes;
  @override
  void initState() {
    super.initState();
    _bytes = context.read<ApiClient>().bytes(widget.path);
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<List<int>>(
        future: _bytes,
        builder: (_, s) {
          if (s.connectionState != ConnectionState.done) return const SizedBox(height: 120, child: Center(child: CircularProgressIndicator()));
          if (s.hasError) return const Text('Photo unavailable.', style: TextStyle(color: Colors.grey));
          return ClipRRect(borderRadius: BorderRadius.circular(8), child: Image.memory(Uint8List.fromList(s.data!)));
        },
      );
}
