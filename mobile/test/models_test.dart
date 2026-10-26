import 'package:fieldsales_mobile/api/api_client.dart';
import 'package:fieldsales_mobile/models.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('FollowUp parses outcome history in server order and UTC timestamps', () {
    final f = FollowUp.fromJson({
      'id': 5, 'customer_id': 2, 'title': 'Follow-up with Al Noor', 'status': 'Pending', 'is_overdue': false,
      'due_date': '2026-11-01T10:00:00Z', 'completed_at': null, 'notes': null,
      'customer': {'name': 'Al Noor', 'mobile': '+971500000001'}, 'assigned_salesman': {'full_name': 'Sara'},
      'outcomes': [
        {'id': 1, 'outcome_text': 'Customer requested product details', 'recorded_by_name': 'Sara', 'recorded_at': '2026-10-25T08:00:00Z'},
        {'id': 2, 'outcome_text': 'Product details sent', 'recorded_by_name': 'Sara', 'recorded_at': '2026-10-27T08:00:00Z'},
      ],
    });
    expect(f.outcomes.map((o) => o.text), ['Customer requested product details', 'Product details sent']);
    expect(f.dueDate!.isUtc, isFalse); // converted to local time for display
    expect(f.dueDate!.toUtc().hour, 10);
    expect(f.customerName, 'Al Noor');
  });

  test('Me exposes permissions and data scope', () {
    final me = Me.fromJson({'id': 1, 'company_id': 1, 'username': 'u', 'full_name': 'U', 'role': {'name': 'Salesman', 'data_scope': 'assigned'}, 'company_name': 'Acme', 'permissions': ['Customer.View']});
    expect(me.permissions.contains('Customer.View'), isTrue);
    expect(me.dataScope, 'assigned');
  });

  test('ApiClient maps the error envelope and field errors', () async {
    final client = ApiClient(client: MockClient((req) async => http.Response(
        '{"error":{"code":"validation_error","message":"Invalid request","details":[{"field":"mobile","message":"Enter a valid phone number"}]}}', 422,
        headers: {'content-type': 'application/json'})));
    try {
      await client.post('/customers', {});
      fail('expected ApiException');
    } on ApiException catch (e) {
      expect(e.status, 422);
      expect(e.fieldErrors['mobile'], 'Enter a valid phone number');
    }
  });

  test('ApiClient sends the bearer token and calls onUnauthorized on 401', () async {
    String? auth;
    final client = ApiClient(client: MockClient((req) async {
      auth = req.headers['Authorization'];
      return http.Response('{"error":{"code":"unauthorized","message":"Token has expired"}}', 401);
    }));
    var expired = false;
    client.token = 'abc';
    client.onUnauthorized = () => expired = true;
    await expectLater(client.get('/auth/me'), throwsA(isA<ApiException>()));
    expect(auth, 'Bearer abc');
    expect(expired, isTrue);
  });
}
