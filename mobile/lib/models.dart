import 'package:intl/intl.dart';

DateTime? parseUtc(dynamic v) => v == null ? null : DateTime.parse(v as String).toLocal();
String fmtDateTime(DateTime? d) => d == null ? '—' : DateFormat.yMMMd().add_jm().format(d);
String fmtDate(DateTime? d) => d == null ? '—' : DateFormat.yMMMd().format(d);

const businessTypes = [
  'EzeeStitch', 'Accounts', 'Medical', 'Tours', 'Saloon', 'Restaurant', 'RealState', 'Gym', 'Mobile POS',
  'Super Market', 'Basic POS Trading', 'Basic Sales Trading',
];
const visitOutcomes = ['Interested', 'Not Interested', 'Needs Follow-up', 'Demo Scheduled', 'Deal Closed', 'No Answer', 'Other'];

class Me {
  final int id, companyId;
  final String username, fullName, roleName, dataScope, companyName;
  final String? email, mobile;
  final Set<String> permissions;
  Me.fromJson(Map<String, dynamic> j)
      : id = j['id'],
        companyId = j['company_id'],
        username = j['username'],
        fullName = j['full_name'],
        email = j['email'],
        mobile = j['mobile'],
        roleName = j['role']['name'],
        dataScope = j['role']['data_scope'],
        companyName = j['company_name'] ?? '',
        permissions = Set<String>.from(j['permissions'] ?? const []);
}

class Customer {
  final int id;
  final String name, mobile, city, country, status;
  final String? businessType, product, contactPerson, contactPersonMobile, address, email, locationUrl, photoUrl, notes, salesmanName;
  Customer.fromJson(Map<String, dynamic> j)
      : id = j['id'],
        name = j['name'],
        mobile = j['mobile'],
        city = j['city'],
        country = j['country'] ?? '',
        status = j['status'],
        businessType = j['business_type'],
        product = j['product'],
        contactPerson = j['contact_person'],
        contactPersonMobile = j['contact_person_mobile'],
        address = j['address'],
        email = j['email'],
        locationUrl = j['location_url'],
        photoUrl = j['business_photo_url'],
        notes = j['notes'],
        salesmanName = j['assigned_salesman']?['full_name'];
}

class Visit {
  final int id, customerId, userId;
  final int? followUpId;
  final String? customerName, userName, purpose, notes, outcome, photoUrl, branchName;
  final DateTime? visitTime;
  final double? latitude, longitude;
  Visit.fromJson(Map<String, dynamic> j)
      : id = j['id'],
        customerId = j['customer_id'],
        userId = j['user_id'],
        followUpId = j['follow_up_id'],
        customerName = j['customer_name'],
        userName = j['user_name'],
        purpose = j['purpose'],
        notes = j['notes'],
        outcome = j['outcome'],
        photoUrl = j['photo_url'],
        branchName = j['branch_name'],
        visitTime = parseUtc(j['visit_time']),
        latitude = (j['latitude'] as num?)?.toDouble(),
        longitude = (j['longitude'] as num?)?.toDouble();
}

class Outcome {
  final int id;
  final String text;
  final String? by;
  final DateTime? at;
  Outcome.fromJson(Map<String, dynamic> j)
      : id = j['id'],
        text = j['outcome_text'],
        by = j['recorded_by_name'],
        at = parseUtc(j['recorded_at']);
}

class FollowUp {
  final int id, customerId;
  final String title, status;
  final String? notes, customerName, customerMobile, salesmanName, createdByName;
  final DateTime? dueDate, completedAt;
  final bool isOverdue;
  final List<Outcome> outcomes;
  FollowUp.fromJson(Map<String, dynamic> j)
      : id = j['id'],
        customerId = j['customer_id'],
        title = j['title'],
        status = j['status'],
        notes = j['notes'],
        customerName = j['customer']?['name'],
        customerMobile = j['customer']?['mobile'],
        salesmanName = j['assigned_salesman']?['full_name'],
        createdByName = j['created_by_name'],
        dueDate = parseUtc(j['due_date']),
        completedAt = parseUtc(j['completed_at']),
        isOverdue = j['is_overdue'] == true,
        outcomes = ((j['outcomes'] ?? const []) as List).map((o) => Outcome.fromJson(o as Map<String, dynamic>)).toList();
}

