import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/api_client.dart';
import '../models.dart';
import '../state/auth_state.dart';
import '../widgets/common.dart';
import 'customer_detail_screen.dart';
import 'customer_form_screen.dart';

/// Assigned customers + search. For salesmen the API already restricts results to currently assigned customers.
class CustomersScreen extends StatefulWidget {
  const CustomersScreen({super.key});
  @override
  State<CustomersScreen> createState() => _CustomersScreenState();
}

class _CustomersScreenState extends State<CustomersScreen> {
  final _search = TextEditingController();
  Timer? _debounce;
  late Future<PagedList<Customer>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    super.dispose();
  }

  Future<PagedList<Customer>> _load() async {
    final j = await context.read<ApiClient>().get('/customers', query: {'q': _search.text.trim(), 'page_size': 100}) as Map<String, dynamic>;
    return PagedList.fromJson(j, Customer.fromJson);
  }

  void _reload() => setState(() => _future = _load());

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthState>();
    return Scaffold(
      appBar: AppBar(title: Text(auth.isScoped ? 'My customers' : 'Customers')),
      floatingActionButton: (auth.can('Customer.Create') || auth.can('Visit.Create'))
          ? FloatingActionButton.extended(
              onPressed: () async {
                final changed = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => const CustomerFormScreen()));
                if (changed == true) _reload();
              },
              icon: const Icon(Icons.person_add_alt),
              label: const Text('New customer'))
          : null,
      body: Column(children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: TextField(
            controller: _search,
            decoration: const InputDecoration(prefixIcon: Icon(Icons.search), hintText: 'Search name, mobile or city', border: OutlineInputBorder()),
            onChanged: (_) {
              _debounce?.cancel();
              _debounce = Timer(const Duration(milliseconds: 400), _reload);
            },
          ),
        ),
        Expanded(
          child: FutureView<PagedList<Customer>>(
            future: _future,
            onRetry: _reload,
            builder: (context, page) {
              if (page.items.isEmpty) return const EmptyView('No customers found.');
              return RefreshIndicator(
                onRefresh: () async => _reload(),
                child: ListView.separated(
                  itemCount: page.items.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (_, i) {
                    final c = page.items[i];
                    return ListTile(
                      title: Text(c.name),
                      subtitle: Text('${c.mobile} · ${c.city}${c.businessType != null ? ' · ${c.businessType}' : ''}'),
                      trailing: c.status == 'Active' ? const Icon(Icons.chevron_right) : const StatusChip('Inactive'),
                      onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => CustomerDetailScreen(id: c.id))).then((_) => _reload()),
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
