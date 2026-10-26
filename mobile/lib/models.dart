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