class PagedList<T> {
  final List<T> items;
  final int total;
  PagedList(this.items, this.total);
  factory PagedList.fromJson(Map<String, dynamic> j, T Function(Map<String, dynamic>) f) =>
      PagedList((j['items'] as List).map((e) => f(e as Map<String, dynamic>)).toList(), j['total'] as int);
}

// ---------- attendance ----------
class PlaceInfo {
  final double? latitude, longitude, accuracy;
  final String? address, area;
  final bool isMocked;
  PlaceInfo.fromJson(Map<String, dynamic> j)
      : latitude = (j['latitude'] as num?)?.toDouble(),
        longitude = (j['longitude'] as num?)?.toDouble(),
        accuracy = (j['accuracy'] as num?)?.toDouble(),
        address = j['address'],
        area = j['area'],
        isMocked = j['is_mocked'] == true;
  String get label => area ?? address ?? (latitude == null ? '—' : '${latitude!.toStringAsFixed(5)}, ${longitude!.toStringAsFixed(5)}');
}

class AttendanceBreak {
  final int id, minutes;
  final String breakType;
  final DateTime startAt;
  final DateTime? endAt;
  final PlaceInfo start;
  final PlaceInfo? end;
  AttendanceBreak.fromJson(Map<String, dynamic> j)
      : id = j['id'],
        minutes = j['minutes'] ?? 0,
        breakType = j['break_type'] ?? 'Other',
        startAt = parseUtc(j['start_at'])!,
        endAt = parseUtc(j['end_at']),
        start = PlaceInfo.fromJson(j['start'] as Map<String, dynamic>),
        end = j['end'] == null ? null : PlaceInfo.fromJson(j['end'] as Map<String, dynamic>);
}

class AttendanceSession {
  final int id, breakMinutes, workedMinutes;
  final String status, state, userName;
  final String? checkOutMethod;
  final DateTime workDate, checkInAt;
  final DateTime? checkOutAt;
  final PlaceInfo checkIn;
  final PlaceInfo? checkOut;
  final List<AttendanceBreak> breaks;
  final bool anyMocked;
  AttendanceSession.fromJson(Map<String, dynamic> j)
      : id = j['id'],
        breakMinutes = j['break_minutes'] ?? 0,
        workedMinutes = j['worked_minutes'] ?? 0,
        status = j['status'] ?? 'Open',
        state = j['state'] ?? 'working',
        userName = j['user_name'] ?? '',
        checkOutMethod = j['check_out_method'],
        workDate = DateTime.parse(j['work_date'] as String),
        checkInAt = parseUtc(j['check_in_at'])!,
        checkOutAt = parseUtc(j['check_out_at']),
        checkIn = PlaceInfo.fromJson(j['check_in'] as Map<String, dynamic>),
        checkOut = j['check_out'] == null ? null : PlaceInfo.fromJson(j['check_out'] as Map<String, dynamic>),
        breaks = ((j['breaks'] ?? const []) as List).map((b) => AttendanceBreak.fromJson(b as Map<String, dynamic>)).toList(),
        anyMocked = j['any_mocked'] == true;

  bool get onBreak => state == 'on_break';
  bool get isOpen => status == 'Open';
  AttendanceBreak? get openBreak => breaks.where((b) => b.endAt == null).firstOrNull;

  /// Live worked time: (check-out or now) - check-in - breaks.
  Duration workedAt(DateTime now) {
    final end = checkOutAt ?? now;
    var total = end.difference(checkInAt);
    for (final b in breaks) {
      total -= (b.endAt ?? end).difference(b.startAt);
    }
    return total.isNegative ? Duration.zero : total;
  }

  Duration breakAt(DateTime now) {
    final end = checkOutAt ?? now;
    var total = Duration.zero;
    for (final b in breaks) {
      total += (b.endAt ?? end).difference(b.startAt);
    }
    return total;
  }
}

String fmtDuration(Duration d) {
  final h = d.inHours, m = d.inMinutes.remainder(60);
  return h > 0 ? '${h}h ${m.toString().padLeft(2, '0')}m' : '${m}m';
}

String fmtTime(DateTime? d) => d == null ? '—' : DateFormat.jm().format(d);
