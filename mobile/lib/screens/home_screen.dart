import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/auth_state.dart';
import 'customers_screen.dart';
import 'dashboard_screen.dart';
import 'followups_screen.dart';
import 'profile_screen.dart';
import 'visits_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _index = 0;
  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthState>();
    final tabs = <({String label, IconData icon, Widget page})>[
      (label: 'Home', icon: Icons.dashboard_outlined, page: const DashboardScreen()),
      if (auth.can('Customer.View')) (label: 'Customers', icon: Icons.people_outline, page: const CustomersScreen()),
      if (auth.can('Visit.View')) (label: 'Visits', icon: Icons.place_outlined, page: const VisitsScreen()),
      if (auth.can('FollowUp.View')) (label: 'Follow-ups', icon: Icons.event_note_outlined, page: const FollowUpsScreen()),
      (label: 'Profile', icon: Icons.person_outline, page: const ProfileScreen()),
    ];
    if (_index >= tabs.length) _index = 0;
    return Scaffold(
      // top: false lets the dashboard header run under the status bar; screens with an AppBar pad themselves.
      body: SafeArea(top: false, child: IndexedStack(index: _index, children: [for (final t in tabs) t.page])),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: [for (final t in tabs) NavigationDestination(icon: Icon(t.icon), label: t.label)],
      ),
    );
  }
}
