#!/usr/bin/env bash
# Generates the android/ and ios/ platform folders (needs the Flutter SDK) and applies FieldSales permissions.
# Run from the mobile/ directory:   bash tool/setup_platforms.sh
set -euo pipefail
command -v flutter >/dev/null || { echo "Flutter SDK not found. Install it from https://docs.flutter.dev/get-started/install"; exit 1; }

flutter create . --project-name fieldsales_mobile --org com.fieldsales --platforms android,ios
flutter pub get

python3 - <<'PY'
import re, pathlib

# ---------- Android ----------
m = pathlib.Path("android/app/src/main/AndroidManifest.xml")
s = m.read_text()
perms = """    <uses-permission android:name="android.permission.INTERNET"/>
    <uses-permission android:name="android.permission.CAMERA"/>
    <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>
    <uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION"/>
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>
    <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED"/>
    <uses-feature android:name="android.hardware.camera" android:required="false"/>
    <uses-feature android:name="android.hardware.location.gps" android:required="false"/>
"""
if "ACCESS_FINE_LOCATION" not in s:
    s = s.replace("<application", perms + "    <application", 1)
# receivers needed by flutter_local_notifications to restore scheduled reminders after reboot
receivers = """        <receiver android:exported="false" android:name="com.dexterous.flutterlocalnotifications.ScheduledNotificationReceiver"/>
        <receiver android:exported="false" android:name="com.dexterous.flutterlocalnotifications.ScheduledNotificationBootReceiver">
            <intent-filter>
                <action android:name="android.intent.action.BOOT_COMPLETED"/>
                <action android:name="android.intent.action.MY_PACKAGE_REPLACED"/>
            </intent-filter>
        </receiver>
"""
if "ScheduledNotificationReceiver" not in s:
    s = s.replace("</application>", receivers + "    </application>", 1)
s = s.replace('android:label="fieldsales_mobile"', 'android:label="FieldSales"')
m.write_text(s)

# Debug builds may talk to http://10.0.2.2 (emulator -> host). Release builds stay HTTPS-only.
d = pathlib.Path("android/app/src/debug/AndroidManifest.xml")
if d.exists():
    t = d.read_text()
    if "usesCleartextTraffic" not in t:
        t = t.replace("</manifest>", '    <application android:usesCleartextTraffic="true"/>\n</manifest>')
        d.write_text(t)

# ---------- iOS ----------
p = pathlib.Path("ios/Runner/Info.plist")
s = p.read_text()
keys = """	<key>NSCameraUsageDescription</key>
	<string>FieldSales uses the camera to attach photos to customers and visits.</string>
	<key>NSPhotoLibraryUsageDescription</key>
	<string>FieldSales lets you choose a photo to attach to a visit.</string>
	<key>NSLocationWhenInUseUsageDescription</key>
	<string>FieldSales records your location when you capture a visit location and when you start or end your day or a break (attendance).</string>
	<key>NSAppTransportSecurity</key>
	<dict>
		<key>NSAllowsLocalNetworking</key>
		<true/>
	</dict>
"""
if "NSCameraUsageDescription" not in s:
    s = s.replace("</dict>\n</plist>", keys + "</dict>\n</plist>")
    p.write_text(s)
print("Platform permissions applied.")
PY

cat <<'MSG'

Two manual Android Gradle steps remain (the generated file format depends on your Flutter version):
  1. android/app/build.gradle(.kts): set minSdk to 23 (required by flutter_secure_storage).
  2. flutter_local_notifications needs core-library desugaring:
       compileOptions { isCoreLibraryDesugaringEnabled = true }      (Kotlin DSL)
       dependencies  { coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4") }
Then:  flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
MSG
