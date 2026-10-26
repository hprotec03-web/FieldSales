import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/attendance_state.dart';
import '../state/auth_state.dart';
import '../widgets/common.dart';
import 'check_in_screen.dart';

/// Salesmen (attendance required) must check in before they can use the app.
/// Other roles pass straight through to [child].
class AttendanceGate extends StatefulWidget {
  const AttendanceGate({super.key, required this.child});
  final Widget child;
  @override
  State<AttendanceGate> createState() => _AttendanceGateState();
}

class _AttendanceGateState extends State<AttendanceGate> with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  /// Coming back to the app (e.g. next morning) re-checks today's attendance.
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed) return;
    final me = context.read<AuthState>().me;
    if (me != null && context.read<AuthState>().can('Attendance.Mark')) context.read<AttendanceState>().load(me.id);
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthState>();
    final me = auth.me;
    final att = context.watch<AttendanceState>();
    if (me == null || !auth.can('Attendance.Mark')) return widget.child;

    // first load for this user (also keeps the dashboard attendance card up to date for managers)
    if (att.userId != me.id && !att.loading) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && context.read<AttendanceState>().userId != me.id) context.read<AttendanceState>().load(me.id);
      });
    }
    final mustCheckIn = auth.isScoped; // salesmen
    if (!mustCheckIn) return widget.child;

    if (att.userId != me.id || (att.loading && att.session == null && att.todayClosed == null)) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (att.session != null) return widget.child;
    if (att.error != null && att.todayClosed == null) {
      return Scaffold(
        body: SafeArea(
          child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
            ErrorView(message: errorText(att.error!), onRetry: () => att.load(me.id)),
            TextButton(
              onPressed: () async {
                await auth.logout();
                att.clear();
              },
              child: const Text('Log out'),
            ),
          ]),
        ),
      );
    }
    return const CheckInScreen();
  }
}
