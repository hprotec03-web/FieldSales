import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/api_client.dart';
import '../models.dart';
import '../state/auth_state.dart';
import '../widgets/common.dart';
import 'visit_form_screen.dart';

/// "Create customer". Users with Customer.Create add the customer directly. Salesmen (no Customer.Create) use the
/// Visit workflow instead: the customer is created together with the first visit and assigned to them.
class CustomerFormScreen extends StatefulWidget {
  const CustomerFormScreen({super.key});
  @override
  State<CustomerFormScreen> createState() => _CustomerFormScreenState();
}

class CustomerFields {
  final name = TextEditingController(), mobile = TextEditingController(), city = TextEditingController(),
      country = TextEditingController(), contact = TextEditingController(), contactMobile = TextEditingController(),
      email = TextEditingController(), address = TextEditingController(), notes = TextEditingController();
  String? businessType, product;

  Map<String, dynamic> toJson() => {
        'name': name.text.trim(), 'mobile': mobile.text.trim(), 'city': city.text.trim(),
        'country': country.text.trim().isEmpty ? null : country.text.trim(),
        'business_type': businessType, 'product': product,
        'contact_person': _n(contact), 'contact_person_mobile': _n(contactMobile), 'email': _n(email), 'address': _n(address), 'notes': _n(notes),
      };
  static String? _n(TextEditingController c) => c.text.trim().isEmpty ? null : c.text.trim();
}

/// Reusable customer fields (used by this screen and by the visit form's "new customer" mode).
class CustomerFieldsForm extends StatefulWidget {
  const CustomerFieldsForm({super.key, required this.fields});
  final CustomerFields fields;
  @override
  State<CustomerFieldsForm> createState() => _CustomerFieldsFormState();
}

class _CustomerFieldsFormState extends State<CustomerFieldsForm> {
  @override
  Widget build(BuildContext context) {
    final f = widget.fields;
    InputDecoration d(String l) => InputDecoration(labelText: l, border: const OutlineInputBorder());
    const gap = SizedBox(height: 12);
    return Column(children: [
      TextFormField(controller: f.name, decoration: d('Name *'), validator: (v) => (v == null || v.trim().isEmpty) ? 'Name is required' : null),
      gap,
      TextFormField(controller: f.mobile, keyboardType: TextInputType.phone, decoration: d('Mobile *'),
          validator: (v) => RegExp(r'^\+?[\d\s\-().]{6,20}$').hasMatch((v ?? '').trim()) ? null : 'Enter a valid phone number'),
      gap,
      TextFormField(controller: f.city, decoration: d('City *'), validator: (v) => (v == null || v.trim().isEmpty) ? 'City is required' : null),
      gap,
      TextFormField(controller: f.country, decoration: d('Country (default: United Arab Emirates)')),
      gap,
      DropdownButtonFormField<String>(value: f.businessType, decoration: d('Business type'), items: [for (final b in businessTypes) DropdownMenuItem(value: b, child: Text(b))], onChanged: (v) => setState(() => f.businessType = v)),
      gap,
      DropdownButtonFormField<String>(value: f.product, decoration: d('Product'), items: [for (final b in businessTypes) DropdownMenuItem(value: b, child: Text(b))], onChanged: (v) => setState(() => f.product = v)),
      gap,
      TextFormField(controller: f.contact, decoration: d('Contact person')),
      gap,
      TextFormField(controller: f.contactMobile, keyboardType: TextInputType.phone, decoration: d('Contact person mobile'),
          validator: (v) => (v == null || v.trim().isEmpty || RegExp(r'^\+?[\d\s\-().]{6,20}$').hasMatch(v.trim())) ? null : 'Enter a valid phone number'),
      gap,
      TextFormField(controller: f.email, keyboardType: TextInputType.emailAddress, decoration: d('Email'),
          validator: (v) => (v == null || v.trim().isEmpty || RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$').hasMatch(v.trim())) ? null : 'Enter a valid email'),
      gap,
      TextFormField(controller: f.address, decoration: d('Address')),
      gap,
      TextFormField(controller: f.notes, maxLines: 3, decoration: d('Notes')),
    ]);
  }
}

class _CustomerFormScreenState extends State<CustomerFormScreen> {
  final _form = GlobalKey<FormState>();
  final _fields = CustomerFields();
  bool _busy = false;
  String? _error;

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthState>();
    if (!auth.can('Customer.Create')) {
      // Salesman: customers are created through the visit workflow.
      return const VisitFormScreen(startWithNewCustomer: true);
    }
    return Scaffold(
      appBar: AppBar(title: const Text('New customer')),
      body: Form(
        key: _form,
        child: ListView(padding: const EdgeInsets.all(16), children: [
          if (_error != null) Padding(padding: const EdgeInsets.only(bottom: 12), child: Text(_error!, style: TextStyle(color: Colors.red.shade800))),
          CustomerFieldsForm(fields: _fields),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _busy ? null : () async {
              if (!_form.currentState!.validate()) return;
              setState(() { _busy = true; _error = null; });
              try {
                await context.read<ApiClient>().post('/customers', _fields.toJson());
                if (mounted) { showSnack(context, 'Customer created'); Navigator.pop(context, true); }
              } catch (e) {
                if (mounted) setState(() => _error = errorText(e));
              } finally {
                if (mounted) setState(() => _busy = false);
              }
            },
            child: _busy ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2)) : const Text('Create customer'),
          ),
        ]),
      ),
    );
  }
}
