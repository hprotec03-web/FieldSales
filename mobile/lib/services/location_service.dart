import 'dart:async';

import 'package:geocoding/geocoding.dart';
import 'package:geolocator/geolocator.dart';

/// A GPS fix plus a readable place name (when the phone's geocoder can provide one).
class LocationFix {
  LocationFix({required this.latitude, required this.longitude, this.accuracy, this.isMocked = false, this.address, this.area});
  final double latitude, longitude;
  final double? accuracy;
  final bool isMocked;
  final String? address, area;

  String get label => area ?? address ?? '${latitude.toStringAsFixed(5)}, ${longitude.toStringAsFixed(5)}';

  Map<String, dynamic> toJson() => {
        'latitude': double.parse(latitude.toStringAsFixed(6)),
        'longitude': double.parse(longitude.toStringAsFixed(6)),
        if (accuracy != null) 'accuracy': double.parse(accuracy!.toStringAsFixed(1)),
        'is_mocked': isMocked,
        if (address != null) 'address': address,
        if (area != null) 'area': area,
      };
}

class LocationError implements Exception {
  LocationError(this.message, {this.openSettings = false});
  final String message;
  final bool openSettings;
  @override
  String toString() => message;
}

class LocationService {
  /// Asks for permission if needed and returns the current position. Throws [LocationError] with a user-friendly message.
  static Future<LocationFix> current() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      throw LocationError('Location is turned off. Turn on location (GPS) to continue.', openSettings: true);
    }
    var perm = await Geolocator.checkPermission();
    if (perm == LocationPermission.denied) perm = await Geolocator.requestPermission();
    if (perm == LocationPermission.deniedForever) {
      throw LocationError('Location permission is blocked. Allow it in the app settings to continue.', openSettings: true);
    }
    if (perm == LocationPermission.denied) {
      throw LocationError('Location permission is needed to record attendance.');
    }
    Position p;
    try {
      p = await Geolocator.getCurrentPosition(
          locationSettings: const LocationSettings(accuracy: LocationAccuracy.high, timeLimit: Duration(seconds: 20)));
    } on TimeoutException {
      throw LocationError('Could not get a GPS fix. Move to an open area and try again.');
    } catch (_) {
      throw LocationError('Could not get your location. Please try again.');
    }
    final place = await _describe(p.latitude, p.longitude);
    return LocationFix(
      latitude: p.latitude,
      longitude: p.longitude,
      accuracy: p.accuracy,
      isMocked: p.isMocked,
      address: place?.$1,
      area: place?.$2,
    );
  }

  static Future<void> openSettings() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      await Geolocator.openLocationSettings();
    } else {
      await Geolocator.openAppSettings();
    }
  }

  /// (address, area) from the device geocoder; null when offline or unavailable. Never throws.
  static Future<(String?, String?)?> _describe(double lat, double lng) async {
    try {
      final marks = await placemarkFromCoordinates(lat, lng).timeout(const Duration(seconds: 6));
      if (marks.isEmpty) return null;
      final m = marks.first;
      String? clean(String? s) => (s == null || s.trim().isEmpty) ? null : s.trim();
      final parts = <String>[];
      for (final s in [clean(m.street) ?? clean(m.name), clean(m.subLocality), clean(m.locality), clean(m.administrativeArea)]) {
        if (s != null && !parts.contains(s)) parts.add(s);
      }
      final areaParts = <String>[];
      for (final s in [clean(m.subLocality), clean(m.locality) ?? clean(m.administrativeArea)]) {
        if (s != null && !areaParts.contains(s)) areaParts.add(s);
      }
      String? cut(String s, int n) => s.isEmpty ? null : (s.length <= n ? s : s.substring(0, n));
      return (cut(parts.join(', '), 300), cut(areaParts.join(', '), 150));
    } catch (_) {
      return null;
    }
  }
}
