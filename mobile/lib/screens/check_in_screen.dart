import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models.dart';
import '../services/location_service.dart';
import '../state/attendance_state.dart';
import '../state/auth_state.dart';
import '../widgets/attendance_widgets.dart';
import '../widgets/charts.dart';
import '../widgets/common.dart';

/// "Start your day": records check-in time and GPS location. Shown after login until the salesman checks in.
/// [standalone] = opened from the dashboard (pops itself after checking in) rather than shown by the gate.
class CheckInScreen extends StatefulWidget {
  const CheckInScreen({super.key, this.standalone = false});
  final bool standalone;
  @override
  State<CheckInScreen> createState() => _CheckInScreenState();
}

class _CheckInScreenState extends State<CheckInScreen> {
  final _note = TextEditingController();
  Timer? _clock;
  LocationFix? _fix;
  DateTime? _fixAt;
  LocationError? _locError;
  bool _locating = false, _busy = false;

  @override
  void initState() {
    super.initState();
    _clock = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
    _locate();
  }

  @override
  void dispose() {
    _clock?.cancel();
    _note.dispose();
    super.dispose();
  }

  Future<void> _locate() async {
    setState(() {
      _locating = true;
      _locError = null;
    });
    try {
      final f = await LocationService.current();
      if (mounted) {
        setState(() {
          _fix = f;
          _fixAt = DateTime.now();
        });
      }
    } on LocationError catch (e) {
      if (mounted) setState(() => _locError = e);
    } finally {
      if (mounted) setState(() => _locating = false);
    }
  }

