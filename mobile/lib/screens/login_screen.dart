import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/auth_state.dart';
import '../widgets/common.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _form = GlobalKey<FormState>();
  final _user = TextEditingController();
  final _pass = TextEditingController();
  bool _busy = false, _hide = true;
  String? _error;

  Future<void> _submit() async {
    if (!_form.currentState!.validate()) return;
    setState(() { _busy = true; _error = null; });
    try {
      await context.read<AuthState>().login(_user.text, _pass.text);
    } catch (e) {
      if (mounted) setState(() => _error = errorText(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 400),
              child: Form(
                key: _form,
                child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  Text('FieldSales', textAlign: TextAlign.center, style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.bold, color: Theme.of(context).colorScheme.primary)),
                  const SizedBox(height: 24),
                  if (_error != null) Container(padding: const EdgeInsets.all(12), margin: const EdgeInsets.only(bottom: 12), decoration: BoxDecoration(color: Colors.red.shade50, borderRadius: BorderRadius.circular(8)), child: Text(_error!, style: TextStyle(color: Colors.red.shade800))),
                  TextFormField(controller: _user, decoration: const InputDecoration(labelText: 'Username', border: OutlineInputBorder()), autofillHints: const [AutofillHints.username], textInputAction: TextInputAction.next, validator: (v) => (v == null || v.trim().isEmpty) ? 'Username is required' : null),
                  const SizedBox(height: 12),
                  TextFormField(controller: _pass, obscureText: _hide, autofillHints: const [AutofillHints.password], onFieldSubmitted: (_) => _submit(),
                      decoration: InputDecoration(labelText: 'Password', border: const OutlineInputBorder(), suffixIcon: IconButton(icon: Icon(_hide ? Icons.visibility : Icons.visibility_off), onPressed: () => setState(() => _hide = !_hide))),
                      validator: (v) => (v == null || v.isEmpty) ? 'Password is required' : null),
                  const SizedBox(height: 20),
                  FilledButton(onPressed: _busy ? null : _submit, child: _busy ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2)) : const Text('Sign in')),
                ]),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
