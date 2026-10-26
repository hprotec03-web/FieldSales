import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/api_client.dart';
import '../state/auth_state.dart';
import '../widgets/attendance_widgets.dart';
import '../widgets/common.dart';
import 'attendance_history_screen.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthState>();
    final me = auth.me;
    if (me == null) return const SizedBox.shrink();
    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Text(me.fullName, style: Theme.of(context).textTheme.headlineSmall),
        LabeledValue('Username', me.username), LabeledValue('Role', me.roleName), LabeledValue('Company', me.companyName),
        LabeledValue('Email', me.email), LabeledValue('Mobile', me.mobile),
        const SizedBox(height: 16),
        if (auth.can('Attendance.Mark')) ...[
          OutlinedButton.icon(
            icon: const Icon(Icons.history_rounded),
            label: const Text('My attendance'),
            onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const AttendanceHistoryScreen())),
          ),
          const SizedBox(height: 8),
        ],
        OutlinedButton.icon(icon: const Icon(Icons.lock_outline), label: const Text('Change password'), onPressed: () => showDialog(context: context, builder: (_) => const _PasswordDialog())),
        const SizedBox(height: 8),
        FilledButton.tonalIcon(
          icon: const Icon(Icons.logout),
          label: const Text('Log out'),
          onPressed: () => logoutWithAttendance(context),
        ),
      ]),
    );
  }
}

class _PasswordDialog extends StatefulWidget {
  const _PasswordDialog();
  @override
  State<_PasswordDialog> createState() => _PasswordDialogState();
}

class _PasswordDialogState extends State<_PasswordDialog> {
  final _form = GlobalKey<FormState>();
  final _cur = TextEditingController(), _new = TextEditingController(), _confirm = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Change password'),
      content: Form(
        key: _form,
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          if (_error != null) Text(_error!, style: TextStyle(color: Colors.red.shade800)),
          TextFormField(controller: _cur, obscureText: true, decoration: const InputDecoration(labelText: 'Current password'), validator: (v) => (v == null || v.isEmpty) ? 'Required' : null),
          TextFormField(controller: _new, obscureText: true, decoration: const InputDecoration(labelText: 'New password'),
              validator: (v) => (v != null && v.length >= 8 && RegExp(r'[A-Za-z]').hasMatch(v) && RegExp(r'\d').hasMatch(v)) ? null : 'At least 8 characters with letters and digits'),
          TextFormField(controller: _confirm, obscureText: true, decoration: const InputDecoration(labelText: 'Confirm new password'), validator: (v) => v == _new.text ? null : 'Passwords do not match'),
        ]),
      ),
      actions: [
        TextButton(onPressed: _busy ? null : () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(
          onPressed: _busy ? null : () async {
            if (!_form.currentState!.validate()) return;
            setState(() { _busy = true; _error = null; });
            try {
              await context.read<ApiClient>().post('/auth/change-password', {'current_password': _cur.text, 'new_password': _new.text});
              if (mounted) { Navigator.pop(context); showSnack(context, 'Password changed'); }
            } catch (e) {
              if (mounted) setState(() => _error = errorText(e));
            } finally {
              if (mounted) setState(() => _busy = false);
            }
          },
          child: const Text('Change'),
        ),
      ],
    );
  }
}