  Future<void> _start() async {
    final att = context.read<AttendanceState>();
    setState(() => _busy = true);
    try {
      // use the fix shown on screen if it is fresh, otherwise take a new one
      var fix = _fix;
      if (fix == null || _fixAt == null || DateTime.now().difference(_fixAt!) > const Duration(minutes: 2)) {
        fix = await LocationService.current();
      }
      await att.checkIn(fix, note: _note.text);
      if (!mounted) return;
      showSnack(context, 'Checked in at ${fmtTime(DateTime.now())}. Have a great day!');
      if (widget.standalone) Navigator.pop(context);
    } on LocationError catch (e) {
      if (mounted) {
        setState(() => _locError = e);
        await showLocationProblem(context, e);
      }
    } catch (e) {
      if (mounted) showSnack(context, errorText(e), error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthState>();
    final att = context.watch<AttendanceState>();
    final me = auth.me;
    final now = DateTime.now();
    final done = att.todayClosed;
    final top = MediaQuery.of(context).padding.top;

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light,
      child: Scaffold(
        backgroundColor: const Color(0xFFF6F7F9),
        body: ListView(padding: EdgeInsets.zero, children: [
          // header with live clock
          Container(
            padding: EdgeInsets.fromLTRB(20, top + 12, 12, 28),
            decoration: const BoxDecoration(
              gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF0B1220), Color(0xFF0D366B), Color(0xFF1C5CAB)]),
              borderRadius: BorderRadius.vertical(bottom: Radius.circular(28)),
            ),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(
                  child: Text(widget.standalone ? 'Start your day' : 'Hello, ${(me?.fullName ?? '').split(' ').first}',
                      style: const TextStyle(color: Color(0xFF9EC5F4), fontSize: 15, fontWeight: FontWeight.w600)),
                ),
                if (widget.standalone)
                  IconButton(onPressed: () => Navigator.pop(context), icon: const Icon(Icons.close_rounded, color: Colors.white))
                else
                  TextButton.icon(
                    onPressed: () async {
                      await auth.logout();
                      att.clear();
                    },
                    icon: const Icon(Icons.logout_rounded, size: 18, color: Color(0xFFB6C2D4)),
                    label: const Text('Log out', style: TextStyle(color: Color(0xFFB6C2D4))),
                  ),
              ]),
              const SizedBox(height: 18),
              Text(DateFormat.jm().format(now),
                  style: const TextStyle(color: Colors.white, fontSize: 52, height: 1, fontWeight: FontWeight.w700, letterSpacing: -1.5)),
              const SizedBox(height: 6),
              Text(DateFormat('EEEE, d MMMM y').format(now), style: const TextStyle(color: Color(0xFFB6C2D4), fontSize: 15)),
              if (me != null) ...[
                const SizedBox(height: 2),
                Text('${me.roleName} · ${me.companyName}', style: const TextStyle(color: Color(0xFF8A9BB4), fontSize: 13)),
              ],
            ]),
          ),

          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              if (done != null) ...[_DaySummary(s: done), const SizedBox(height: 12)],
              _card(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('Your location', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: kMuted)),
                const SizedBox(height: 10),
                Row(children: [
                  Container(
                    width: 44,
                    height: 44,
                    decoration: BoxDecoration(
                      color: (_locError != null ? kCritical : (_fix != null ? kGood : kSeries)).withAlpha(28),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: _locating
                        ? const Padding(padding: EdgeInsets.all(12), child: CircularProgressIndicator(strokeWidth: 2.5))
                        : Icon(_locError != null ? Icons.location_off_outlined : Icons.my_location_rounded,
                            color: _locError != null ? kCritical : (_fix != null ? kGood : kSeries)),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(
                        _locating ? 'Finding your location…' : (_locError != null ? 'Location unavailable' : (_fix?.label ?? '—')),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontWeight: FontWeight.w600, color: kInk),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        _locError?.message ??
                            (_fix == null
                                ? 'GPS is used to record where you start'
                                : '±${(_fix!.accuracy ?? 0).round()} m · ${_fix!.latitude.toStringAsFixed(5)}, ${_fix!.longitude.toStringAsFixed(5)}'),
                        style: TextStyle(fontSize: 12, color: _locError != null ? kCritical : kMuted),
                      ),
                    ]),
                  ),
                  IconButton(tooltip: 'Refresh location', onPressed: _locating ? null : _locate, icon: const Icon(Icons.refresh_rounded)),
                ]),
                if (_fix?.isMocked == true) ...[
                  const SizedBox(height: 10),
                  const Text('⚠ A fake-GPS app seems to be active. Your check-in will be flagged.',
                      style: TextStyle(fontSize: 12, color: kCritical, fontWeight: FontWeight.w600)),
                ],
                if (_locError?.openSettings == true)
                  TextButton.icon(onPressed: LocationService.openSettings, icon: const Icon(Icons.settings_outlined), label: const Text('Open settings')),
              ])),
              const SizedBox(height: 12),
              _card(TextField(
                controller: _note,
                maxLength: 500,
                maxLines: 2,
                minLines: 1,
                decoration: const InputDecoration(labelText: 'Note (optional)', hintText: 'e.g. starting at the Deira market', border: InputBorder.none, counterText: ''),
              )),
              const SizedBox(height: 20),
              SizedBox(
                height: 56,
                child: FilledButton.icon(
                  style: FilledButton.styleFrom(backgroundColor: kSeries, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16))),
                  onPressed: _busy || _locating ? null : _start,
                  icon: _busy
                      ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2.5, color: Colors.white))
                      : const Icon(Icons.login_rounded),
                  label: Text(done != null ? 'Start a new session' : 'Start my day',
                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                ),
              ),
              const SizedBox(height: 10),
              const Text(
                  'Your check-in time and location are shared with your manager. While you are working, your location is '
                  'also shared every 10 minutes (paused during breaks, stopped when you end your day).',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 12, color: kMuted)),
            ]),
          ),
        ]),
      ),
    );
  }

  Widget _card(Widget child) => Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(18), border: Border.all(color: kBorder)),
        child: child,
      );
}

class _DaySummary extends StatelessWidget {
  const _DaySummary({required this.s});
  final AttendanceSession s;
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(color: kGood.withAlpha(20), borderRadius: BorderRadius.circular(18), border: Border.all(color: kGood.withAlpha(60))),
        child: Row(children: [
          const Icon(Icons.check_circle_rounded, color: kGood, size: 32),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Day complete', style: TextStyle(fontWeight: FontWeight.w700, color: kInk, fontSize: 16)),
              Text('${fmtTime(s.checkInAt)} – ${fmtTime(s.checkOutAt)} · breaks ${fmtDuration(Duration(minutes: s.breakMinutes))}',
                  style: const TextStyle(fontSize: 13, color: Color(0xFF475569))),
            ]),
          ),
          Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
            Text(fmtDuration(Duration(minutes: s.workedMinutes)), style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: kInk)),
            const Text('worked', style: TextStyle(fontSize: 11, color: kMuted)),
          ]),
        ]),
      );
}
