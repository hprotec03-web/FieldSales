import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../api/api_client.dart';
import '../models.dart';
import '../services/reminder_service.dart';
import '../state/auth_state.dart';
import '../widgets/common.dart';
import 'customer_form_screen.dart';

class VisitFormScreen extends StatefulWidget {
  const VisitFormScreen({super.key, this.customer, this.startWithNewCustomer = false});
  final Customer? customer;
  final bool startWithNewCustomer;
  @override
  State<VisitFormScreen> createState() => _VisitFormScreenState();
}

class _VisitFormScreenState extends State<VisitFormScreen> {
  final _form = GlobalKey<FormState>();
  final _newCustomer = CustomerFields();
  final _purpose = TextEditingController(), _notes = TextEditingController(), _fuNotes = TextEditingController(), _search = TextEditingController();
  late bool _newMode;
  Customer? _selected;
  List<Customer> _results = [];
  bool _searching = false;
  DateTime _visitTime = DateTime.now();
  DateTime? _followUp;
  bool _remind = true;
  String? _outcome;
  int? _branchId;
  List<Map<String, dynamic>> _branches = [];
  double? _lat, _lng;
  String? _geoMessage;
  XFile? _photo;
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _selected = widget.customer;
    _newMode = widget.startWithNewCustomer;
    _loadBranches();
    if (!_newMode && _selected == null) _doSearch();
  }

  Future<void> _loadBranches() async {
    final auth = context.read<AuthState>();
    if (!auth.can('Branch.View')) return;
    try {
      final list = await context.read<ApiClient>().get('/branches') as List;
      if (mounted) setState(() => _branches = list.cast<Map<String, dynamic>>().where((b) => b['is_active'] == true).toList());
    } catch (_) {/* branch is optional */}
  }

  Future<void> _doSearch() async {
    setState(() => _searching = true);
    try {
      final j = await context.read<ApiClient>().get('/customers', query: {'q': _search.text.trim(), 'status': 'Active', 'page_size': 20}) as Map<String, dynamic>;
      if (mounted) setState(() => _results = PagedList.fromJson(j, Customer.fromJson).items);
    } catch (e) {
      if (mounted) showSnack(context, errorText(e), error: true);
    } finally {
      if (mounted) setState(() => _searching = false);
    }
  }

  Future<DateTime?> _pickDateTime(DateTime initial) async {
    final d = await showDatePicker(context: context, initialDate: initial, firstDate: DateTime(2020), lastDate: DateTime(2100));
    if (d == null || !mounted) return null;
    final t = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(initial));
    if (t == null) return null;
    return DateTime(d.year, d.month, d.day, t.hour, t.minute);
  }

  /// Location is requested only when the user taps the button; recording a visit never requires it.
  Future<void> _captureLocation() async {
    setState(() => _geoMessage = null);
    try {
      if (!await Geolocator.isLocationServiceEnabled()) {
        setState(() => _geoMessage = 'Location services are turned off. You can still save the visit without a location.');
        return;
      }
      var perm = await Geolocator.checkPermission();
      if (perm == LocationPermission.denied) perm = await Geolocator.requestPermission();
      if (perm == LocationPermission.denied || perm == LocationPermission.deniedForever) {
        setState(() => _geoMessage = perm == LocationPermission.deniedForever
            ? 'Location permission is blocked. Enable it in system settings, or save the visit without it.'
            : 'Location permission denied. You can still save the visit without it.');
        return;
      }
      final p = await Geolocator.getCurrentPosition(locationSettings: const LocationSettings(accuracy: LocationAccuracy.high, timeLimit: Duration(seconds: 15)));
      setState(() { _lat = double.parse(p.latitude.toStringAsFixed(6)); _lng = double.parse(p.longitude.toStringAsFixed(6)); });
    } catch (_) {
      setState(() => _geoMessage = 'Could not get your location. You can still save the visit without it.');
    }
  }

  Future<void> _pickPhoto(ImageSource source) async {
    try {
      final f = await ImagePicker().pickImage(source: source, maxWidth: 1600, imageQuality: 85);
      if (f != null) setState(() => _photo = f);
    } catch (_) {
      if (mounted) showSnack(context, 'Could not access the ${source == ImageSource.camera ? 'camera' : 'gallery'}. Check app permissions.', error: true);
    }
  }

  Future<void> _submit() async {
    if (!_newMode && _selected == null) { setState(() => _error = 'Select a customer or create a new one.'); return; }
    if (!_form.currentState!.validate()) return;
    setState(() { _busy = true; _error = null; });
    final api = context.read<ApiClient>();
    final reminders = context.read<ReminderService>();
    try {
      final body = <String, dynamic>{
        'visit_time': _visitTime.toUtc().toIso8601String(),
        'purpose': _purpose.text.trim().isEmpty ? null : _purpose.text.trim(),
        'notes': _notes.text.trim().isEmpty ? null : _notes.text.trim(),
        'outcome': _outcome, 'branch_id': _branchId, 'latitude': _lat, 'longitude': _lng,
        'follow_up_date': _followUp?.toUtc().toIso8601String(),
        'follow_up_notes': _fuNotes.text.trim().isEmpty ? null : _fuNotes.text.trim(),
        if (_newMode) 'new_customer': _newCustomer.toJson() else 'customer_id': _selected!.id,
      };
      final visit = await api.post('/visits', body) as Map<String, dynamic>;
      if (_photo != null) {
        try {
          await api.upload('/visits/${visit['id']}/photo', _photo!.path);
        } catch (e) {
          if (mounted) showSnack(context, 'Visit saved, but the photo failed: ${errorText(e)}', error: true);
        }
      }
      final fuId = visit['follow_up_id'] as int?;
      if (fuId != null && _remind) {
        final fu = FollowUp.fromJson(await api.get('/followups/$fuId') as Map<String, dynamic>);
        if (await reminders.requestPermission()) await reminders.schedule(fu);
      }
      if (mounted) { showSnack(context, fuId != null ? 'Visit and follow-up saved' : 'Visit saved'); Navigator.pop(context, true); }
    } catch (e) {
      if (mounted) setState(() => _error = errorText(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthState>();
    final canPickExisting = auth.can('Customer.View');
    InputDecoration d(String l) => InputDecoration(labelText: l, border: const OutlineInputBorder());
    return Scaffold(
      appBar: AppBar(title: const Text('Record visit')),
      body: Form(
        key: _form,
        child: ListView(padding: const EdgeInsets.all(16), children: [
          if (_error != null) Container(padding: const EdgeInsets.all(12), margin: const EdgeInsets.only(bottom: 12), decoration: BoxDecoration(color: Colors.red.shade50, borderRadius: BorderRadius.circular(8)), child: Text(_error!, style: TextStyle(color: Colors.red.shade800))),
          if (widget.customer == null && canPickExisting)
            SegmentedButton<bool>(
              segments: const [ButtonSegment(value: false, label: Text('Existing customer')), ButtonSegment(value: true, label: Text('New customer'))],
              selected: {_newMode},
              onSelectionChanged: (s) => setState(() => _newMode = s.first),
            ),
          const SizedBox(height: 12),
          if (_newMode) ...[
            const Text('The new customer is created with this visit and assigned to you.', style: TextStyle(color: Colors.grey)),
            const SizedBox(height: 12),
            CustomerFieldsForm(fields: _newCustomer),
          ] else if (widget.customer != null)
            ListTile(tileColor: Colors.blue.shade50, title: Text(widget.customer!.name), subtitle: Text('${widget.customer!.mobile} · ${widget.customer!.city}'))
          else ...[
            if (_selected != null) ListTile(tileColor: Colors.blue.shade50, title: Text(_selected!.name), subtitle: const Text('Selected'), trailing: IconButton(icon: const Icon(Icons.close), onPressed: () => setState(() => _selected = null))),
            TextField(controller: _search, decoration: InputDecoration(labelText: 'Search customers', border: const OutlineInputBorder(), suffixIcon: IconButton(icon: const Icon(Icons.search), onPressed: _doSearch)), onSubmitted: (_) => _doSearch()),
            if (_searching) const Padding(padding: EdgeInsets.all(12), child: Center(child: CircularProgressIndicator()))
            else if (_results.isEmpty) const Padding(padding: EdgeInsets.all(12), child: Text('No customers found.', style: TextStyle(color: Colors.grey)))
            else for (final c in _results) ListTile(dense: true, title: Text(c.name), subtitle: Text('${c.mobile} · ${c.city}'), selected: _selected?.id == c.id, onTap: () => setState(() => _selected = c)),
          ],
          const Divider(height: 32),
          ListTile(contentPadding: EdgeInsets.zero, title: const Text('Visit time'), subtitle: Text(fmtDateTime(_visitTime)), trailing: const Icon(Icons.edit_calendar_outlined),
              onTap: () async { final v = await _pickDateTime(_visitTime); if (v != null) setState(() => _visitTime = v); }),
          const SizedBox(height: 8),
          TextFormField(controller: _purpose, decoration: d('Purpose'), maxLength: 300),
          DropdownButtonFormField<String>(value: _outcome, decoration: d('Outcome'), items: [for (final o in visitOutcomes) DropdownMenuItem(value: o, child: Text(o))], onChanged: (v) => setState(() => _outcome = v)),
          const SizedBox(height: 12),
          if (_branches.isNotEmpty) ...[
            DropdownButtonFormField<int>(value: _branchId, decoration: d('Branch (optional)'), items: [for (final b in _branches) DropdownMenuItem(value: b['id'] as int, child: Text(b['name'] as String))], onChanged: (v) => setState(() => _branchId = v)),
            const SizedBox(height: 12),
          ],
          TextFormField(controller: _notes, decoration: d('Notes'), maxLines: 3),
          const SizedBox(height: 16),
          Wrap(spacing: 8, runSpacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [
            OutlinedButton.icon(onPressed: _captureLocation, icon: const Icon(Icons.my_location), label: Text(_lat == null ? 'Capture location (optional)' : '$_lat, $_lng')),
            if (_lat != null) TextButton(onPressed: () => setState(() { _lat = null; _lng = null; }), child: const Text('Clear')),
            OutlinedButton.icon(onPressed: () => _pickPhoto(ImageSource.camera), icon: const Icon(Icons.photo_camera_outlined), label: const Text('Take photo')),
            OutlinedButton.icon(onPressed: () => _pickPhoto(ImageSource.gallery), icon: const Icon(Icons.photo_library_outlined), label: const Text('Choose photo')),
            if (_photo != null) Chip(label: Text(_photo!.name, overflow: TextOverflow.ellipsis), onDeleted: () => setState(() => _photo = null)),
          ]),
          if (_geoMessage != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(_geoMessage!, style: TextStyle(color: Colors.amber.shade900, fontSize: 12))),
          if (auth.can('FollowUp.Create')) ...[
            const Divider(height: 32),
            Text('Follow-up (optional)', style: Theme.of(context).textTheme.titleMedium),
            ListTile(contentPadding: EdgeInsets.zero, title: Text(_followUp == null ? 'No follow-up' : fmtDateTime(_followUp)), subtitle: const Text('Pick a date to create a pending follow-up'),
                trailing: _followUp == null ? const Icon(Icons.event_outlined) : IconButton(icon: const Icon(Icons.close), onPressed: () => setState(() => _followUp = null)),
                onTap: () async { final v = await _pickDateTime(DateTime.now().add(const Duration(days: 1))); if (v != null) setState(() => _followUp = v); }),
            if (_followUp != null) ...[
              TextFormField(controller: _fuNotes, decoration: d('Follow-up notes'), maxLines: 2),
              SwitchListTile(contentPadding: EdgeInsets.zero, title: const Text('Remind me 1 hour before'), value: _remind, onChanged: (v) => setState(() => _remind = v)),
            ],
          ],
          const SizedBox(height: 24),
          FilledButton(onPressed: _busy ? null : _submit, child: _busy ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2)) : const Text('Save visit')),
          const SizedBox(height: 24),
        ]),
      ),
    );
  }
}
