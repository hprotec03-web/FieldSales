"""Applies the two Android Gradle settings FieldSales needs, for either Gradle DSL.

  * minSdk 23                     (flutter_secure_storage)
  * core library desugaring       (flutter_local_notifications)

Run from the mobile/ directory after `flutter create`:   python3 tool/patch_gradle.py
"""
import pathlib
import re
import sys

DESUGAR = "com.android.tools:desugar_jdk_libs:2.1.4"
kts = pathlib.Path("android/app/build.gradle.kts")
groovy = pathlib.Path("android/app/build.gradle")


def patch_kotlin(s: str) -> str:
    s = re.sub(r"minSdk\s*=\s*[^\n]+", "minSdk = 23", s)
    if "isCoreLibraryDesugaringEnabled" not in s:
        s = re.sub(r"(compileOptions\s*\{)", r"\1\n        isCoreLibraryDesugaringEnabled = true\n", s, count=1)
    if "coreLibraryDesugaring(" not in s:
        if re.search(r"^dependencies\s*\{", s, re.M):
            s = re.sub(r"(^dependencies\s*\{)", rf'\1\n    coreLibraryDesugaring("{DESUGAR}")', s, count=1, flags=re.M)
        else:
            s += f'\ndependencies {{\n    coreLibraryDesugaring("{DESUGAR}")\n}}\n'
    return s


def patch_groovy(s: str) -> str:
    s = re.sub(r"minSdk(?:Version)?\s*=?\s*[^\n]+", "minSdkVersion 23", s, count=1)
    if "coreLibraryDesugaringEnabled" not in s:
        s = re.sub(r"(compileOptions\s*\{)", r"\1\n        coreLibraryDesugaringEnabled true\n", s, count=1)
    if "coreLibraryDesugaring '" not in s and 'coreLibraryDesugaring "' not in s:
        if re.search(r"^dependencies\s*\{", s, re.M):
            s = re.sub(r"(^dependencies\s*\{)", rf"\1\n    coreLibraryDesugaring '{DESUGAR}'", s, count=1, flags=re.M)
        else:
            s += f"\ndependencies {{\n    coreLibraryDesugaring '{DESUGAR}'\n}}\n"
    return s


if kts.exists():
    kts.write_text(patch_kotlin(kts.read_text()))
    print("Patched", kts)
elif groovy.exists():
    groovy.write_text(patch_groovy(groovy.read_text()))
    print("Patched", groovy)
else:
    sys.exit("android/app/build.gradle(.kts) not found - run `flutter create` first.")
